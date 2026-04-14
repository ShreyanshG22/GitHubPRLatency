import os
import logging
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software engineer performing a code review on a pull request.
Analyze the provided code diff for:
1. Performance issues (inefficient algorithms, unnecessary computations, memory leaks)
2. Security vulnerabilities (SQL injection, XSS, hardcoded secrets)
3. Code quality (readability, naming conventions, code duplication)
4. Bug risks (null references, off-by-one errors, race conditions)
5. Best practices violations

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
- Be specific and actionable in your comments
- If the diff is clean, return high score with minimal comments
- Focus on the most impactful issues first"""


async def analyze_diff(diff_content: str, pr_title: str, pr_author: str) -> dict:
    """Analyze a PR diff using OpenAI GPT-5.2 via Emergent integration."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        logger.error("EMERGENT_LLM_KEY not configured")
        return {
            "summary": "Analysis unavailable - LLM key not configured",
            "score": 0,
            "comments": []
        }

    # Truncate diff if too long (token limits)
    max_diff_length = 12000
    truncated = False
    if len(diff_content) > max_diff_length:
        diff_content = diff_content[:max_diff_length]
        truncated = True

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"pr-review-{uuid.uuid4()}",
            system_message=SYSTEM_PROMPT
        ).with_model("openai", "gpt-5.2")

        prompt = f"PR Title: {pr_title}\nAuthor: {pr_author}\n"
        if truncated:
            prompt += "(Note: Diff was truncated due to size)\n"
        prompt += f"\n--- DIFF ---\n{diff_content}\n--- END DIFF ---"

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        # Parse the JSON response
        import json
        # Clean response - remove possible markdown fences
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
