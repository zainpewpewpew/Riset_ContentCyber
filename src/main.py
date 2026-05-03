import logging
import sys
from datetime import datetime, timezone

from feed_fetcher import fetch_all_feeds, filter_by_date, filter_by_topic
from message_formatter import (
    format_article,
    format_batch_summary,
    format_no_news,
    format_error_report,
)
from state_manager import filter_new_articles, load_sent_articles, save_sent_articles
from summarizer import summarize_article
from whatsapp_sender import send_to_all_recipients, send_text_to_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_RUN = 3


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

    # --- STEP 4: Limit articles per run ---
    if len(new_articles) > MAX_ARTICLES_PER_RUN:
        logger.info(
            "Limiting from %d to %d articles per run",
            len(new_articles), MAX_ARTICLES_PER_RUN,
        )
        new_articles = new_articles[:MAX_ARTICLES_PER_RUN]

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

    # --- STEP 6: Format captions ---
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

    # --- STEP 7: Send batch summary ---
    if len(new_articles) > 1:
        try:
            summary = format_batch_summary(new_articles)
            send_text_to_all(summary)
        except Exception as e:
            logger.error("Failed to send batch summary: %s", e)

    # --- STEP 8: Send articles ---
    try:
        stats = send_to_all_recipients(new_articles, captions)
    except Exception as e:
        logger.critical("Fatal error sending articles: %s", e)
        errors.append(f"Gagal mengirim artikel ke WhatsApp: {e}")
        stats = {"sent": 0, "failed": len(new_articles)}

    # --- STEP 9: Save state ---
    try:
        for article in new_articles:
            sent_urls.add(article["link"])
        save_sent_articles(sent_urls)
    except Exception as e:
        logger.error("Failed to save sent articles state: %s", e)
        errors.append(f"Gagal menyimpan state: {e}")

    # --- STEP 10: Send error report if any issues ---
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
