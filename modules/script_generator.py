import anthropic

SYSTEM_PROMPT = """You are a video script writer for short local SEO videos.
Write exactly 5 lines — one per scene. Each line must be under 15 words.
Output ONLY a JSON object with keys: hook, problem, solution, trust, cta.
No extra text, no markdown, no explanation."""

USER_TEMPLATE = """Write a 5-scene video script for this local business page:
- City: {city}, {state}
- Service: {vertical}
- Brand: {brand_name}
- Unique selling point: {unique_data}

Return JSON only: {{"hook": "...", "problem": "...", "solution": "...", "trust": "...", "cta": "..."}}"""


def generate_script(city, state, vertical, unique_data, brand_name, anthropic_api_key, model="claude-haiku-4-5-20251001"):
    client = anthropic.Anthropic(api_key=anthropic_api_key)
    message = client.messages.create(
        model=model,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": USER_TEMPLATE.format(
                city=city, state=state, vertical=vertical,
                unique_data=unique_data, brand_name=brand_name
            )
        }]
    )
    import json
    raw = message.content[0].text.strip()
    scenes = json.loads(raw)
    voiceover = " ".join([
        scenes["hook"], scenes["problem"], scenes["solution"],
        scenes["trust"], scenes["cta"]
    ])
    return scenes, voiceover
