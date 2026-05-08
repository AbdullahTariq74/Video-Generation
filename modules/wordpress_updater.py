import requests


def get_post_id_by_slug(wp_url, slug, username, app_password):
    for endpoint in ["pages", "posts"]:
        r = requests.get(
            f"{wp_url}/wp-json/wp/v2/{endpoint}",
            params={"slug": slug},
            auth=(username, app_password),
            timeout=15
        )
        results = r.json()
        if isinstance(results, list) and results:
            return results[0]["id"]
    return None


def inject_video(wp_url, post_id, youtube_video_id, schema_html, username, app_password):
    r = requests.get(
        f"{wp_url}/wp-json/wp/v2/pages/{post_id}",
        auth=(username, app_password),
        timeout=15
    )
    current_content = r.json()["content"]["raw"]

    if youtube_video_id in current_content:
        print("  [wp] Video already injected, skipping.")
        return

    video_block = f"""
<!-- BamBam Video Block -->
<div class="bambam-video" style="margin:2rem 0;max-width:800px;">
  <iframe width="100%" height="450"
    src="https://www.youtube.com/embed/{youtube_video_id}"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen>
  </iframe>
</div>
{schema_html}
<!-- /BamBam Video Block -->
"""
    requests.post(
        f"{wp_url}/wp-json/wp/v2/pages/{post_id}",
        auth=(username, app_password),
        json={"content": current_content + "\n" + video_block},
        timeout=15
    )
