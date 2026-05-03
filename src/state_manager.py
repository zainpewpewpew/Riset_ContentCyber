import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).parent.parent / "data" / "sent_articles.json"
MAX_HISTORY = 1000


def load_sent_articles(state_path: Path = STATE_PATH) -> set[str]:
    """Load the set of already-sent article URLs.

    Handles corrupted/invalid state files gracefully.
    """
    if not state_path.exists():
        logger.info("State file not found, starting fresh")
        return set()

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.warning("State file has unexpected format (not a list), resetting")
            _backup_state(state_path)
            return set()

        valid_urls = set()
        for item in data:
            if isinstance(item, str) and item.startswith("http"):
                valid_urls.add(item)

        logger.info("Loaded %d sent article URLs", len(valid_urls))
        return valid_urls

    except json.JSONDecodeError as e:
        logger.error("State file is corrupted: %s", e)
        _backup_state(state_path)
        return set()
    except Exception as e:
        logger.error("Unexpected error loading state: %s", e)
        return set()


def _backup_state(state_path: Path) -> None:
    """Backup corrupted state file before resetting."""
    try:
        backup_path = state_path.with_suffix(".json.bak")
        shutil.copy2(state_path, backup_path)
        logger.info("Corrupted state backed up to %s", backup_path)
    except Exception as e:
        logger.error("Failed to backup state: %s", e)


def save_sent_articles(sent: set[str], state_path: Path = STATE_PATH) -> None:
    """Save sent article URLs to JSON, keeping only the most recent entries."""
    sent_list = sorted(sent)
    if len(sent_list) > MAX_HISTORY:
        logger.info("Trimming history from %d to %d entries", len(sent_list), MAX_HISTORY)
        sent_list = sent_list[-MAX_HISTORY:]

    state_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = state_path.with_suffix(".json.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(sent_list, f, indent=2, ensure_ascii=False)

        temp_path.replace(state_path)
        logger.info("Saved %d sent article URLs", len(sent_list))
    except Exception as e:
        logger.error("Failed to save state: %s", e)
        if temp_path.exists():
            temp_path.unlink()
        raise


def filter_new_articles(articles: list[dict], sent: set[str]) -> list[dict]:
    """Filter out articles that have already been sent."""
    new_articles = [a for a in articles if a.get("link", "") not in sent]
    logger.info("Found %d new articles (out of %d total)", len(new_articles), len(articles))
    return new_articles
