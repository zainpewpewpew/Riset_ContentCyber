import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

WA_MAX_CAPTION_LENGTH = 4096


def _truncate(text: str, max_length: int = WA_MAX_CAPTION_LENGTH) -> str:
    """Truncate text to max length at word boundary."""
    if len(text) <= max_length:
        return text
    truncated = text[: max_length - 50].rsplit("\n", 1)[0]
    return truncated + "\n\n_(pesan dipotong karena terlalu panjang)_"


def _safe_str(value, default: str = "N/A") -> str:
    """Safely convert value to string, handling None and encoding issues."""
    if value is None:
        return default
    try:
        return str(value).strip() or default
    except Exception:
        return default


def format_article(article: dict) -> str:
    """Format a single article into a WhatsApp message caption."""
    lines = []

    lines.append("*[Yakes Telkom - Cyber Security Alert]*")
    lines.append("")

    title = _safe_str(article.get("title"), "Judul tidak tersedia")
    lines.append(f"*{title}*")
    lines.append("")

    lines.append(f"_Sumber:_ {_safe_str(article.get('source'))}")

    if article.get("published"):
        lines.append(f"_Tanggal:_ {_safe_str(article.get('published'))}")

    tags = article.get("tags")
    if tags and isinstance(tags, list) and len(tags) > 0:
        clean_tags = [_safe_str(t) for t in tags[:8] if _safe_str(t) != "N/A"]
        if clean_tags:
            lines.append(f"_Kategori:_ {', '.join(clean_tags)}")

    lines.append("")

    summary = _safe_str(article.get("summary"), "")
    if summary:
        lines.append(summary)
        lines.append("")

    link = _safe_str(article.get("link"), "")
    if link and link != "N/A":
        lines.append(f"Baca selengkapnya:\n{link}")

    result = "\n".join(lines)
    return _truncate(result)


def format_batch_summary(articles: list[dict]) -> str:
    """Format a summary when multiple articles are sent at once."""
    count = len(articles)
    sources = set()
    for a in articles:
        src = _safe_str(a.get("source"), "")
        if src and src != "N/A":
            sources.add(src)

    sources_str = ", ".join(sources) if sources else "berbagai sumber"

    return (
        f"*[Yakes Telkom - Cyber Security Update]*\n\n"
        f"Ditemukan *{count}* berita cyber security terbaru dari "
        f"{sources_str}.\n\n"
        f"Berikut ringkasan yang relevan untuk Yakes Telkom:"
    )


def format_no_news() -> str:
    """Format message when no new articles are found in the last week."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y")

    return (
        f"*[Yakes Telkom - Cyber Security Update]*\n\n"
        f"_Tanggal:_ {today}\n\n"
        f"Tidak ditemukan berita cyber security baru dalam 7 hari terakhir.\n\n"
        f"Ini bisa berarti situasi keamanan siber relatif stabil. "
        f"Namun tetap waspada dan pastikan sistem Yakes Telkom selalu "
        f"ter-update dengan patch keamanan terbaru."
    )


def format_error_report(errors: list[str]) -> str:
    """Format error report message to notify about issues."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    lines = [
        "*[Yakes Telkom - Bot Status Report]*",
        "",
        f"_Tanggal:_ {today}",
        "",
        f"Ditemukan *{len(errors)}* masalah saat menjalankan bot:",
        "",
    ]

    for i, error in enumerate(errors, 1):
        clean_error = _safe_str(error)
        if len(clean_error) > 200:
            clean_error = clean_error[:200] + "..."
        lines.append(f"{i}. {clean_error}")

    lines.append("")
    lines.append("_Harap hubungi tim IT untuk investigasi lebih lanjut._")

    return "\n".join(lines)
