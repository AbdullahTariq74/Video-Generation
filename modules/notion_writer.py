import requests


def update_page_status(notion_api_key, notion_page_id, youtube_video_id=None, status="done"):
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    properties = {
        "Video Status": {"select": {"name": status}},
    }
    if youtube_video_id:
        properties["Video URL"] = {
            "url": f"https://youtube.com/watch?v={youtube_video_id}"
        }
    requests.patch(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=headers, json={"properties": properties}, timeout=15
    )
