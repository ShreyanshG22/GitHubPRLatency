from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
import uuid


# ─── Auth Models ─────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str
    password: str
    name: str = "User"


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str
    created_at: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ─── GitHub Webhook Models ───────────────────────────────────────────
class PullRequestInfo(BaseModel):
    number: int
    title: str
    author: str
    repo_full_name: str
    base_branch: str
    head_branch: str
    url: str


class ReviewComment(BaseModel):
    path: str
    line: int
    body: str
    severity: str = "info"  # info, warning, error


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pr_number: int
    repo_full_name: str
    pr_title: str
    pr_author: str
    pr_url: str
    summary: str
    comments: List[ReviewComment] = []
    score: int = 0  # 0-100 performance score
    status: str = "pending"  # pending, analyzing, completed, failed
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


class WebhookLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    action: str
    repo_full_name: str
    pr_number: Optional[int] = None
    delivery_id: str = ""
    status: str = "received"  # received, processed, failed
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
