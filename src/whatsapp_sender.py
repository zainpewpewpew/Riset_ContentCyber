import logging
import os
import re
import time

from whatsapp_api_client_python import API

logger = logging.getLogger(__name__)

SEND_DELAY_SECONDS = 3
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 5


def _create_client() -> API.GreenAPI:
    instance_id = os.environ.get("GREEN_API_INSTANCE_ID", "").strip()
    api_token = os.environ.get("GREEN_API_TOKEN", "").strip()

    if not instance_id or not api_token:
        raise ValueError(
            "GREEN_API_INSTANCE_ID and GREEN_API_TOKEN environment variables are required"
        )

    return API.GreenAPI(instance_id, api_token)


def _get_recipients() -> list[str]:
    """Parse WA_RECIPIENTS env var (newline-separated chat IDs)."""
    raw = os.environ.get("WA_RECIPIENTS", "")
    recipients = []

    for line in raw.strip().splitlines():
        chat_id = line.strip()
        if not chat_id:
            continue

        if not re.match(r"^[\d]+@(c|g|s)\.us$", chat_id):
            logger.warning("Invalid chat ID format, skipping: %s", chat_id)
            continue

        recipients.append(chat_id)

    if not recipients:
        raise ValueError(
            "WA_RECIPIENTS has no valid chat IDs. "
            "Format: 6281234567890@c.us (personal) or 120363xxx@g.us (group)"
        )

    logger.info("Loaded %d recipients", len(recipients))
    return recipients


def _validate_image_url(url: str) -> bool:
    """Basic validation that URL looks like a valid image URL."""
    if not url or not isinstance(url, str):
        return False
    if not url.startswith("http"):
        return False
    if len(url) > 2000:
        return False
    return True


def send_image_message(
    client: API.GreenAPI,
    chat_id: str,
    image_url: str,
    caption: str,
    filename: str = "news.jpg",
) -> bool:
    """Send an image with caption to a chat, with retry on failure."""
    if not _validate_image_url(image_url):
        logger.warning("Invalid image URL for %s, falling back to text", chat_id)
        return send_text_message(client, chat_id, caption)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.sending.sendFileByUrl(
                chat_id, image_url, filename, caption
            )
            if response.code == 200:
                logger.info("Image message sent to %s", chat_id)
                return True
            else:
                logger.error(
                    "Failed to send image to %s (attempt %d/%d): %s",
                    chat_id, attempt, MAX_RETRIES, response.data,
                )
        except Exception as e:
            logger.error(
                "Error sending image to %s (attempt %d/%d): %s",
                chat_id, attempt, MAX_RETRIES, e,
            )

        if attempt < MAX_RETRIES:
            logger.info("Retrying in %ds...", RETRY_DELAY_SECONDS)
            time.sleep(RETRY_DELAY_SECONDS)

    logger.warning("Image send failed after %d attempts, falling back to text", MAX_RETRIES)
    return send_text_message(client, chat_id, caption)


def send_text_message(
    client: API.GreenAPI,
    chat_id: str,
    text: str,
) -> bool:
    """Send a text message to a chat, with retry on failure."""
    if not text or not text.strip():
        logger.warning("Empty text message for %s, skipping", chat_id)
        return False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.sending.sendMessage(chat_id, text)
            if response.code == 200:
                logger.info("Text message sent to %s", chat_id)
                return True
            else:
                logger.error(
                    "Failed to send text to %s (attempt %d/%d): %s",
                    chat_id, attempt, MAX_RETRIES, response.data,
                )
        except Exception as e:
            logger.error(
                "Error sending text to %s (attempt %d/%d): %s",
                chat_id, attempt, MAX_RETRIES, e,
            )

        if attempt < MAX_RETRIES:
            logger.info("Retrying in %ds...", RETRY_DELAY_SECONDS)
            time.sleep(RETRY_DELAY_SECONDS)

    return False


def send_article(client: API.GreenAPI, chat_id: str, article: dict, caption: str) -> bool:
    """Send an article to a single recipient (image+caption or text fallback)."""
    thumbnail = article.get("thumbnail")

    if thumbnail and _validate_image_url(thumbnail):
        return send_image_message(client, chat_id, thumbnail, caption)
    else:
        return send_text_message(client, chat_id, caption)


def send_text_to_all(text: str) -> None:
    """Send a plain text message to all recipients."""
    try:
        client = _create_client()
        recipients = _get_recipients()
    except ValueError as e:
        logger.error("Cannot send text to all: %s", e)
        return

    for recipient in recipients:
        send_text_message(client, recipient, text)
        time.sleep(SEND_DELAY_SECONDS)


def send_to_all_recipients(articles: list[dict], captions: list[str]) -> dict:
    """Send all articles to all recipients.

    Returns a dict with counts: {"sent": N, "failed": N}
    """
    try:
        client = _create_client()
        recipients = _get_recipients()
    except ValueError as e:
        logger.error("Cannot send articles: %s", e)
        return {"sent": 0, "failed": len(articles)}

    stats = {"sent": 0, "failed": 0}

    for article, caption in zip(articles, captions):
        for recipient in recipients:
            success = send_article(client, recipient, article, caption)
            if success:
                stats["sent"] += 1
            else:
                stats["failed"] += 1

            time.sleep(SEND_DELAY_SECONDS)

    logger.info("Send complete: %d sent, %d failed", stats["sent"], stats["failed"])
    return stats
