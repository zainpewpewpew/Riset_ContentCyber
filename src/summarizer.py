import logging
import os

import requests

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """Kamu adalah ahli cyber security yang menjelaskan berita ke orang awam.
Tugasmu: buat ringkasan berita cyber security dalam Bahasa Indonesia yang mudah dipahami.

Aturan:
- Maksimal 3-4 kalimat
- Gunakan bahasa yang sederhana, hindari jargon teknis
- Jika ada istilah teknis, jelaskan singkat dalam kurung
- Sertakan dampak/pentingnya berita ini bagi pengguna biasa
- Jangan gunakan emoji"""


def _get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    return key


def summarize_article(title: str, content: str, source: str) -> str:
    """Summarize an article using OpenAI ChatGPT API.

    Returns the AI-generated summary, or falls back to truncated content on error.
    """
    try:
        api_key = _get_api_key()
    except ValueError:
        logger.warning("OPENAI_API_KEY not set, using raw content as summary")
        return _fallback_summary(content)

    user_prompt = (
        f"Judul: {title}\n"
        f"Sumber: {source}\n"
        f"Konten:\n{content[:3000]}"
    )

    try:
        response = requests.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 300,
                "temperature": 0.5,
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        summary = data["choices"][0]["message"]["content"].strip()
        logger.info("Summarized: %s", title[:60])
        return summary

    except Exception as e:
        logger.error("Failed to summarize '%s': %s", title[:60], e)
        return _fallback_summary(content)


def _fallback_summary(content: str) -> str:
    """Truncate content as fallback when AI summarization fails."""
    if len(content) > 500:
        return content[:500].rsplit(" ", 1)[0] + "..."
    return content
