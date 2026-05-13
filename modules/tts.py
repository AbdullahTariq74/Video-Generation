import asyncio

# Cartesia is primary. edge-tts is fallback when no Cartesia key or on any error.

CARTESIA_MODEL = "sonic-english"


def make_voiceover(text, output_path, cartesia_api_key=None, voice_id=""):
    if cartesia_api_key:
        try:
            resolved_voice = voice_id or _get_default_voice(cartesia_api_key)
            _cartesia(text, output_path, cartesia_api_key, resolved_voice)
            return
        except Exception as e:
            print(f"  [tts] Cartesia failed ({e}) — falling back to edge-tts")

    print("  [tts] Using edge-tts fallback")
    asyncio.run(_edge_tts(text, output_path))


def _get_default_voice(api_key):
    """Pick the best English voice available on the account."""
    from cartesia import Cartesia
    client = Cartesia(api_key=api_key)
    voices = client.voices.list()

    # Only consider English voices
    en_voices = [v for v in voices if getattr(v, "language", "en") in ("en", "en-US", "english")]
    pool = en_voices or voices  # fallback to all if nothing tagged English

    preferred_keywords = ["professional", "news", "narrat", "announcer", "male"]
    for kw in preferred_keywords:
        for v in pool:
            if kw in getattr(v, "name", "").lower():
                print(f"  [tts] Using Cartesia voice: {v.name} ({v.id})")
                return v.id

    first = pool[0]
    print(f"  [tts] Using Cartesia voice: {first.name} ({first.id})")
    return first.id


def _cartesia(text, output_path, api_key, voice_id):
    from cartesia import Cartesia
    client = Cartesia(api_key=api_key)
    result = client.tts.bytes(
        model_id=CARTESIA_MODEL,
        transcript=text,
        voice={"mode": "id", "id": voice_id},
        output_format={"container": "mp3", "encoding": "mp3", "sample_rate": 44100},
    )
    # SDK may return a generator of chunks or raw bytes
    audio_bytes = b"".join(result) if not isinstance(result, (bytes, bytearray)) else result
    with open(output_path, "wb") as f:
        f.write(audio_bytes)


async def _edge_tts(text, output_path, voice="en-US-GuyNeural"):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_path)
