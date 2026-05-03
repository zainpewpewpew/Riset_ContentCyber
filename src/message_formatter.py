import logging

logger = logging.getLogger(__name__)


def format_article(article: dict) -> str:
    """Format a single article into a WhatsApp message caption.

    Uses WhatsApp text formatting:
    *bold* for title, _italic_ for metadata.
    """
    lines = []

    lines.append("*[Yakes Telkom - Cyber Security Alert]*")
    lines.append("")

    # Title (bold)
    lines.append(f"*{article['title']}*")
    lines.append("")

    # Source
    lines.append(f"_Sumber:_ {article['source']}")

    # Date
    if article.get("published"):
        lines.append(f"_Tanggal:_ {article['published']}")

    # Tags/Categories
    if article.get("tags"):
        tags_str = ", ".join(article["tags"][:8])
        lines.append(f"_Kategori:_ {tags_str}")

    lines.append("")

    # Summary
    if article.get("summary"):
        lines.append(article["summary"])
        lines.append("")

    # Link
    lines.append(f"Baca selengkapnya:\n{article['link']}")

    return "\n".join(lines)


def format_batch_summary(articles: list[dict]) -> str:
    """Format a summary when multiple articles are sent at once."""
    count = len(articles)
    sources = set(a["source"] for a in articles)
    return (
        f"*[Yakes Telkom - Cyber Security Update]*\n\n"
        f"Ditemukan *{count}* berita cyber security terbaru dari "
        f"{', '.join(sources)}.\n\n"
        f"Berikut ringkasan yang relevan untuk Yakes Telkom:"
    )


def format_no_news() -> str:
    """Format message when no new articles are found in the last week."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%d %B %Y")

    return (
        f"*[Yakes Telkom - Cyber Security Update]*\n\n"
        f"_Tanggal:_ {today}\n\n"
        f"Tidak ditemukan berita cyber security baru dalam 7 hari terakhir.\n\n"
        f"Ini bisa berarti situasi keamanan siber relatif stabil. "
        f"Namun tetap waspada dan pastikan sistem Yakes Telkom selalu "
        f"ter-update dengan patch keamanan terbaru."
    )
