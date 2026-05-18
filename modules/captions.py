"""
Live word-by-word captions: Whisper transcription → ASS subtitle file → FFmpeg burn-in.
Uses OpenAI Whisper API if an api_key is supplied, otherwise falls back to local whisper package.
"""
import os
import subprocess

WORDS_PER_CUE = 4  # social media style: 3-4 words appear at a time


def generate_captions(voiceover_path, output_ass_path, openai_api_key=None, offset=0.0):
    """Transcribe voiceover and write an ASS subtitle file ready for burn-in.
    offset: seconds to shift all timestamps forward (= intro clip duration).
    """
    words = _transcribe(voiceover_path, openai_api_key)
    if not words:
        raise RuntimeError("Whisper returned no words — check audio file")
    _words_to_ass(words, output_ass_path, offset=offset)
    return output_ass_path


def burn_captions(video_path, ass_path, output_path, ffmpeg_path="ffmpeg"):
    """Burn ASS captions into video, writing a new file at output_path."""
    # FFmpeg subtitles filter on Windows needs the colon in the drive letter escaped
    safe = os.path.abspath(ass_path).replace("\\", "/")
    # Escape colon in drive letter (e.g. C:/ → C\:/)
    if len(safe) > 1 and safe[1] == ":":
        safe = safe[0] + "\\:" + safe[2:]

    result = subprocess.run([
        ffmpeg_path, "-y", "-i", video_path,
        "-vf", f"subtitles='{safe}'",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path
    ], capture_output=True)

    if result.returncode != 0:
        raise RuntimeError(f"Caption burn failed:\n{result.stderr.decode()[-800:]}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _transcribe(audio_path, openai_api_key=None):
    """Return list of {word, start, end} dicts."""
    if openai_api_key:
        try:
            return _transcribe_openai(audio_path, openai_api_key)
        except Exception as e:
            print(f"  [captions] OpenAI Whisper failed ({e}) — trying local whisper")
    return _transcribe_local(audio_path)


def _transcribe_openai(audio_path, api_key):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )
    return [
        {"word": w.word.strip(), "start": w.start, "end": w.end}
        for w in result.words if w.word.strip()
    ]


def _transcribe_local(audio_path):
    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "Local whisper not installed. Run: pip install openai-whisper\n"
            "Or provide an openai_api_key."
        )
    print("  [captions] Loading local Whisper model (base)...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            if w["word"].strip():
                words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})
    return words


def _ts(seconds):
    """Seconds → ASS timestamp  H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _words_to_ass(words, output_path, offset=0.0):
    """Write ASS file with WORDS_PER_CUE words per cue, social-media style."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # White text, black 4px outline, bold, center-bottom, MarginV=90
        "Style: Cap,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,1,0,1,4,1,2,80,80,90,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    cues = []
    for i in range(0, len(words), WORDS_PER_CUE):
        chunk = words[i : i + WORDS_PER_CUE]
        start = chunk[0]["start"] + offset
        end = chunk[-1]["end"] + offset + 0.15  # tiny tail for readability
        text = " ".join(w["word"] for w in chunk)
        cues.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{text}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.writelines(cues)
