import requests


def update_page_status(notion_api_key, notion_page_id, youtube_video_id=None, status="done", field_map=None):
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    
    status_field = "Video Status"
    if field_map and "video_status" in field_map:
        status_field = field_map["video_status"]
        
    properties = {
        status_field: {"select": {"name": status}},
    }
    
    url_field = "Video URL"
    if field_map and "video_url" in field_map:
        url_field = field_map["video_url"]

    if youtube_video_id:
        properties[url_field] = {
            "url": f"https://youtube.com/watch?v={youtube_video_id}"
        }
        
    requests.patch(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=headers, json={"properties": properties}, timeout=15
    )
