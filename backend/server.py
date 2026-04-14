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
from comment_bot import post_review_comment, format_review_body
from diff_parser import parse_diff
from cpp_analyzer import analyze_cpp, analyze_cpp_blocks, ALL_RULE_NAMES

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

    return {"id": user_id, "email": email, "name": data.name, "role": "user", "created_at": user_doc["created_at"], "token": access_token}


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
        "role": user.get("role", "user"), "created_at": user.get("created_at", ""),
        "token": access_token
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


# ─── Rate Limiting ───────────────────────────────────────────────────
async def check_rate_limit(repo_full_name: str, default_rpm: int = 30) -> bool:
    """Check if a repo has exceeded its rate limit. Returns True if allowed."""
    # Check for per-repo override
    repo_settings = await db.repo_settings.find_one(
        {"repo_full_name": repo_full_name}, {"_id": 0}
    )
    max_rpm = (repo_settings or {}).get("rate_limit_rpm", default_rpm)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=60)

    count = await db.rate_limits.count_documents({
        "repo": repo_full_name,
        "ts": {"$gte": window_start}
    })

    if count >= max_rpm:
        return False

    await db.rate_limits.insert_one({"repo": repo_full_name, "ts": now})
    return True


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

        # Parse diff into structured code blocks
        parsed = parse_diff(diff)
        logger.info(
            f"Parsed {repo_full_name}#{pr_number}: "
            f"{parsed.file_count} files, {parsed.total_blocks} blocks"
        )

        # Analyze with structured blocks
        result = await analyze_diff(diff, pr_title, pr_author, parsed=parsed)

        # ── P1: Load per-repo rule configuration ──
        repo_settings = await db.repo_settings.find_one(
            {"repo_full_name": repo_full_name}, {"_id": 0}
        )
        rule_config = (repo_settings or {}).get("rule_config")
        severity_threshold = (repo_settings or {}).get("severity_threshold")
        auto_post = (repo_settings or {}).get("auto_post_comments", True)

        # Run static C++ analysis on any C++ files in the diff
        from diff_parser import Language
        cpp_files = parsed.files_by_language(Language.CPP)
        cpp_static_findings = []
        for cpp_file in cpp_files:
            report = analyze_cpp_blocks(cpp_file.blocks, cpp_file.path, config=rule_config)
            for f in report.findings:
                cpp_static_findings.append({
                    "path": report.file_path,
                    "line": f.line,
                    "body": f"[{f.rule}] {f.explanation} — {f.suggestion}",
                    "severity": {"high": "error", "medium": "warning", "low": "info"}.get(f.severity, "info"),
                })

        # Merge static findings into LLM comments
        if cpp_static_findings:
            result["comments"] = result.get("comments", []) + cpp_static_findings
            logger.info(f"Added {len(cpp_static_findings)} C++ static findings for {repo_full_name}#{pr_number}")

        # ── P1: Apply severity threshold filter ──
        if severity_threshold:
            threshold_map = {"high": 0, "error": 0, "medium": 1, "warning": 1, "low": 2, "info": 2}
            threshold_val = threshold_map.get(severity_threshold, 2)
            result["comments"] = [
                c for c in result["comments"]
                if threshold_map.get(c.get("severity", "info"), 2) <= threshold_val
            ]

        # Update analysis
        update_data = {
            "summary": result["summary"],
            "score": result["score"],
            "comments": result["comments"],
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        await db.reviews.update_one({"id": analysis.id}, {"$set": update_data})

        # Post comment to GitHub (respects per-repo auto_post setting)
        if auto_post:
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

    # ── P1: Webhook retry deduplication ──
    if delivery_id:
        existing = await db.webhook_logs.find_one({"delivery_id": delivery_id})
        if existing:
            logger.info(f"Duplicate delivery {delivery_id} — skipping")
            return {"message": "Delivery already processed", "duplicate": True}

    # ── P1: Rate limiting ──
    if not await check_rate_limit(repo_full_name):
        logger.warning(f"Rate limit exceeded for {repo_full_name}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded for this repository")

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

    # ── P1: Check repo settings — is this repo enabled? ──
    repo_settings = await db.repo_settings.find_one(
        {"repo_full_name": repo_full_name}, {"_id": 0}
    )
    if repo_settings and not repo_settings.get("enabled", True):
        return {"message": f"Analysis disabled for {repo_full_name}"}

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


# ─── P2: Trends API ──────────────────────────────────────────────────
@api_router.get("/stats/trends")
async def get_stats_trends(request: Request, days: int = 30):
    """Return daily review counts and average scores for charting."""
    await get_current_user(request)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    pipeline = [
        {"$match": {"status": "completed", "completed_at": {"$gte": cutoff}}},
        {"$addFields": {"date": {"$substr": ["$completed_at", 0, 10]}}},
        {"$group": {
            "_id": "$date",
            "count": {"$sum": 1},
            "avg_score": {"$avg": "$score"},
            "min_score": {"$min": "$score"},
            "max_score": {"$max": "$score"},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = await db.reviews.aggregate(pipeline).to_list(days)
    return [
        {
            "date": r["_id"],
            "count": r["count"],
            "avg_score": round(r["avg_score"], 1),
            "min_score": r["min_score"],
            "max_score": r["max_score"],
        }
        for r in results
    ]


# ─── P2: Webhook Replay ──────────────────────────────────────────────
@api_router.post("/webhook-logs/{log_id}/replay")
async def replay_webhook(log_id: str, request: Request, background_tasks: BackgroundTasks):
    """Re-trigger processing for a webhook delivery."""
    await get_current_user(request)
    log_entry = await db.webhook_logs.find_one({"id": log_id}, {"_id": 0})
    if not log_entry:
        raise HTTPException(status_code=404, detail="Webhook log not found")

    if log_entry.get("event_type") != "pull_request":
        raise HTTPException(status_code=400, detail="Only pull_request events can be replayed")

    # Find the original review to get PR info
    pr_number = log_entry.get("pr_number")
    repo_full_name = log_entry.get("repo_full_name", "")
    if not pr_number or not repo_full_name:
        raise HTTPException(status_code=400, detail="Missing PR number or repo info")

    # Create a synthetic payload for reprocessing
    replay_delivery = f"replay-{log_id}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    synthetic_payload = {
        "action": "reopened",
        "pull_request": {
            "number": pr_number,
            "title": f"[Replay] PR #{pr_number}",
            "user": {"login": "replay"},
            "html_url": f"https://github.com/{repo_full_name}/pull/{pr_number}",
            "head": {"sha": ""},
        },
        "repository": {"full_name": repo_full_name},
    }

    # Log the replay
    replay_log = WebhookLog(
        event_type="pull_request",
        action="replay",
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        delivery_id=replay_delivery,
        status="received"
    )
    await db.webhook_logs.insert_one(replay_log.model_dump())

    background_tasks.add_task(process_pull_request, synthetic_payload, replay_delivery)
    return {"message": f"Replaying analysis for {repo_full_name}#{pr_number}", "delivery_id": replay_delivery}


# ─── P2: Team Management ─────────────────────────────────────────────
@api_router.get("/team")
async def list_team(request: Request):
    """List all users (admin only)."""
    current = await get_current_user(request)
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
    # Add string id
    for u in users:
        if "_id" in u:
            del u["_id"]
    return users


@api_router.put("/team/{user_email}/role")
async def update_user_role(user_email: str, request: Request):
    """Update a user's role (admin only)."""
    current = await get_current_user(request)
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    new_role = body.get("role", "")
    if new_role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be admin, member, or viewer")

    result = await db.users.update_one(
        {"email": user_email.lower()},
        {"$set": {"role": new_role}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"Role updated to {new_role}", "email": user_email}


@api_router.delete("/team/{user_email}")
async def remove_team_member(user_email: str, request: Request):
    """Remove a user (admin only, cannot remove self)."""
    current = await get_current_user(request)
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if current["email"] == user_email.lower():
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.users.delete_one({"email": user_email.lower()})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user_email} removed"}


@api_router.get("/")
async def root():
    return {"message": "PR Review Bot API", "version": "1.0.0"}


# ─── Diff Parser Test Endpoint ────────────────────────────────────────
from pydantic import BaseModel as _BM

class DiffParseRequest(_BM):
    diff_text: str

class CppAnalyzeRequest(_BM):
    code: str
    file_path: str = "<input>"
    start_line: int = 1
    config: dict | None = None

class PreviewCommentRequest(_BM):
    comments: list = []
    summary: str = "Analysis complete."
    score: int = 75

class RepoSettingsCreate(_BM):
    repo_full_name: str
    enabled: bool = True
    auto_post_comments: bool = True
    rate_limit_rpm: int = 30
    severity_threshold: str | None = None  # "high", "medium", or None (all)
    rule_config: dict | None = None  # {enabled_rules, disabled_rules, severity_overrides}

class RepoSettingsUpdate(_BM):
    enabled: bool | None = None
    auto_post_comments: bool | None = None
    rate_limit_rpm: int | None = None
    severity_threshold: str | None = None
    rule_config: dict | None = None

@api_router.post("/parse-diff")
async def parse_diff_endpoint(body: DiffParseRequest, request: Request):
    """Parse a raw unified diff and return structured code blocks."""
    await get_current_user(request)
    parsed = parse_diff(body.diff_text)
    return {
        "file_count": parsed.file_count,
        "total_blocks": parsed.total_blocks,
        "files": [
            {
                "path": f.path,
                "language": f.language.value,
                "added_lines": f.total_added_lines,
                "modified_lines": f.total_modified_lines,
                "blocks": [
                    {
                        "start_line": b.start_line,
                        "end_line": b.end_line,
                        "change_type": b.change_type.value,
                        "line_count": b.line_count,
                        "text": b.text,
                    }
                    for b in f.blocks
                ],
            }
            for f in parsed.files
        ],
    }


@api_router.post("/analyze-cpp")
async def analyze_cpp_endpoint(body: CppAnalyzeRequest, request: Request):
    """Run C++ static performance analysis on submitted code."""
    await get_current_user(request)
    report = analyze_cpp(body.code, body.file_path, body.start_line, config=body.config)
    return {
        "file_path": report.file_path,
        "total_findings": report.count,
        "high": len(report.by_severity("high")),
        "medium": len(report.by_severity("medium")),
        "low": len(report.by_severity("low")),
        "findings": report.to_dicts(),
    }


@api_router.post("/preview-comment")
async def preview_comment_endpoint(body: PreviewCommentRequest, request: Request):
    """Preview the formatted markdown that would be posted to GitHub."""
    await get_current_user(request)
    markdown = format_review_body(body.comments, body.summary, body.score)
    return {"markdown": markdown}


# ─── P1: Repo Settings CRUD ──────────────────────────────────────────
@api_router.get("/available-rules")
async def get_available_rules(request: Request):
    """Return all available C++ analysis rule names."""
    await get_current_user(request)
    return {"rules": ALL_RULE_NAMES}


@api_router.get("/repo-settings")
async def list_repo_settings(request: Request):
    """List all configured repository settings."""
    await get_current_user(request)
    settings = await db.repo_settings.find({}, {"_id": 0}).to_list(100)
    return settings


@api_router.get("/repo-settings/{repo_owner}/{repo_name}")
async def get_repo_settings(repo_owner: str, repo_name: str, request: Request):
    """Get settings for a specific repository."""
    await get_current_user(request)
    repo_full_name = f"{repo_owner}/{repo_name}"
    settings = await db.repo_settings.find_one(
        {"repo_full_name": repo_full_name}, {"_id": 0}
    )
    if not settings:
        # Return defaults
        return {
            "repo_full_name": repo_full_name,
            "enabled": True,
            "auto_post_comments": True,
            "rate_limit_rpm": 30,
            "severity_threshold": None,
            "rule_config": None,
            "is_default": True,
        }
    return settings


@api_router.post("/repo-settings")
async def create_repo_settings(body: RepoSettingsCreate, request: Request):
    """Create settings for a repository."""
    await get_current_user(request)
    existing = await db.repo_settings.find_one({"repo_full_name": body.repo_full_name})
    if existing:
        raise HTTPException(status_code=409, detail="Settings already exist for this repo. Use PUT to update.")

    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_at"] = doc["created_at"]
    await db.repo_settings.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.put("/repo-settings/{repo_owner}/{repo_name}")
async def update_repo_settings(repo_owner: str, repo_name: str, body: RepoSettingsUpdate, request: Request):
    """Update settings for a repository (partial update)."""
    await get_current_user(request)
    repo_full_name = f"{repo_owner}/{repo_name}"

    update_fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.repo_settings.find_one_and_update(
        {"repo_full_name": repo_full_name},
        {"$set": update_fields},
        upsert=True,
        return_document=True,
    )
    result.pop("_id", None)
    # Ensure repo_full_name is set on upsert
    if "repo_full_name" not in result:
        await db.repo_settings.update_one(
            {"repo_full_name": repo_full_name},
            {"$set": {"repo_full_name": repo_full_name}}
        )
        result["repo_full_name"] = repo_full_name
    return result


@api_router.delete("/repo-settings/{repo_owner}/{repo_name}")
async def delete_repo_settings(repo_owner: str, repo_name: str, request: Request):
    """Delete settings for a repository (reverts to defaults)."""
    await get_current_user(request)
    repo_full_name = f"{repo_owner}/{repo_name}"
    result = await db.repo_settings.delete_one({"repo_full_name": repo_full_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No settings found for this repo")
    return {"message": f"Settings deleted for {repo_full_name}"}


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
    # P1 indexes
    await db.rate_limits.create_index("ts", expireAfterSeconds=120)  # auto-expire after 2 min
    await db.rate_limits.create_index([("repo", 1), ("ts", 1)])
    await db.repo_settings.create_index("repo_full_name", unique=True)
    await db.webhook_logs.create_index("delivery_id")

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
        f.write("# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write("## Auth Endpoints\n")
        f.write("- POST /api/auth/register\n- POST /api/auth/login\n")
        f.write("- POST /api/auth/logout\n- GET /api/auth/me\n")
        f.write("- POST /api/auth/refresh\n- POST /api/auth/forgot-password\n")
        f.write("- POST /api/auth/reset-password\n\n")
        f.write("## Webhook Endpoint\n- POST /api/github-webhook\n\n")
        f.write("## Dashboard Endpoints (auth required)\n")
        f.write("- GET /api/webhook-logs\n- GET /api/reviews\n")
        f.write("- GET /api/reviews/{review_id}\n- GET /api/stats\n\n")
        f.write("## Repo Settings Endpoints (auth required)\n")
        f.write("- GET /api/available-rules\n")
        f.write("- GET /api/repo-settings\n")
        f.write("- GET /api/repo-settings/{owner}/{name}\n")
        f.write("- POST /api/repo-settings\n")
        f.write("- PUT /api/repo-settings/{owner}/{name}\n")
        f.write("- DELETE /api/repo-settings/{owner}/{name}\n")

    logger.info("PR Review Bot API started")


@app.on_event("shutdown")
async def shutdown():
    client.close()
