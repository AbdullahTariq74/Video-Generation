from notion_client import Client


def get_pending_pages(notion_api_key, database_id):
    client = Client(auth=notion_api_key)
    results = client.databases.query(
        database_id=database_id,
        filter={"property": "video_status", "select": {"equals": "pending"}}
    )
    pages = []
    for r in results["results"]:
        props = r["properties"]
        pages.append({
            "notion_page_id":  r["id"],
            "page_url":        _text(props, "page_url", field_type="url"),
            "page_slug":       _text(props, "page_slug"),
            "geo_city":        _text(props, "geo_city"),
            "geo_state":       _text(props, "geo_state"),
            "vertical":        _text(props, "vertical"),
            "unique_data":     _text(props, "unique_data_point"),
            "brand_name":      _text(props, "brand_name"),
            "youtube_channel": _text(props, "youtube_channel_id"),
            "hero_image_url":  _text(props, "hero_image_url", field_type="url"),
        })
    return pages


def _text(props, key, field_type="rich_text"):
    if key not in props:
        return ""
    prop = props[key]
    if field_type == "url":
        return prop.get("url") or ""
    rich = prop.get("rich_text", [])
    if not rich:
        return ""
    return rich[0]["plain_text"]
