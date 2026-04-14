import os
import hmac
import hashlib
import httpx
import logging

logger = logging.getLogger(__name__)


def validate_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Validate the GitHub webhook signature using HMAC-SHA256."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not configured, skipping signature validation")
        return True

    if not signature_header:
        return False

    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


async def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the diff of a pull request from GitHub API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "PR-Review-Bot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        logger.error(f"Failed to fetch PR diff: {response.status_code} - {response.text}")
        raise Exception(f"GitHub API error: {response.status_code}")


async def fetch_pr_files(repo_full_name: str, pr_number: int) -> list:
    """Fetch the list of changed files in a pull request."""
    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PR-Review-Bot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        logger.error(f"Failed to fetch PR files: {response.status_code}")
        raise Exception(f"GitHub API error: {response.status_code}")
