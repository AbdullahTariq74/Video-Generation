import json
from datetime import date


def generate_video_schema(page_url, youtube_video_id, title, description):
    schema = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": title,
        "description": description[:300],
        "thumbnailUrl": [
            f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/hqdefault.jpg",
        ],
        "uploadDate": date.today().isoformat(),
        "duration": "PT36S",
        "contentUrl": f"https://www.youtube.com/watch?v={youtube_video_id}",
        "embedUrl": f"https://www.youtube.com/embed/{youtube_video_id}",
    }
    return f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'
