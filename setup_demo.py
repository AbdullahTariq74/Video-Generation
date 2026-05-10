"""
Creates branded intro/outro for a client using PIL (no fontconfig needed).
Usage: python setup_demo.py --client your_client_id --brand "Brand Name"
"""
import argparse
import json
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080


def get_ffmpeg():
    try:
        with open("config/settings.json") as f:
            return json.load(f).get("ffmpeg_path", "ffmpeg")
    except Exception:
        return "ffmpeg"


def find_font(size):
    candidates = [
        "C:/Windows/Fonts/ArialBD.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_branded_frame(output_png, brand_text, sub_text="", bg_color=(15, 15, 30)):
    img = Image.new("RGB", (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Gradient overlay strip at bottom
    for y in range(H // 2, H):
        alpha = int(80 * (y - H // 2) / (H // 2))
        draw.line([(0, y), (W, y)], fill=(alpha // 4, alpha // 4, alpha // 2))

    # Brand name — large, centered
    font_main = find_font(96)
    bbox = draw.textbbox((0, 0), brand_text, font=font_main)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = (H - th) // 2 - 40

    # Shadow
    draw.text((x + 4, y + 4), brand_text, font=font_main, fill=(0, 0, 0, 180))
    draw.text((x, y), brand_text, font=font_main, fill=(255, 255, 255))

    # Sub text
    if sub_text:
        font_sub = find_font(42)
        bbox2 = draw.textbbox((0, 0), sub_text, font=font_sub)
        sw = bbox2[2] - bbox2[0]
        draw.text(((W - sw) // 2, y + th + 30), sub_text, font=font_sub, fill=(200, 200, 220))

    # Accent line
    draw.rectangle([(W // 2 - 120, y - 30), (W // 2 + 120, y - 26)], fill=(80, 120, 255))

    img.save(output_png)


def image_to_video(image_path, output_path, duration):
    subprocess.run([
        get_ffmpeg(), "-y",
        "-loop", "1", "-i", image_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        output_path
    ], check=True, capture_output=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--tagline", default="", help="Optional tagline under brand name")
    args = parser.parse_args()

    assets_dir = f"assets/clients/{args.client}"
    os.makedirs(assets_dir, exist_ok=True)

    print(f"\nCreating branded intro/outro for '{args.client}'...\n")

    # Intro frame
    intro_png = f"{assets_dir}/intro_frame.png"
    tagline = args.tagline or "Professional. Trusted. Results."
    make_branded_frame(intro_png, args.brand, sub_text=tagline)
    image_to_video(intro_png, f"{assets_dir}/intro.mp4", duration=3)
    print(f"  Created: {assets_dir}/intro.mp4")

    # Outro frame
    outro_png = f"{assets_dir}/outro_frame.png"
    make_branded_frame(outro_png, args.brand, sub_text="Visit us online today", bg_color=(10, 20, 15))
    image_to_video(outro_png, f"{assets_dir}/outro.mp4", duration=4)
    print(f"  Created: {assets_dir}/outro.mp4")

    # Cleanup temp PNGs
    os.remove(intro_png)
    os.remove(outro_png)

    print("\nDone. Replace with real branded videos anytime.")
