import logging
import sys

from feed_fetcher import fetch_all_feeds, filter_by_date
from message_formatter import format_article, format_batch_summary, format_no_news
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
    logger.info("=== Cyber Security News Bot started ===")

    # 1. Fetch all RSS feeds
    all_articles = fetch_all_feeds()

    # 2. Filter by date: last 7 days
    if all_articles:
        all_articles = filter_by_date(all_articles, max_days=7)

    # 3. Filter out already-sent articles
    sent_urls = load_sent_articles()
    new_articles = filter_new_articles(all_articles, sent_urls) if all_articles else []

    if not new_articles:
        logger.info("No new articles found in the last 7 days.")
        send_text_to_all(format_no_news())
        return

    # 4. Limit articles per run to avoid spam
    if len(new_articles) > MAX_ARTICLES_PER_RUN:
        logger.info(
            "Limiting from %d to %d articles per run",
            len(new_articles), MAX_ARTICLES_PER_RUN,
        )
        new_articles = new_articles[:MAX_ARTICLES_PER_RUN]

    # 5. Summarize articles with AI
    logger.info("Summarizing %d articles with ChatGPT...", len(new_articles))
    for article in new_articles:
        ai_summary = summarize_article(
            title=article["title"],
            content=article.get("summary", ""),
            source=article["source"],
        )
        article["summary"] = ai_summary

    # 6. Format captions
    captions = [format_article(article) for article in new_articles]

    logger.info("Sending %d new articles to WhatsApp...", len(new_articles))

    # 7. Send batch summary first (if multiple articles)
    if len(new_articles) > 1:
        summary = format_batch_summary(new_articles)
        send_text_to_all(summary)

    # 8. Send each article
    stats = send_to_all_recipients(new_articles, captions)

    # 9. Mark articles as sent (even if some sends failed, to avoid retry loops)
    for article in new_articles:
        sent_urls.add(article["link"])
    save_sent_articles(sent_urls)

    logger.info(
        "=== Bot finished: %d sent, %d failed ===",
        stats["sent"], stats["failed"],
    )

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
