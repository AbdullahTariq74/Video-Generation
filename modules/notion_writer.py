from notion_client import Client


def update_page_status(notion_api_key, notion_page_id, youtube_video_id=None, status="done"):
    client = Client(auth=notion_api_key)
    properties = {
        "video_status": {"select": {"name": status}},
    }
    if youtube_video_id:
        properties["youtube_video_id"] = {
            "rich_text": [{"text": {"content": youtube_video_id}}]
        }
        properties["youtube_url"] = {
            "url": f"https://youtube.com/watch?v={youtube_video_id}"
        }
    client.pages.update(page_id=notion_page_id, properties=properties)
