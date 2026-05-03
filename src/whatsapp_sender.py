import logging
import os
import time

from whatsapp_api_client_python import API

logger = logging.getLogger(__name__)

SEND_DELAY_SECONDS = 3


def _create_client() -> API.GreenAPI:
    instance_id = os.environ.get("GREEN_API_INSTANCE_ID", "")
    api_token = os.environ.get("GREEN_API_TOKEN", "")

    if not instance_id or not api_token:
        raise ValueError(
            "GREEN_API_INSTANCE_ID and GREEN_API_TOKEN environment variables are required"
        )

    return API.GreenAPI(instance_id, api_token)


def _get_recipients() -> list[str]:
    """Parse WA_RECIPIENTS env var (newline-separated chat IDs)."""
    raw = os.environ.get("WA_RECIPIENTS", "")
    recipients = [
        line.strip()
        for line in raw.strip().splitlines()
        if line.strip()
    ]

    if not recipients:
        raise ValueError(
            "WA_RECIPIENTS environment variable is empty. "
            "Set it with newline-separated chat IDs (e.g. 6281234567890@c.us)"
        )

    return recipients


def send_image_message(
    client: API.GreenAPI,
    chat_id: str,
    image_url: str,
    caption: str,
    filename: str = "news.jpg",
) -> bool:
    """Send an image with caption to a chat."""
    try:
        response = client.sending.sendFileByUrl(
            chat_id, image_url, filename, caption
        )
        if response.code == 200:
            logger.info("Image message sent to %s", chat_id)
            return True
        else:
            logger.error("Failed to send image to %s: %s", chat_id, response.data)
            return False
    except Exception as e:
        logger.error("Error sending image to %s: %s", chat_id, e)
        return False


def send_text_message(
    client: API.GreenAPI,
    chat_id: str,
    text: str,
) -> bool:
    """Send a text message to a chat."""
    try:
        response = client.sending.sendMessage(chat_id, text)
        if response.code == 200:
            logger.info("Text message sent to %s", chat_id)
            return True
        else:
            logger.error("Failed to send text to %s: %s", chat_id, response.data)
            return False
    except Exception as e:
        logger.error("Error sending text to %s: %s", chat_id, e)
        return False


def send_article(client: API.GreenAPI, chat_id: str, article: dict, caption: str) -> bool:
    """Send an article to a single recipient (image+caption or text fallback)."""
    thumbnail = article.get("thumbnail")

    if thumbnail:
        return send_image_message(client, chat_id, thumbnail, caption)
    else:
        return send_text_message(client, chat_id, caption)


def send_text_to_all(text: str) -> None:
    """Send a plain text message to all recipients."""
    client = _create_client()
    recipients = _get_recipients()

    for recipient in recipients:
        send_text_message(client, recipient, text)
        time.sleep(SEND_DELAY_SECONDS)


def send_to_all_recipients(articles: list[dict], captions: list[str]) -> dict:
    """Send all articles to all recipients.

    Returns a dict with counts: {"sent": N, "failed": N}
    """
    client = _create_client()
    recipients = _get_recipients()

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
