import logging
import sys
import tempfile
from datetime import datetime, timezone

from feed_fetcher import fetch_all_feeds, filter_by_date, filter_by_topic
from message_formatter import (
    format_article,
    format_batch_summary,
    format_no_news,
    format_error_report,
)
from poster_generator import generate_poster, cleanup_posters
from state_manager import filter_new_articles, load_sent_articles, save_sent_articles
from summarizer import summarize_article
from whatsapp_sender import send_to_all_recipients, send_text_to_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_RUN = 1
MAX_ARTICLES_PER_DAY = 3


def _get_today_send_count() -> tuple[int, str]:
    """Check how many articles have been sent today using a temp marker file."""
    from pathlib import Path
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    marker = Path(tempfile.gettempdir()) / "cybersec_daily_count.txt"

    try:
        if marker.exists():
            data = marker.read_text().strip().split("\n")
            if data and data[0] == today_str:
                return len(data) - 1, today_str
    except Exception:
        pass

    return 0, today_str


def _record_today_send(source: str) -> None:
    """Record that we sent an article today."""
    from pathlib import Path
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    marker = Path(tempfile.gettempdir()) / "cybersec_daily_count.txt"

    try:
        lines = []
        if marker.exists():
            lines = marker.read_text().strip().split("\n")
            if not lines or lines[0] != today_str:
                lines = [today_str]
        else:
            lines = [today_str]
        lines.append(source)
        marker.write_text("\n".join(lines))
    except Exception:
        pass


def _pick_diverse_article(articles: list[dict], sent_urls: set[str]) -> list[dict]:
    """Pick 1 article from a source that hasn't been used today yet.

    Ensures each of the 3 daily sends comes from a different source.
    """
    from pathlib import Path
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    marker = Path(tempfile.gettempdir()) / "cybersec_daily_count.txt"

    today_sources = set()
    send_count = 0
    try:
        if marker.exists():
            lines = marker.read_text().strip().split("\n")
            if lines and lines[0] == today_str:
                today_sources = set(lines[1:])
                send_count = len(today_sources)
    except Exception:
        pass

    if send_count >= MAX_ARTICLES_PER_DAY:
        logger.info("Already sent %d articles today (max %d), skipping", send_count, MAX_ARTICLES_PER_DAY)
        return []

    for article in articles:
        source = article.get("source", "")
        if source not in today_sources:
            logger.info("Selected article from '%s' (today: %d/%d sent)", source, send_count + 1, MAX_ARTICLES_PER_DAY)
            return [article]

    if articles:
        logger.info("All sources used today, picking newest article")
        return [articles[0]]

    return []


def main():
    start_time = datetime.now(timezone.utc)
    logger.info("=== Cyber Security News Bot started ===")

    errors = []

    # --- STEP 1: Fetch RSS feeds ---
    try:
        all_articles = fetch_all_feeds()
    except Exception as e:
        logger.critical("Fatal error fetching feeds: %s", e)
        errors.append(f"Gagal mengambil RSS feed: {e}")
        all_articles = []

    # Edge case: all feeds failed
    if not all_articles:
        logger.warning("No articles fetched from any feed.")
        errors.append("Tidak ada artikel yang berhasil diambil dari semua sumber RSS.")

    # --- STEP 2: Filter by date (last 7 days) ---
    if all_articles:
        try:
            all_articles = filter_by_date(all_articles, max_days=7)
        except Exception as e:
            logger.error("Error filtering by date: %s", e)
            errors.append(f"Gagal filter artikel berdasarkan tanggal: {e}")

    # --- STEP 2b: Filter by topic (vulnerability/server/website) ---
    if all_articles:
        try:
            all_articles = filter_by_topic(all_articles)
        except Exception as e:
            logger.error("Error filtering by topic: %s", e)
            errors.append(f"Gagal filter artikel berdasarkan topik: {e}")

    # --- STEP 3: Filter already-sent articles ---
    try:
        sent_urls = load_sent_articles()
    except Exception as e:
        logger.error("Error loading sent articles state: %s", e)
        errors.append(f"Gagal membaca state artikel terkirim: {e}")
        sent_urls = set()

    new_articles = filter_new_articles(all_articles, sent_urls) if all_articles else []

    # --- NEGATIVE CASE: No new articles found ---
    if not new_articles:
        logger.info("No new articles found in the last 7 days.")
        try:
            if errors:
                send_text_to_all(format_error_report(errors))
            else:
                send_text_to_all(format_no_news())
        except Exception as e:
            logger.error("Failed to send 'no news' notification: %s", e)
        return

    # --- STEP 4: Pick 1 article, rotating sources ---
    new_articles = _pick_diverse_article(new_articles, sent_urls)

    if not new_articles:
        logger.info("Daily limit reached or no suitable article. Exiting.")
        return

    # --- STEP 5: Summarize with AI ---
    logger.info("Summarizing %d articles with ChatGPT...", len(new_articles))
    summarize_errors = 0
    for article in new_articles:
        try:
            ai_summary = summarize_article(
                title=article["title"],
                content=article.get("summary", ""),
                source=article["source"],
            )
            article["summary"] = ai_summary
        except Exception as e:
            logger.error("Unexpected error summarizing '%s': %s", article["title"][:50], e)
            summarize_errors += 1

    if summarize_errors > 0:
        errors.append(f"Gagal summarize {summarize_errors} dari {len(new_articles)} artikel.")

    # --- STEP 6: Generate posters ---
    logger.info("Generating posters for %d articles...", len(new_articles))
    poster_errors = 0
    for article in new_articles:
        try:
            poster_path = generate_poster(article)
            if poster_path:
                article["poster_path"] = str(poster_path)
            else:
                poster_errors += 1
        except Exception as e:
            logger.error("Error generating poster for '%s': %s", article["title"][:50], e)
            poster_errors += 1

    if poster_errors > 0:
        logger.warning("%d posters failed to generate", poster_errors)

    # --- STEP 7: Format captions ---
    captions = []
    for article in new_articles:
        try:
            captions.append(format_article(article))
        except Exception as e:
            logger.error("Error formatting article '%s': %s", article["title"][:50], e)
            captions.append(f"*{article.get('title', 'Unknown')}*\n\n{article.get('link', '')}")

    # Edge case: verify captions match articles
    if len(captions) != len(new_articles):
        logger.error("Caption count mismatch: %d captions vs %d articles", len(captions), len(new_articles))
        min_len = min(len(captions), len(new_articles))
        new_articles = new_articles[:min_len]
        captions = captions[:min_len]

    logger.info("Sending %d new articles to WhatsApp...", len(new_articles))

    # --- STEP 8: Send batch summary ---
    if len(new_articles) > 1:
        try:
            summary = format_batch_summary(new_articles)
            send_text_to_all(summary)
        except Exception as e:
            logger.error("Failed to send batch summary: %s", e)

    # --- STEP 9: Send articles ---
    try:
        stats = send_to_all_recipients(new_articles, captions)
    except Exception as e:
        logger.critical("Fatal error sending articles: %s", e)
        errors.append(f"Gagal mengirim artikel ke WhatsApp: {e}")
        stats = {"sent": 0, "failed": len(new_articles)}

    # --- STEP 10: Save state + record daily send ---
    try:
        for article in new_articles:
            sent_urls.add(article["link"])
            if stats["sent"] > 0:
                _record_today_send(article.get("source", "unknown"))
        save_sent_articles(sent_urls)
    except Exception as e:
        logger.error("Failed to save sent articles state: %s", e)
        errors.append(f"Gagal menyimpan state: {e}")

    # --- STEP 11: Cleanup poster files ---
    try:
        cleanup_posters()
    except Exception as e:
        logger.error("Failed to cleanup posters: %s", e)

    # --- STEP 12: Send error report if any issues ---
    if errors:
        try:
            send_text_to_all(format_error_report(errors))
        except Exception as e:
            logger.error("Failed to send error report: %s", e)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "=== Bot finished in %.1fs: %d sent, %d failed, %d errors ===",
        elapsed, stats["sent"], stats["failed"], len(errors),
    )

    if stats["failed"] > 0 or errors:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical("Unhandled exception: %s", e, exc_info=True)
        try:
            send_text_to_all(format_error_report([f"Bot crash: {e}"]))
        except Exception:
            pass
        sys.exit(2)
