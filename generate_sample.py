import os
import json
import random
import sys
import subprocess

# Add current directory to path so modules can be imported
sys.path.append(os.getcwd())

from modules.assembler import assemble_video, set_ffmpeg_path
from modules.tts import make_voiceover
from modules.caption_overlay import add_title_overlay

# Settings
FFMPEG_PATH = "C:/Users/abdta/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffmpeg.exe"
FFPROBE_PATH = "C:/Users/abdta/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffprobe.exe"
CLIENT_ID = "simplecarship"
VERTICAL = "Auto Transport"
CITY = "Miami"
STATE = "Florida"
BRAND_NAME = "Simple Car Ship"
CARTESIA_KEY = "sk_car_TYQL6dKfZYDuPtmD3ZxDuQ"

def get_duration(path):
    cmd = [
        FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ]
    return float(subprocess.check_output(cmd).decode().strip())

def generate():
    set_ffmpeg_path(FFMPEG_PATH)
    work_dir = "output/sample_simplecarship"
    os.makedirs(work_dir, exist_ok=True)

    print("--- Generating Sync-Corrected Sample Video for Simple Car Ship ---")

    # 1. Assets Selection
    intro_path = f"assets/clients/{CLIENT_ID}/intro.mp4"
    outro_path = f"assets/clients/{CLIENT_ID}/outro.mp4"
    
    if not os.path.exists(intro_path) or not os.path.exists(outro_path):
        print(f"Error: Missing intro/outro for {CLIENT_ID}.")
        return

    # Stock images
    stock_images = []
    base_stock_dir = "assets/stock_images/by_vertical/auto_transport"
    for category in ["truck loading", "highway driving", "luxury cars", "inspections"]:
        cat_dir = os.path.join(base_stock_dir, category)
        if os.path.exists(cat_dir):
            files = [os.path.join(cat_dir, f) for f in os.listdir(cat_dir) if f.endswith((".png", ".jpg", ".jpeg"))]
            if files:
                stock_images.append(random.choice(files))
    
    if len(stock_images) < 4:
        cat_dir = os.path.join(base_stock_dir, "truck loading")
        files = [os.path.join(cat_dir, f) for f in os.listdir(cat_dir) if f.endswith((".png", ".jpg"))]
        stock_images.extend(random.sample(files, 4 - len(stock_images)))
    
    selected_images = stock_images[:4]

    # B-roll selection
    base_broll_dir = "assets/broll/by_vertical/auto_transport"
    broll_clips = [os.path.join(base_broll_dir, f) for f in os.listdir(base_broll_dir) if f.endswith(".mp4")]
    random.shuffle(broll_clips)
    selected_broll = broll_clips[:2]

    # 2. Script
    scenes = {
        "hook": "Are you looking for a reliable auto transport service in Miami? Simple Car Ship is here to provide the professional care your vehicle deserves.",
        "problem": "Moving a car can be a stressful and complicated process, often filled with hidden costs and carriers that just don't communicate with you.",
        "solution": "At Simple Car Ship, we make vehicle transport easy and transparent. Our door-to-door service ensures your car is handled with absolute safety and security.",
        "trust": "We are fully insured and highly rated for our commitment to excellence. Whether it's a luxury car or a daily driver, we treat every vehicle like our own.",
        "cta": "Ready to get started? Visit SimpleCarShip.com today for your free Florida shipping quote and experience the professional difference with Simple Car Ship."
    }
    
    # 3. Synchronize Scene Durations
    print("  -> Measuring scene durations for perfect sync...")
    durations = []
    scene_order = ["hook", "problem", "solution", "trust", "cta"]
    for key in scene_order:
        tmp_path = os.path.join(work_dir, f"tmp_{key}.mp3")
        make_voiceover(scenes[key], tmp_path, cartesia_api_key=CARTESIA_KEY)
        dur = get_duration(tmp_path)
        # Add a tiny buffer (0.3s) for natural pause
        durations.append(dur + 0.3)
        os.remove(tmp_path)
    
    print(f"  -> Calculated durations: {durations}")

    # Full voiceover text
    voiceover_text = "  ".join([scenes[k] for k in scene_order])
    voiceover_path = os.path.join(work_dir, "voiceover.mp3")
    print("  -> Generating full voiceover...")
    make_voiceover(voiceover_text, voiceover_path, cartesia_api_key=CARTESIA_KEY)

    # 4. Title Card
    print("  -> Creating title card...")
    title_card_path = os.path.join(work_dir, "title_card.jpg")
    add_title_overlay(selected_images[0], VERTICAL, f"{CITY}, {STATE}", title_card_path)

    # 5. Assemble
    print("  -> Assembling video...")
    all_images = [title_card_path] + selected_images
    output_path = "output/sample_simplecarship.mp4"
    
    try:
        assemble_video(
            image_paths=all_images,
            scenes=scenes,
            broll_paths=selected_broll,
            intro_path=intro_path,
            outro_path=outro_path,
            voiceover_path=voiceover_path,
            output_path=output_path,
            work_dir=work_dir,
            image_duration=durations
        )
        print(f"\n[OK] Success! Perfectly synced video created: {output_path}")
    except Exception as e:
        print(f"\n[FAIL] Assembly failed: {e}")

if __name__ == "__main__":
    generate()
