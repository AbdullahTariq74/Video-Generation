import os
import subprocess
import tempfile

W, H = 1920, 1080
FPS = 25
FFMPEG = "ffmpeg"  # overridden by set_ffmpeg_path()

FONT_PATH = (
    "C:/Windows/Fonts/Arial.ttf"
    if os.path.exists("C:/Windows/Fonts/Arial.ttf")
    else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)


def set_ffmpeg_path(path):
    global FFMPEG
    FFMPEG = path


def _run(cmd):
    cmd[0] = FFMPEG
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{result.stderr.decode()}")


def normalize_clip(src, dst):
    """Force any image or video to 1920x1080 H.264."""
    _run([
        "ffmpeg", "-y", "-i", src,
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", dst
    ])


def image_to_clip(image_path, dst, duration=5, caption="", motion="zoom_in"):
    """Animate a still image into a video clip with Ken Burns motion and optional caption."""
    from modules.caption_overlay import add_caption

    frames = duration * FPS
    zoom_filter = _motion_filter(motion, frames)

    # Burn caption into image via PIL (works on Windows — no fontconfig needed)
    src = image_path
    captioned_tmp = None
    if caption:
        captioned_tmp = dst.replace(".mp4", "_src.jpg")
        add_caption(image_path, caption, captioned_tmp)
        src = captioned_tmp

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
        f"{zoom_filter}"
    )
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", src,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
        dst
    ])

    if captioned_tmp and os.path.exists(captioned_tmp):
        os.remove(captioned_tmp)


def _motion_filter(motion, frames):
    if motion == "zoom_in":
        return f"zoompan=z='min(zoom+0.0008,1.08)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif motion == "zoom_out":
        return f"zoompan=z='if(eq(on\\,1)\\,1.08\\,max(zoom-0.0008\\,1.0))':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif motion == "pan_right":
        return f"zoompan=z='1.05':d={frames}:x='on/{frames}*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)'"
    else:  # pan_left
        return f"zoompan=z='1.05':d={frames}:x='(iw-iw/zoom)-on/{frames}*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)'"


MOTIONS = ["zoom_in", "zoom_out", "pan_right", "pan_left"]


def concat_with_audio(clip_paths, voiceover_path, output_path):
    """Concatenate video clips and mix voiceover audio."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        concat_file = f.name
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    silent = output_path.replace(".mp4", "_silent.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", silent])

    mixed = output_path.replace(".mp4", "_mixed.mp4")
    _run([
        "ffmpeg", "-y",
        "-i", silent, "-i", voiceover_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", "apad", "-shortest",
        mixed
    ])

    # Re-encode for maximum compatibility (WhatsApp, email, mobile)
    _run([
        "ffmpeg", "-y", "-i", mixed,
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
        "-pix_fmt", "yuv420p", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ])

    os.unlink(concat_file)
    os.remove(silent)
    os.remove(mixed)


def assemble_video(image_paths, scenes, broll_paths, intro_path, outro_path,
                   voiceover_path, output_path, work_dir, image_duration=5):
    """
    Full assembly: intro → 5 image scenes (broll every 2 images) → outro + voiceover.
    scenes: dict with keys hook/problem/solution/trust/cta for captions.
    """
    os.makedirs(work_dir, exist_ok=True)
    clips = []
    idx = 0

    def norm(src, label):
        nonlocal idx
        dst = os.path.join(work_dir, f"clip_{idx:03d}_{label}.mp4")
        idx += 1
        normalize_clip(src, dst)
        return dst

    def img(src, caption, motion_key):
        nonlocal idx
        dst = os.path.join(work_dir, f"clip_{idx:03d}_scene.mp4")
        idx += 1
        image_to_clip(src, dst, duration=image_duration, caption=caption, motion=motion_key)
        return dst

    scene_order = ["hook", "problem", "solution", "trust", "cta"]
    broll_cycle = (broll_paths * 10) if broll_paths else []
    broll_idx = 0

    clips.append(norm(intro_path, "intro"))

    for i, (img_path, scene_key) in enumerate(zip(image_paths, scene_order)):
        caption = scenes.get(scene_key, "") if scenes else ""
        motion = MOTIONS[i % len(MOTIONS)]
        clips.append(img(img_path, caption, motion))

        # Insert broll after every 2nd image (not after the last image)
        if (i + 1) % 2 == 0 and i < len(image_paths) - 1 and broll_cycle:
            if broll_idx < len(broll_cycle):
                clips.append(norm(broll_cycle[broll_idx], f"broll{broll_idx}"))
                broll_idx += 1

    clips.append(norm(outro_path, "outro"))

    concat_with_audio(clips, voiceover_path, output_path)
