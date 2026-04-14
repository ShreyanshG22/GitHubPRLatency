import os
import json
import logging
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage
from diff_parser import ParsedDiff, format_blocks_for_analysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software engineer performing a code review on a pull request.
The diff has been pre-parsed into structured code blocks with language tags and line numbers.
Each block is labeled [ADDED] (new code) or [MODIFIED] (changed existing code).

Analyze for:
1. Performance issues (inefficient algorithms, unnecessary computations, memory leaks)
2. Security vulnerabilities (SQL injection, XSS, hardcoded secrets)
3. Code quality (readability, naming conventions, code duplication)
4. Bug risks (null references, off-by-one errors, race conditions)
5. Best practices violations
6. Language-specific issues (Python: type hints, C++: memory management, RAII)

Respond in the following JSON format ONLY (no markdown, no code fences):
{
  "summary": "Brief overall assessment of the PR",
  "score": 75,
  "comments": [
    {
      "path": "filename.py",
      "line": 10,
      "body": "Specific issue description and suggestion",
      "severity": "warning"
    }
  ]
}

- score: 0-100 where 100 is perfect code
- severity: "info", "warning", or "error"
- Use the exact file paths and line numbers from the parsed blocks
- Be specific and actionable in your comments
- If the diff is clean, return high score with minimal comments
- Focus on the most impactful issues first"""


async def analyze_diff(diff_content: str, pr_title: str, pr_author: str,
                       parsed: ParsedDiff | None = None) -> dict:
    """Analyze a PR diff using OpenAI GPT-5.2 via Emergent integration.

    Args:
        diff_content: Raw diff string (used as fallback).
        pr_title: Pull request title.
        pr_author: Pull request author login.
        parsed: Pre-parsed diff. When provided the formatted blocks
                are sent instead of the raw diff, giving the LLM
                structured context with language tags and line numbers.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        logger.error("EMERGENT_LLM_KEY not configured")
        return {
            "summary": "Analysis unavailable - LLM key not configured",
            "score": 0,
            "comments": []
        }

    # Build analysis content — prefer structured blocks when available
    if parsed and parsed.file_count > 0:
        analysis_text = format_blocks_for_analysis(parsed)
        file_summary = (
            f"Files changed: {parsed.file_count} | "
            f"Code blocks: {parsed.total_blocks}"
        )
    else:
        analysis_text = diff_content
        file_summary = ""

    # Truncate if too long (token limits)
    max_length = 12000
    truncated = False
    if len(analysis_text) > max_length:
        analysis_text = analysis_text[:max_length]
        truncated = True

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"pr-review-{uuid.uuid4()}",
            system_message=SYSTEM_PROMPT
        ).with_model("openai", "gpt-5.2")

        prompt = f"PR Title: {pr_title}\nAuthor: {pr_author}\n"
        if file_summary:
            prompt += f"{file_summary}\n"
        if truncated:
            prompt += "(Note: Content was truncated due to size)\n"
        prompt += f"\n--- CODE CHANGES ---\n{analysis_text}\n--- END ---"

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        # Clean and parse JSON response
        clean_response = response.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.split("\n", 1)[1]
        if clean_response.endswith("```"):
            clean_response = clean_response.rsplit("```", 1)[0]
        clean_response = clean_response.strip()

        result = json.loads(clean_response)
        return {
            "summary": result.get("summary", "No summary provided"),
            "score": min(100, max(0, int(result.get("score", 50)))),
            "comments": result.get("comments", [])
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return {
            "summary": f"Analysis completed but response parsing failed. Raw: {response[:200] if response else 'empty'}",
            "score": 50,
            "comments": []
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return {
            "summary": f"Analysis failed: {str(e)}",
            "score": 0,
            "comments": []
        }
