import os
import re
import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _find_font(size):
    candidates = [
        "C:/Windows/Fonts/ArialBD.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _make_pil_service_image(service, output_path):
    """Professional dark-brand service cover image — no API needed."""
    img = Image.new("RGB", (W, H), (10, 12, 30))
    draw = ImageDraw.Draw(img)

    # Dark gradient top → bottom
    for y in range(H):
        t = y / H
        r = int(10 + t * 15)
        g = int(12 + t * 18)
        b = int(30 + t * 35)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Subtle diagonal grid lines
    for i in range(-H, W + H, 90):
        draw.line([(i, 0), (i + H, H)], fill=(255, 255, 255, 6), width=1)

    # Blue horizontal accent lines flanking the text zone
    draw.rectangle([(120, H // 2 - 130), (W - 120, H // 2 - 125)], fill=(55, 100, 255))
    draw.rectangle([(120, H // 2 + 115), (W - 120, H // 2 + 120)], fill=(55, 100, 255))

    # Corner marks
    for cx, cy, dx, dy in [(120, 120, 1, 1), (W - 120, 120, -1, 1),
                            (120, H - 120, 1, -1), (W - 120, H - 120, -1, -1)]:
        draw.line([(cx, cy), (cx + dx * 60, cy)], fill=(55, 100, 255), width=3)
        draw.line([(cx, cy), (cx, cy + dy * 60)], fill=(55, 100, 255), width=3)

    # Service name centered
    display = service.title()
    font_main = _find_font(100)
    bbox = draw.textbbox((0, 0), display, font=font_main)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = (H - th) // 2 - 15

    # Drop shadow layers
    for ox, oy in [(8, 8), (5, 5), (3, 3)]:
        draw.text((x + ox, y + oy), display, font=font_main, fill=(0, 0, 0))
    draw.text((x, y), display, font=font_main, fill=(255, 255, 255))

    # Subtitle below
    font_sub = _find_font(40)
    sub = "Professional Services"
    bbox2 = draw.textbbox((0, 0), sub, font=font_sub)
    sw = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, y + th + 28), sub, font=font_sub, fill=(160, 185, 230))

    img.save(output_path, quality=95)
    return output_path


def _make_kie_service_image(service, output_path, kie_api_key, kie_endpoint):
    """Generate via Kie.ai image API."""
    prompt = (
        f"Ultra-professional {service} business hero photograph, "
        "dark navy luxury background, cinematic soft studio lighting, "
        "high-end corporate advertising style, no text, no watermark, "
        "16:9 aspect ratio, photorealistic, 4K"
    )
    resp = requests.post(
        kie_endpoint,
        headers={"Authorization": f"Bearer {kie_api_key}", "Content-Type": "application/json"},
        json={"prompt": prompt, "n": 1, "size": "1920x1080"},
        timeout=90,
    )
    resp.raise_for_status()
    image_url = resp.json()["data"][0]["url"]

    img_resp = requests.get(image_url, timeout=30)
    img_resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(img_resp.content)
    return output_path


def get_or_create_service_image(service, output_dir, kie_api_key=None, kie_endpoint=None):
    """
    Returns path to a professional cover image for this service.
    Creates and caches it on first call; subsequent calls return cached copy.
    """
    os.makedirs(output_dir, exist_ok=True)
    cover_path = os.path.join(output_dir, "cover.jpg")

    if os.path.exists(cover_path):
        return cover_path

    if kie_api_key:
        try:
            return _make_kie_service_image(service, cover_path, kie_api_key, kie_endpoint)
        except Exception as e:
            print(f"  [service-img] Kie.ai failed ({e}) — using PIL fallback")

    return _make_pil_service_image(service, cover_path)
