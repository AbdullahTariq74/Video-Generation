import json
import re

SYSTEM_PROMPT = """You are a video script writer for 30-second local SEO videos.
Write exactly 5 lines — one per scene. Each line must be 18-25 words (spoken aloud in ~5 seconds).
The 5 lines together should take approximately 25 seconds to read aloud.
Base the script DIRECTLY on the page content provided — use the specific services, benefits, and
selling points from that page, not generic copy.
Output ONLY a JSON object with keys: hook, problem, solution, trust, cta.
No extra text, no markdown, no explanation."""

USER_TEMPLATE = """Write a 5-scene video script based on this published page:

PAGE CONTENT:
{unique_data}

DETAILS:
- City: {city}, {state}
- Service: {vertical}
- Brand: {brand_name}

Use the actual content from the page above to write specific, relevant copy — not generic filler.
Return JSON only: {{"hook": "...", "problem": "...", "solution": "...", "trust": "...", "cta": "..."}}"""


def generate_script(city, state, vertical, unique_data, brand_name,
                    anthropic_api_key=None, openai_api_key=None,
                    model="claude-haiku-4-5-20251001"):
    raw = None

    if anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            message = client.messages.create(
                model=model,
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": USER_TEMPLATE.format(
                    city=city, state=state, vertical=vertical,
                    unique_data=unique_data, brand_name=brand_name
                )}]
            )
            raw = message.content[0].text.strip()
        except Exception as e:
            print(f"  [script] Claude failed ({e}) — trying OpenAI fallback")

    if raw is None and openai_api_key:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(
                    city=city, state=state, vertical=vertical,
                    unique_data=unique_data, brand_name=brand_name
                )}
            ]
        )
        raw = resp.choices[0].message.content.strip()

    if raw is None:
        raise RuntimeError("No API key available for script generation")

    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    scenes = json.loads(raw)
    voiceover = " ".join([
        scenes["hook"], scenes["problem"], scenes["solution"],
        scenes["trust"], scenes["cta"]
    ])
    return scenes, voiceover
