import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).parent.parent / "data" / "sent_articles.json"
MAX_HISTORY = 1000


def load_sent_articles(state_path: Path = STATE_PATH) -> set[str]:
    """Load the set of already-sent article URLs."""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_sent_articles(sent: set[str], state_path: Path = STATE_PATH) -> None:
    """Save sent article URLs to JSON, keeping only the most recent entries."""
    sent_list = sorted(sent)
    if len(sent_list) > MAX_HISTORY:
        sent_list = sent_list[-MAX_HISTORY:]

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(sent_list, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d sent article URLs", len(sent_list))


def filter_new_articles(articles: list[dict], sent: set[str]) -> list[dict]:
    """Filter out articles that have already been sent."""
    new_articles = [a for a in articles if a["link"] not in sent]
    logger.info("Found %d new articles (out of %d total)", len(new_articles), len(articles))
    return new_articles
