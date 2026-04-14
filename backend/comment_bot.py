"""
comment_bot.py — Format and post review comments on GitHub pull requests.

Uses GitHub REST API to post richly formatted markdown comments
with severity-based sections for each finding.
"""

import os
import httpx
import logging
from typing import List

logger = logging.getLogger(__name__)


# ─── Severity Mapping ────────────────────────────────────────────────

_SEVERITY_CONFIG = {
    "high": {
        "icon": "\u26d4",        # ⛔
        "label": "Performance Error",
        "priority": 0,
    },
    "error": {
        "icon": "\u26d4",
        "label": "Performance Error",
        "priority": 0,
    },
    "medium": {
        "icon": "\u26a0\ufe0f",  # ⚠️
        "label": "Performance Warning",
        "priority": 1,
    },
    "warning": {
        "icon": "\u26a0\ufe0f",
        "label": "Performance Warning",
        "priority": 1,
    },
    "low": {
        "icon": "\U0001f4a1",    # 💡
        "label": "Suggestion",
        "priority": 2,
    },
    "info": {
        "icon": "\U0001f4a1",
        "label": "Suggestion",
        "priority": 2,
    },
}


def _sev(raw: str) -> dict:
    return _SEVERITY_CONFIG.get(raw, _SEVERITY_CONFIG["info"])


# ─── Markdown Formatters ─────────────────────────────────────────────

def _format_score_bar(score: int) -> str:
    """Render a visual score bar using unicode block characters."""
    filled = round(score / 10)
    empty = 10 - filled
    bar = "\u2588" * filled + "\u2591" * empty
    return f"`{bar}` **{score}/100**"


def _format_single_finding(comment: dict) -> str:
    """Format one finding into a markdown section matching the example format.

    Accepts dicts with mixed key sets:
    - LLM comments:    {path, line, body, severity}
    - Static findings: {path, line, severity, rule, explanation, suggestion, snippet}
    """
    severity_raw = comment.get("severity", "info")
    cfg = _sev(severity_raw)

    path = comment.get("path", "")
    line = comment.get("line", "")
    location = f"`{path}:{line}`" if path and line else (f"`{path}`" if path else "")

    # Extract rule / explanation / suggestion — either from dedicated fields
    # (cpp_analyzer) or parsed from the 'body' field (LLM / merged comments).
    rule = comment.get("rule", "")
    explanation = comment.get("explanation", "")
    suggestion = comment.get("suggestion", "")
    body = comment.get("body", "")

    # If we only have 'body' (LLM comments), use it as the explanation
    if body and not explanation:
        # Check if body contains our merged format: "[rule] explanation — suggestion"
        if body.startswith("[") and "] " in body:
            bracket_end = body.index("] ")
            rule = body[1:bracket_end]
            rest = body[bracket_end + 2:]
            if " \u2014 " in rest:
                explanation, suggestion = rest.split(" \u2014 ", 1)
            else:
                explanation = rest
        else:
            explanation = body

    # Build the markdown block
    lines: List[str] = []
    lines.append(f"#### {cfg['icon']} {cfg['label']}")

    if rule:
        lines.append(f"**Rule:** `{rule}`")

    if location:
        lines.append(f"**File:** {location}")

    lines.append("")

    if explanation:
        lines.append("**Explanation:**")
        lines.append(explanation)
        lines.append("")

    if suggestion:
        lines.append("**Suggestion:**")
        lines.append(suggestion)
        lines.append("")

    snippet = comment.get("snippet", "")
    if snippet:
        lines.append("<details><summary>Code</summary>")
        lines.append("")
        lines.append("```cpp")
        lines.append(snippet)
        lines.append("```")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def format_review_body(
    comments: list,
    summary: str,
    score: int,
) -> str:
    """Build the full markdown body for a PR review comment.

    Returns a formatted string ready to post to GitHub.
    """
    parts: List[str] = []

    # ── Header ──
    parts.append("# PR Review Bot Analysis")
    parts.append("")
    parts.append(f"## {_format_score_bar(score)}")
    parts.append("")
    parts.append(summary)
    parts.append("")

    if not comments:
        parts.append("---")
        parts.append("")
        parts.append("> No issues found. Code looks good! :white_check_mark:")
        return "\n".join(parts)

    # ── Stats line ──
    high_count = sum(1 for c in comments if _sev(c.get("severity", "info"))["priority"] == 0)
    med_count = sum(1 for c in comments if _sev(c.get("severity", "info"))["priority"] == 1)
    low_count = sum(1 for c in comments if _sev(c.get("severity", "info"))["priority"] == 2)

    stats_parts = []
    if high_count:
        stats_parts.append(f"\u26d4 {high_count} error(s)")
    if med_count:
        stats_parts.append(f"\u26a0\ufe0f {med_count} warning(s)")
    if low_count:
        stats_parts.append(f"\U0001f4a1 {low_count} suggestion(s)")

    parts.append(f"### Findings ({len(comments)})")
    parts.append(" &middot; ".join(stats_parts))
    parts.append("")

    # ── Sort by severity (errors first) then by line number ──
    sorted_comments = sorted(
        comments,
        key=lambda c: (
            _sev(c.get("severity", "info"))["priority"],
            c.get("line", 0),
        ),
    )

    # ── Individual findings ──
    for c in sorted_comments:
        parts.append("---")
        parts.append("")
        parts.append(_format_single_finding(c))

    parts.append("---")
    parts.append("")
    parts.append(
        "<sub>Generated by **PR Review Bot** "
        "&mdash; AI + static analysis</sub>"
    )

    return "\n".join(parts)


# ─── GitHub API ──────────────────────────────────────────────────────

async def post_review_comment(
    repo_full_name: str,
    pr_number: int,
    comments: list,
    summary: str,
    score: int,
    commit_sha: str = "",
) -> bool:
    """Post a formatted review comment on a GitHub pull request."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("GITHUB_TOKEN not configured, skipping comment posting")
        return False

    body = format_review_body(comments, summary, score)

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "PR-Review-Bot",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = (
                f"https://api.github.com/repos/{repo_full_name}"
                f"/issues/{pr_number}/comments"
            )
            response = await client.post(url, headers=headers, json={"body": body})

            if response.status_code in (200, 201):
                logger.info(
                    f"Posted review on {repo_full_name}#{pr_number} "
                    f"({len(comments)} findings)"
                )
                return True

            logger.error(
                f"GitHub API {response.status_code}: {response.text[:200]}"
            )
            return False

    except Exception as e:
        logger.error(f"Failed to post review: {e}")
        return False
