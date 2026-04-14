from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, Request, HTTPException, Response, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import json
import bcrypt
import jwt
import secrets
from datetime import datetime, timezone, timedelta

from models import (
    UserCreate, UserLogin, UserResponse, ForgotPasswordRequest,
    ResetPasswordRequest, AnalysisResult, WebhookLog, PullRequestInfo
)
from github_client import validate_webhook_signature, fetch_pr_diff
from analyzer import analyze_diff
from comment_bot import post_review_comment

# ─── Config ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"

# ─── MongoDB ─────────────────────────────────────────────────────────
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# ─── App Setup ───────────────────────────────────────────────────────
app = FastAPI(title="PR Review Bot API")
api_router = APIRouter(prefix="/api")


# ─── Password Helpers ────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT Helpers ─────────────────────────────────────────────────────
def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Brute Force Protection ─────────────────────────────────────────
async def check_brute_force(identifier: str):
    record = await db.login_attempts.find_one({"identifier": identifier})
    if record and record.get("attempts", 0) >= 5:
        locked_until = record.get("locked_until")
        if locked_until and datetime.now(timezone.utc) < locked_until:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})


async def record_failed_attempt(identifier: str):
    record = await db.login_attempts.find_one({"identifier": identifier})
    if record:
        new_attempts = record.get("attempts", 0) + 1
        update = {"$set": {"attempts": new_attempts}}
        if new_attempts >= 5:
            update["$set"]["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=15)
        await db.login_attempts.update_one({"identifier": identifier}, update)
    else:
        await db.login_attempts.insert_one({"identifier": identifier, "attempts": 1})


async def clear_failed_attempts(identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})


# ─── Auth Endpoints ──────────────────────────────────────────────────
@api_router.post("/auth/register")
async def register(data: UserCreate, response: Response):
    email = data.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(data.password)
    user_doc = {
        "email": email,
        "password_hash": hashed,
        "name": data.name,
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    return {"id": user_id, "email": email, "name": data.name, "role": "user", "created_at": user_doc["created_at"]}


@api_router.post("/auth/login")
async def login(data: UserLogin, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    await check_brute_force(identifier)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        await record_failed_attempt(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_failed_attempts(identifier)
    user_id = str(user["_id"])

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "id": user_id, "email": user["email"], "name": user.get("name", ""),
        "role": user.get("role", "user"), "created_at": user.get("created_at", "")
    }


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}


@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return {
        "id": user["_id"], "email": user["email"],
        "name": user.get("name", ""), "role": user.get("role", "user"),
        "created_at": user.get("created_at", "")
    }


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access_token = create_access_token(str(user["_id"]), user["email"])
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@api_router.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    email = data.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user:
        return {"message": "If that email exists, a reset link has been sent"}
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token": token,
        "user_id": str(user["_id"]),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False
    })
    logger.info(f"Password reset link: /reset-password?token={token}")
    return {"message": "If that email exists, a reset link has been sent"}


@api_router.post("/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    record = await db.password_reset_tokens.find_one({"token": data.token, "used": False})
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if record["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    hashed = hash_password(data.new_password)
    await db.users.update_one({"_id": ObjectId(record["user_id"])}, {"$set": {"password_hash": hashed}})
    await db.password_reset_tokens.update_one({"token": data.token}, {"$set": {"used": True}})
    return {"message": "Password reset successfully"}


# ─── GitHub Webhook Endpoint ─────────────────────────────────────────
async def process_pull_request(payload: dict, delivery_id: str):
    """Background task: analyze PR and post review."""
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    pr_number = pr.get("number", 0)
    repo_full_name = repo.get("full_name", "")
    pr_title = pr.get("title", "")
    pr_author = pr.get("user", {}).get("login", "unknown")
    pr_url = pr.get("html_url", "")
    head_sha = pr.get("head", {}).get("sha", "")

    analysis = AnalysisResult(
        pr_number=pr_number,
        repo_full_name=repo_full_name,
        pr_title=pr_title,
        pr_author=pr_author,
        pr_url=pr_url,
        summary="Analyzing...",
        status="analyzing"
    )

    # Store initial analysis record
    analysis_doc = analysis.model_dump()
    await db.reviews.insert_one(analysis_doc)

    try:
        # Fetch diff
        diff = await fetch_pr_diff(repo_full_name, pr_number)

        # Analyze
        result = await analyze_diff(diff, pr_title, pr_author)

        # Update analysis
        update_data = {
            "summary": result["summary"],
            "score": result["score"],
            "comments": result["comments"],
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        await db.reviews.update_one({"id": analysis.id}, {"$set": update_data})

        # Post comment to GitHub
        await post_review_comment(
            repo_full_name, pr_number,
            result["comments"], result["summary"],
            result["score"], head_sha
        )

        # Update webhook log
        await db.webhook_logs.update_one(
            {"delivery_id": delivery_id},
            {"$set": {"status": "processed"}}
        )

        logger.info(f"Completed review for {repo_full_name}#{pr_number} - Score: {result['score']}")

    except Exception as e:
        logger.error(f"Failed to process PR {repo_full_name}#{pr_number}: {e}")
        await db.reviews.update_one(
            {"id": analysis.id},
            {"$set": {"status": "failed", "summary": f"Analysis failed: {str(e)}"}}
        )
        await db.webhook_logs.update_one(
            {"delivery_id": delivery_id},
            {"$set": {"status": "failed", "error_message": str(e)}}
        )


@api_router.post("/github-webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events for pull request reviews."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    # Validate signature
    if not validate_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)
    action = payload.get("action", "")
    repo = payload.get("repository", {})
    repo_full_name = repo.get("full_name", "unknown")
    pr_number = payload.get("pull_request", {}).get("number") if "pull_request" in payload else None

    # Log webhook event
    log = WebhookLog(
        event_type=event,
        action=action,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        delivery_id=delivery_id,
        status="received"
    )
    await db.webhook_logs.insert_one(log.model_dump())

    # Handle ping event
    if event == "ping":
        return {"message": "pong"}

    # Handle pull request events
    if event == "pull_request" and action in ("opened", "synchronize", "reopened"):
        background_tasks.add_task(process_pull_request, payload, delivery_id)
        return {"message": f"Processing PR #{pr_number} from {repo_full_name}"}

    return {"message": f"Event '{event}:{action}' acknowledged but not processed"}


# ─── Dashboard API Endpoints ─────────────────────────────────────────
@api_router.get("/webhook-logs")
async def get_webhook_logs(request: Request, limit: int = 50):
    await get_current_user(request)
    logs = await db.webhook_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return logs


@api_router.get("/reviews")
async def get_reviews(request: Request, limit: int = 50):
    await get_current_user(request)
    reviews = await db.reviews.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return reviews


@api_router.get("/reviews/{review_id}")
async def get_review(review_id: str, request: Request):
    await get_current_user(request)
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@api_router.get("/stats")
async def get_stats(request: Request):
    await get_current_user(request)
    total_webhooks = await db.webhook_logs.count_documents({})
    total_reviews = await db.reviews.count_documents({})
    completed_reviews = await db.reviews.count_documents({"status": "completed"})
    failed_reviews = await db.reviews.count_documents({"status": "failed"})

    avg_score = 0
    if completed_reviews > 0:
        pipeline = [
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "avg": {"$avg": "$score"}}}
        ]
        result = await db.reviews.aggregate(pipeline).to_list(1)
        if result:
            avg_score = round(result[0]["avg"], 1)

    return {
        "total_webhooks": total_webhooks,
        "total_reviews": total_reviews,
        "completed_reviews": completed_reviews,
        "failed_reviews": failed_reviews,
        "avg_score": avg_score
    }


@api_router.get("/")
async def root():
    return {"message": "PR Review Bot API", "version": "1.0.0"}


# ─── Include Router & Middleware ──────────────────────────────────────
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup / Shutdown ──────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.webhook_logs.create_index("created_at")
    await db.reviews.create_index("created_at")

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        logger.info("Admin password updated")

    # Write test credentials
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write(f"# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write(f"## Auth Endpoints\n")
        f.write(f"- POST /api/auth/register\n- POST /api/auth/login\n")
        f.write(f"- POST /api/auth/logout\n- GET /api/auth/me\n")
        f.write(f"- POST /api/auth/refresh\n- POST /api/auth/forgot-password\n")
        f.write(f"- POST /api/auth/reset-password\n\n")
        f.write(f"## Webhook Endpoint\n- POST /api/github-webhook\n\n")
        f.write(f"## Dashboard Endpoints (auth required)\n")
        f.write(f"- GET /api/webhook-logs\n- GET /api/reviews\n")
        f.write(f"- GET /api/reviews/{{review_id}}\n- GET /api/stats\n")

    logger.info("PR Review Bot API started")


@app.on_event("shutdown")
async def shutdown():
    client.close()
