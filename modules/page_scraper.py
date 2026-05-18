import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

SKIP_PATTERNS = ["logo", "icon", "avatar", "badge", "pixel", "tracking", "1x1", "spinner", "flag"]
CONTENT_SELECTORS = ["article", "main", ".entry-content", ".page-content", "#content", ".wp-block-group"]


def extract_page_text(page_url, max_words=400):
    """
    Scrape the page's text content — headings, paragraphs, list items.
    Returns a plain-text summary used by the script generator.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BamBam-VideoBot/1.0)"}
        resp = requests.get(page_url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()

        content_area = None
        for sel in CONTENT_SELECTORS:
            content_area = soup.select_one(sel)
            if content_area:
                break
        if not content_area:
            content_area = soup.find("body") or soup

        lines = []
        for tag in content_area.find_all(["h1", "h2", "h3", "p", "li"]):
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 20:   # skip tiny fragments
                lines.append(text)

        combined = " | ".join(lines)
        words = combined.split()
        return " ".join(words[:max_words])

    except Exception as e:
        print(f"  [scraper] Text scrape failed for {page_url} — {e}")
        return ""


def extract_page_images(page_url, hero_image_url, max_images=5):
    """
    Scrape the published WordPress page and return up to max_images image URLs.
    Hero image from Notion is always first.
    """
    images = []
    if hero_image_url:
        images.append(hero_image_url)

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BamBam-VideoBot/1.0)"}
        resp = requests.get(page_url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        content_area = None
        for sel in CONTENT_SELECTORS:
            content_area = soup.select_one(sel)
            if content_area:
                break
        if not content_area:
            content_area = soup

        for img in content_area.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue
            abs_url = urljoin(page_url, src)
            if any(p in abs_url.lower() for p in SKIP_PATTERNS):
                continue
            if abs_url not in images:
                images.append(abs_url)
            if len(images) >= max_images:
                break

        # og:image as extra fallback if still short
        if len(images) < 2:
            og = soup.find("meta", property="og:image")
            if og and og.get("content") and og["content"] not in images:
                images.insert(1, og["content"])

    except Exception as e:
        print(f"  [scraper] Warning: could not fully scrape {page_url} — {e}")

    return images[:max_images]
