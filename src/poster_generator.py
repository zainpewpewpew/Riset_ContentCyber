import logging
import os
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

POSTER_WIDTH = 800
POSTER_HEIGHT = 420
POSTER_DIR = Path(tempfile.gettempdir()) / "cybersec_posters"

BRAND_COLOR = (0, 200, 150)
WHITE = (255, 255, 255)
LIGHT_GRAY = (180, 180, 180)
DARK_BG = (15, 15, 25)
OVERLAY_COLOR = (0, 0, 0, 180)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font, trying common paths on Ubuntu and Windows."""
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold
        else "C:/Windows/Fonts/arial.ttf",
    ]

    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    return ImageFont.load_default()


def download_thumbnail(url: str) -> Optional[Path]:
    """Download a thumbnail image from URL to a temp file."""
    if not url or not url.startswith("http"):
        return None

    POSTER_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, timeout=15, headers={
            "User-Agent": "CyberSecNewsBot/1.0"
        })
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "image" not in content_type and not url.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp", ".gif")
        ):
            logger.warning("URL does not appear to be an image: %s", url[:100])
            return None

        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".webp" in url.lower():
            ext = ".webp"

        tmp_file = POSTER_DIR / f"thumb_{hash(url) & 0xFFFFFFFF}{ext}"
        tmp_file.write_bytes(response.content)

        img = Image.open(tmp_file)
        if img.size[0] < 50 or img.size[1] < 50:
            logger.warning("Thumbnail too small (%dx%d), skipping", *img.size)
            tmp_file.unlink(missing_ok=True)
            return None

        logger.info("Downloaded thumbnail: %dx%d from %s", img.width, img.height, url[:80])
        return tmp_file

    except Exception as e:
        logger.error("Failed to download thumbnail: %s", e)
        return None


def _resize_and_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize image to cover target size, then center-crop."""
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        new_h = target_h
        new_w = int(target_h * img_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _draw_text_wrapped(draw, text, x, y, max_width, font, fill, max_lines=3):
    """Draw wrapped text and return the y position after the last line."""
    avg_char_width = font.getlength("A")
    chars_per_line = max(1, int(max_width / avg_char_width))

    lines = textwrap.wrap(text, width=chars_per_line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:chars_per_line - 3] + "..."

    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = font.getbbox(line)
        line_height = bbox[3] - bbox[1] + 6
        y += line_height

    return y


def create_overlay_poster(thumb_path: Path, article: dict) -> Optional[Path]:
    """Create poster by overlaying branding on top of downloaded thumbnail."""
    try:
        img = Image.open(thumb_path).convert("RGBA")
        img = _resize_and_crop(img, POSTER_WIDTH, POSTER_HEIGHT)

        img = img.filter(ImageFilter.GaussianBlur(radius=1))

        overlay = Image.new("RGBA", (POSTER_WIDTH, POSTER_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Bottom overlay (gradient-like)
        draw.rectangle(
            [(0, POSTER_HEIGHT // 3), (POSTER_WIDTH, POSTER_HEIGHT)],
            fill=OVERLAY_COLOR,
        )
        # Top bar
        draw.rectangle(
            [(0, 0), (POSTER_WIDTH, 52)],
            fill=(0, 0, 0, 200),
        )

        font_brand = _get_font(18, bold=True)
        font_title = _get_font(24, bold=True)
        font_meta = _get_font(14, bold=False)

        draw.text((20, 16), "[CyberSecurity Terbaru]", font=font_brand, fill=BRAND_COLOR)

        title = article.get("title", "")
        y = POSTER_HEIGHT // 3 + 20
        y = _draw_text_wrapped(draw, title, 20, y, POSTER_WIDTH - 40, font_title, WHITE, max_lines=3)

        y += 10
        source = article.get("source", "")
        date = article.get("published", "")
        meta_text = source
        if date:
            meta_text += f"  |  {date}"
        draw.text((20, y), meta_text, font=font_meta, fill=LIGHT_GRAY)

        tags = article.get("tags", [])
        if tags:
            y += 22
            tags_text = ", ".join(tags[:5])
            draw.text((20, y), tags_text, font=font_meta, fill=BRAND_COLOR)

        result = Image.alpha_composite(img, overlay).convert("RGB")

        output_path = POSTER_DIR / f"poster_{hash(article.get('link', '')) & 0xFFFFFFFF}.jpg"
        result.save(output_path, "JPEG", quality=85)

        logger.info("Created overlay poster: %s", output_path.name)
        return output_path

    except Exception as e:
        logger.error("Failed to create overlay poster: %s", e)
        return None


def create_fallback_poster(article: dict) -> Optional[Path]:
    """Create a poster from scratch when no thumbnail is available."""
    try:
        img = Image.new("RGB", (POSTER_WIDTH, POSTER_HEIGHT), DARK_BG)
        draw = ImageDraw.Draw(img)

        for i in range(POSTER_HEIGHT):
            r = int(15 + (i / POSTER_HEIGHT) * 20)
            g = int(15 + (i / POSTER_HEIGHT) * 15)
            b = int(25 + (i / POSTER_HEIGHT) * 30)
            draw.line([(0, i), (POSTER_WIDTH, i)], fill=(r, g, b))

        draw.rectangle([(0, 0), (POSTER_WIDTH, 52)], fill=(0, 0, 0))

        font_brand = _get_font(20, bold=True)
        font_title = _get_font(28, bold=True)
        font_meta = _get_font(15, bold=False)

        draw.text((20, 14), "[CyberSecurity Terbaru]", font=font_brand, fill=BRAND_COLOR)

        draw.line([(20, 60), (POSTER_WIDTH - 20, 60)], fill=BRAND_COLOR, width=2)

        title = article.get("title", "")
        y = 80
        y = _draw_text_wrapped(draw, title, 20, y, POSTER_WIDTH - 40, font_title, WHITE, max_lines=4)

        y += 20
        source = article.get("source", "")
        date = article.get("published", "")
        meta_text = source
        if date:
            meta_text += f"  |  {date}"
        draw.text((20, y), meta_text, font=font_meta, fill=LIGHT_GRAY)

        tags = article.get("tags", [])
        if tags:
            y += 26
            tags_text = ", ".join(tags[:5])
            draw.text((20, y), tags_text, font=font_meta, fill=BRAND_COLOR)

        draw.rectangle(
            [(0, POSTER_HEIGHT - 6), (POSTER_WIDTH, POSTER_HEIGHT)],
            fill=BRAND_COLOR,
        )

        output_path = POSTER_DIR / f"poster_{hash(article.get('link', '')) & 0xFFFFFFFF}.jpg"
        img.save(output_path, "JPEG", quality=85)

        logger.info("Created fallback poster: %s", output_path.name)
        return output_path

    except Exception as e:
        logger.error("Failed to create fallback poster: %s", e)
        return None


def generate_poster(article: dict) -> Optional[Path]:
    """Generate a poster for an article.

    1. Try to download thumbnail and create overlay poster
    2. If no thumbnail, create fallback poster from scratch
    3. Return None if all methods fail
    """
    POSTER_DIR.mkdir(parents=True, exist_ok=True)

    thumbnail_url = article.get("thumbnail")

    if thumbnail_url:
        thumb_path = download_thumbnail(thumbnail_url)
        if thumb_path:
            poster = create_overlay_poster(thumb_path, article)
            thumb_path.unlink(missing_ok=True)
            if poster:
                return poster

    poster = create_fallback_poster(article)
    return poster


def cleanup_posters():
    """Remove all generated poster files."""
    if POSTER_DIR.exists():
        for f in POSTER_DIR.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
        logger.info("Cleaned up poster files")
