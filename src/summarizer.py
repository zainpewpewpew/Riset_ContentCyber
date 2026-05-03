import logging
import os

import requests

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """Kamu adalah ahli cyber security yang membuat ringkasan berita untuk tim IT Yakes Telkom (Yayasan Kesehatan Telkom), sebuah perusahaan kesehatan di bawah Telkom Indonesia.

Tugasmu: buat ringkasan berita cyber security dalam Bahasa Indonesia yang mudah dipahami, dan jelaskan mengapa berita ini relevan untuk Yakes Telkom.

Konteks Yakes Telkom:
- Perusahaan di industri kesehatan (healthcare)
- Bagian dari ekosistem Telkom Indonesia (telekomunikasi)
- Mengelola data pasien dan rekam medis (data sensitif)
- Menggunakan sistem informasi kesehatan dan infrastruktur IT

Aturan:
- Maksimal 4-5 kalimat
- Gunakan bahasa yang sederhana, hindari jargon teknis
- Jika ada istilah teknis, jelaskan singkat dalam kurung
- Selalu akhiri dengan 1 kalimat tentang relevansi/dampak untuk Yakes Telkom atau industri kesehatan
- Jangan gunakan emoji"""


def _get_api_keys() -> list[str]:
    """Collect all available API keys.

    Supports two formats:
    1. Multiple keys in OPENAI_API_KEY (one per line)
    2. Additional keys in OPENAI_API_KEY_2, OPENAI_API_KEY_3, etc.
    """
    keys = []

    primary = os.environ.get("OPENAI_API_KEY", "").strip()
    if primary:
        for line in primary.splitlines():
            key = line.strip()
            if key and key.startswith("sk-"):
                keys.append(key)

    for i in range(2, 10):
        key = os.environ.get(f"OPENAI_API_KEY_{i}", "").strip()
        if key and key.startswith("sk-"):
            keys.append(key)

    return keys


def _call_openai(api_key: str, user_prompt: str) -> str:
    """Make a single OpenAI API call. Raises on failure."""
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
    return data["choices"][0]["message"]["content"].strip()


def summarize_article(title: str, content: str, source: str) -> str:
    """Summarize an article using OpenAI ChatGPT API.

    Tries multiple API keys in sequence. If key 1 fails (rate limit,
    quota exceeded, etc.), automatically tries key 2, then key 3, etc.
    Falls back to truncated content if all keys fail.
    """
    api_keys = _get_api_keys()

    if not api_keys:
        logger.warning("No OPENAI_API_KEY set, using raw content as summary")
        return _fallback_summary(content)

    user_prompt = (
        f"Judul: {title}\n"
        f"Sumber: {source}\n"
        f"Konten:\n{content[:3000]}"
    )

    for i, key in enumerate(api_keys, start=1):
        try:
            summary = _call_openai(key, user_prompt)
            logger.info("Summarized with key #%d: %s", i, title[:60])
            return summary

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            logger.warning(
                "Key #%d failed (HTTP %s) for '%s': %s",
                i, status, title[:60], e,
            )
            if i < len(api_keys):
                logger.info("Trying next API key (#%d)...", i + 1)
            continue

        except Exception as e:
            logger.warning("Key #%d error for '%s': %s", i, title[:60], e)
            if i < len(api_keys):
                logger.info("Trying next API key (#%d)...", i + 1)
            continue

    logger.error("All %d API keys failed for '%s', using fallback", len(api_keys), title[:60])
    return _fallback_summary(content)


def _fallback_summary(content: str) -> str:
    """Truncate content as fallback when AI summarization fails."""
    if len(content) > 500:
        return content[:500].rsplit(" ", 1)[0] + "..."
    return content
