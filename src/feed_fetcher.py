import logging
import re
from pathlib import Path
from typing import Optional

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "feeds.yaml"


def load_feeds_config(config_path: Path = CONFIG_PATH) -> list[dict]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("feeds", [])


def _extract_thumbnail(entry) -> Optional[str]:
    """Extract thumbnail image URL from an RSS feed entry."""

    # 1. media:thumbnail
    thumbnails = getattr(entry, "media_thumbnail", None)
    if thumbnails and len(thumbnails) > 0:
        return thumbnails[0].get("url")

    # 2. media:content with image type
    media_content = getattr(entry, "media_content", None)
    if media_content:
        for media in media_content:
            medium = media.get("medium", "")
            url = media.get("url", "")
            if medium == "image" or re.search(r"\.(jpg|jpeg|png|webp|gif)", url, re.I):
                return url

    # 3. enclosures with image type
    enclosures = getattr(entry, "enclosures", [])
    for enc in enclosures:
        enc_type = enc.get("type", "")
        enc_url = enc.get("href", enc.get("url", ""))
        if "image" in enc_type or re.search(r"\.(jpg|jpeg|png|webp|gif)", enc_url, re.I):
            return enc_url

    # 4. Parse HTML content/summary for <img> tags
    html_content = ""
    if hasattr(entry, "content") and entry.content:
        html_content = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        html_content = entry.summary or ""

    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            src = img["src"]
            if src.startswith("http"):
                return src

    return None


def _extract_tags(entry) -> list[str]:
    """Extract categories/tags from an RSS feed entry."""
    tags = []
    if hasattr(entry, "tags") and entry.tags:
        for tag in entry.tags:
            term = tag.get("term", "").strip()
            if term:
                tags.append(term)
    return tags


def _extract_summary(entry) -> str:
    """Extract and clean the summary text from an RSS feed entry."""
    html_content = ""
    if hasattr(entry, "summary") and entry.summary:
        html_content = entry.summary
    elif hasattr(entry, "content") and entry.content:
        html_content = entry.content[0].get("value", "")

    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # Truncate to ~500 chars at word boundary
    if len(text) > 500:
        text = text[:500].rsplit(" ", 1)[0] + "..."

    return text


def _parse_date(entry) -> Optional[str]:
    """Parse and format the published date."""
    date_str = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not date_str:
        return None
    try:
        dt = date_parser.parse(date_str)
        return dt.strftime("%d %B %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return date_str


def _parse_datetime(entry):
    """Parse the published date as a timezone-aware datetime object."""
    date_str = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not date_str:
        return None
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def fetch_feed(feed_config: dict) -> list[dict]:
    """Fetch and parse a single RSS feed, returning structured articles."""
    name = feed_config["name"]
    url = feed_config["url"]
    articles = []

    try:
        logger.info("Fetching feed: %s", name)
        response = requests.get(url, timeout=30, headers={
            "User-Agent": "CyberSecNewsBot/1.0"
        })
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        for entry in feed.entries:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", None)
            if not link or not title:
                continue

            article = {
                "title": title.strip(),
                "link": link.strip(),
                "source": name,
                "published": _parse_date(entry),
                "published_dt": _parse_datetime(entry),
                "summary": _extract_summary(entry),
                "thumbnail": _extract_thumbnail(entry),
                "tags": _extract_tags(entry),
            }
            articles.append(article)

        logger.info("Fetched %d articles from %s", len(articles), name)

    except Exception as e:
        logger.error("Failed to fetch feed %s: %s", name, e)

    return articles


def fetch_all_feeds(config_path: Path = CONFIG_PATH) -> list[dict]:
    """Fetch all configured RSS feeds and return combined articles."""
    feeds_config = load_feeds_config(config_path)
    all_articles = []

    for feed_config in feeds_config:
        articles = fetch_feed(feed_config)
        all_articles.extend(articles)

    logger.info("Total articles fetched: %d", len(all_articles))
    return all_articles


def filter_by_date(articles: list[dict], max_days: int = 7) -> list[dict]:
    """Filter articles from the last `max_days` days (default: 1 week).

    Articles without a parseable date are always included.
    Sorted from newest to oldest.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_days)

    result = []
    for article in articles:
        dt = article.get("published_dt")
        if dt is None or dt >= cutoff:
            result.append(article)

    logger.info("Found %d articles from last %d days", len(result), max_days)
    result.sort(key=lambda a: a.get("published_dt") or now, reverse=True)
    return result
