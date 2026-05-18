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


def _probe_duration(path):
    """Return duration in seconds using ffprobe (sibling binary next to ffmpeg)."""
    ffmpeg_dir = os.path.dirname(FFMPEG)
    ffprobe_name = "ffprobe.exe" if FFMPEG.endswith(".exe") else "ffprobe"
    ffprobe = os.path.join(ffmpeg_dir, ffprobe_name) if ffmpeg_dir else ffprobe_name
    try:
        cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path]
        return float(subprocess.check_output(cmd).decode().strip())
    except Exception:
        return 5.0


def normalize_clip(src, dst):
    """Force any image or video to 1920x1080 H.264."""
    _run([
        "ffmpeg", "-y", "-i", src,
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", dst
    ])


def image_to_clip(image_path, dst, duration=5, motion="zoom_in"):
    """Animate a still image into a video clip with Ken Burns motion. No static captions."""
    frames = duration * FPS
    zoom_filter = _motion_filter(motion, frames)
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
        f"{zoom_filter}"
    )
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
        dst
    ])


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


def concat_with_audio(clip_paths, voiceover_path, output_path, intro_duration=0):
    """Concatenate video clips and mix voiceover audio, with optional intro sync."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        concat_file = f.name
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    silent = output_path.replace(".mp4", "_silent.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", silent])

    # Prepend silence equal to intro duration so voiceover starts after intro
    synced_audio = voiceover_path
    if intro_duration > 0:
        synced_audio = voiceover_path.replace(".mp3", "_synced.mp3")
        _run([
            "ffmpeg", "-y",
            "-t", str(intro_duration),          # limit silence to intro duration
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-i", voiceover_path,
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
            synced_audio
        ])

    mixed = output_path.replace(".mp4", "_mixed.mp4")
    _run([
        "ffmpeg", "-y",
        "-i", silent, "-i", synced_audio,
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
    if intro_duration > 0 and os.path.exists(synced_audio):
        os.remove(synced_audio)


def assemble_video(image_paths, scenes, broll_paths, intro_path, outro_path,
                   voiceover_path, output_path, work_dir, image_duration=5,
                   openai_api_key=None):
    """
    Assembly: intro → image clips (no static captions) → b-roll fill to 30s → outro + voiceover.
    B-roll is added after images until the visual track covers the full voiceover + buffer.
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

    def img(src, motion_key, duration):
        nonlocal idx
        dst = os.path.join(work_dir, f"clip_{idx:03d}_scene.mp4")
        idx += 1
        image_to_clip(src, dst, duration=duration, motion=motion_key)
        return dst

    # Intro
    intro_clip = norm(intro_path, "intro")
    clips.append(intro_clip)
    intro_dur = _probe_duration(intro_clip)

    # Voiceover duration — determines how long the visual track needs to be
    vo_dur = _probe_duration(voiceover_path)
    # Target: visual content must cover voiceover + 1.5s tail so video never cuts mid-speech
    target_content_dur = vo_dur + 1.5

    # Image clips (no static captions — live Whisper captions handle text)
    content_dur = 0.0
    for i, img_path in enumerate(image_paths):
        motion = MOTIONS[i % len(MOTIONS)]
        dur = (image_duration[i] if isinstance(image_duration, list) and i < len(image_duration)
               else (image_duration if isinstance(image_duration, int) else 5))
        clip = img(img_path, motion, dur)
        clips.append(clip)
        content_dur += dur

    # Fill with b-roll until visual track covers the full voiceover
    broll_cycle = (broll_paths * 20) if broll_paths else []
    broll_idx = 0
    while content_dur < target_content_dur and broll_idx < len(broll_cycle):
        broll_clip = norm(broll_cycle[broll_idx], f"broll{broll_idx}")
        clips.append(broll_clip)
        content_dur += _probe_duration(broll_clip)
        broll_idx += 1

    # Outro
    clips.append(norm(outro_path, "outro"))

    print(f"  -> Visual track: {content_dur:.1f}s content + intro/outro | Voiceover: {vo_dur:.1f}s")

    concat_with_audio(clips, voiceover_path, output_path, intro_duration=intro_dur)

    # Burn live word-by-word captions via Whisper
    try:
        from modules.captions import generate_captions, burn_captions
        ass_path = os.path.join(work_dir, "captions.ass")
        print("  -> Transcribing voiceover for captions (Whisper)...")
        generate_captions(voiceover_path, ass_path,
                          openai_api_key=openai_api_key,
                          offset=intro_dur)
        captioned_path = output_path.replace(".mp4", "_captioned.mp4")
        print("  -> Burning captions into video...")
        burn_captions(output_path, ass_path, captioned_path, ffmpeg_path=FFMPEG)
        os.replace(captioned_path, output_path)
        print("  -> Captions burned in.")
    except Exception as e:
        print(f"  [captions] Skipped — {e}")
