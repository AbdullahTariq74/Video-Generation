import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080


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


def add_caption(image_path, caption, output_path, font_size=54):
    """
    Burns a caption into the bottom ~22% of the image.
    Semi-transparent dark strip + blue accent line + white text.
    """
    img = Image.open(image_path).convert("RGB").resize((W, H), Image.LANCZOS)

    if not caption:
        img.save(output_path, quality=95)
        return output_path

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)

    strip_top = int(H * 0.775)
    d_ov.rectangle([(0, strip_top), (W, H)], fill=(0, 0, 0, 172))
    d_ov.rectangle([(0, strip_top), (W, strip_top + 5)], fill=(55, 100, 255, 230))

    composited = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composited)

    font = _find_font(font_size)
    lines = textwrap.wrap(caption, width=55)[:2]
    if len(lines) == 2 and len(lines[1]) > 55:
        lines[1] = lines[1][:52] + "..."

    line_h = font_size + 10
    total_h = len(lines) * line_h
    y = strip_top + (H - strip_top - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 210))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    composited.convert("RGB").save(output_path, quality=95)
    return output_path


def add_title_overlay(image_path, service_name, location, output_path):
    """
    Adds a centered translucent band with service name + location text.
    This is the 'title card' effect the client asked for — used on Scene 1 (Hook).
    """
    img = Image.open(image_path).convert("RGB").resize((W, H), Image.LANCZOS)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)

    # Translucent center band — the "frame" the client described
    band_top = int(H * 0.30)
    band_bot = int(H * 0.70)
    d_ov.rectangle([(0, band_top), (W, band_bot)], fill=(0, 0, 0, 158))
    d_ov.rectangle([(100, band_top), (W - 100, band_top + 5)], fill=(55, 100, 255, 230))
    d_ov.rectangle([(100, band_bot - 5), (W - 100, band_bot)], fill=(55, 100, 255, 230))

    composited = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composited)

    font_big = _find_font(90)
    font_loc = _find_font(50)

    # Service name
    s_display = service_name.title()
    bbox1 = draw.textbbox((0, 0), s_display, font=font_big)
    tw1, th1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
    x1 = (W - tw1) // 2
    y1 = (H - th1) // 2 - 45
    draw.text((x1 + 4, y1 + 4), s_display, font=font_big, fill=(0, 0, 0, 180))
    draw.text((x1, y1), s_display, font=font_big, fill=(255, 255, 255, 255))

    # Location line
    if location:
        bbox2 = draw.textbbox((0, 0), location, font=font_loc)
        tw2 = bbox2[2] - bbox2[0]
        x2 = (W - tw2) // 2
        y2 = y1 + th1 + 18
        draw.text((x2 + 2, y2 + 2), location, font=font_loc, fill=(0, 0, 0, 160))
        draw.text((x2, y2), location, font=font_loc, fill=(200, 220, 255, 255))

    composited.convert("RGB").save(output_path, quality=95)
    return output_path
