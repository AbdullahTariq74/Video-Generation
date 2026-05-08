import os
import json
import requests
import hashlib

# Kie.ai image generation — called only when scraped images are fewer than needed.


def generate_images(city, state, vertical, count, output_dir, kie_api_key, kie_endpoint, prompt_template):
    """
    Generate `count` images via Kie.ai API.
    Returns list of local file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    local_paths = []

    prompt = prompt_template.format(vertical=vertical, city=city, state=state)

    for i in range(count):
        try:
            headers = {
                "Authorization": f"Bearer {kie_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "prompt": prompt,
                "n": 1,
                "size": "1920x1080",
            }
            resp = requests.post(kie_endpoint, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            # Kie.ai returns image URLs in data["data"][0]["url"] — adjust if their schema differs
            image_url = data["data"][0]["url"]
            filename = hashlib.md5(f"{prompt}{i}".encode()).hexdigest()[:12] + ".jpg"
            local_path = os.path.join(output_dir, filename)

            img_resp = requests.get(image_url, timeout=30)
            img_resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(img_resp.content)

            local_paths.append(local_path)
            print(f"  [generator] Generated image {i+1}/{count}")

        except Exception as e:
            print(f"  [generator] Failed to generate image {i+1} — {e}")

    return local_paths
