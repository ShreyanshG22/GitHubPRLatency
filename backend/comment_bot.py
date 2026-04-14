import os
import httpx
import logging

logger = logging.getLogger(__name__)


async def post_review_comment(
    repo_full_name: str,
    pr_number: int,
    comments: list,
    summary: str,
    score: int,
    commit_sha: str = ""
) -> bool:
    """Post review comments on a GitHub pull request."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("GITHUB_TOKEN not configured, skipping comment posting")
        return False

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "PR-Review-Bot",
    }

    # Post a summary comment on the PR
    summary_body = f"## PR Review Bot Analysis\n\n"
    summary_body += f"**Score: {score}/100**\n\n"
    summary_body += f"{summary}\n\n"

    if comments:
        summary_body += f"Found **{len(comments)}** issue(s):\n"
        for c in comments:
            icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(c.get("severity", "info"), "🔵")
            summary_body += f"- {icon} `{c.get('path', '')}:{c.get('line', '')}` — {c.get('body', '')}\n"
    else:
        summary_body += "No issues found. Code looks good!"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Post issue comment (summary)
            comment_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
            response = await client.post(
                comment_url,
                headers=headers,
                json={"body": summary_body}
            )

            if response.status_code in (200, 201):
                logger.info(f"Posted review summary on {repo_full_name}#{pr_number}")
                return True
            else:
                logger.error(f"Failed to post comment: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        logger.error(f"Failed to post review: {e}")
        return False
