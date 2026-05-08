import os
import hashlib
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}


def download_images(image_urls, output_dir):
    """Download image URLs to output_dir. Returns list of local file paths."""
    os.makedirs(output_dir, exist_ok=True)
    local_paths = []

    for url in image_urls:
        ext = url.split("?")[0].split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            ext = "jpg"
        filename = hashlib.md5(url.encode()).hexdigest()[:12] + f".{ext}"
        local_path = os.path.join(output_dir, filename)

        if not os.path.exists(local_path):
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"  [downloader] Failed to download {url} — {e}")
                continue

        local_paths.append(local_path)

    return local_paths
