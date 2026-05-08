import asyncio
import os

# Cartesia is primary. edge-tts is fallback when no Cartesia key is provided.


def make_voiceover(text, output_path, cartesia_api_key=None, voice_id="sonic-english"):
    if cartesia_api_key:
        _cartesia(text, output_path, cartesia_api_key, voice_id)
    else:
        print("  [tts] No Cartesia key — using edge-tts fallback")
        asyncio.run(_edge_tts(text, output_path))


def _cartesia(text, output_path, api_key, voice_id):
    from cartesia import Cartesia
    client = Cartesia(api_key=api_key)
    audio_bytes = client.tts.bytes(
        model_id="sonic-english",
        transcript=text,
        voice={"mode": "id", "id": voice_id},
        output_format={"container": "mp3", "encoding": "mp3", "sample_rate": 44100},
    )
    with open(output_path, "wb") as f:
        f.write(audio_bytes)


async def _edge_tts(text, output_path, voice="en-US-GuyNeural"):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_path)
