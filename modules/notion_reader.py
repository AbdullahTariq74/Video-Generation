import requests


def get_pending_pages(notion_api_key, database_id):
    """Fetch all rows where Video Status is 'pending'."""
    return _query(notion_api_key, database_id, filter_body={
        "property": "Video Status",
        "select": {"equals": "pending"}
    })


def get_page_by_notion_id(notion_api_key, notion_page_id):
    """Fetch a single row by its Notion page ID (for demo / direct processing)."""
    headers = _headers(notion_api_key)
    r = requests.get(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=headers, timeout=15
    )
    r.raise_for_status()
    return [_parse_row(r.json())]


def _query(notion_api_key, database_id, filter_body=None):
    headers = _headers(notion_api_key)
    body = {"page_size": 100}
    if filter_body:
        body["filter"] = filter_body
    r = requests.post(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        headers=headers, json=body, timeout=15
    )
    r.raise_for_status()
    return [_parse_row(row) for row in r.json().get("results", [])]


def _parse_row(row):
    props = row["properties"]

    title_raw = _get(props, "Title", "title")
    page_url = _get(props, "Live URL", "url")
    city, state, service = _parse_title(title_raw, page_url)

    return {
        "notion_page_id":  row["id"],
        "page_url":        page_url,
        "page_slug":       _slug_from_url(page_url),
        "geo_city":        city,
        "geo_state":       state,
        "vertical":        service,
        "unique_data":     "",      # not in DB — script_generator uses city+service instead
        "brand_name":      "",      # filled from client config
        "hero_image_url":  "",      # not in DB — scraper gets all images from WP page
        "wp_post_id":      _get(props, "CMS Page ID", "number"),
        "video_status":    _get(props, "Video Status", "select"),
    }


def _parse_title(title, url):
    """
    Parse 'AI marketing agency Chicago | Chicago, Illinois'
    into (city, state, service).
    """
    city, state, service = "", "", ""

    if "|" in title:
        service_part, location_part = title.split("|", 1)
        location_part = location_part.strip()
        if "," in location_part:
            city = location_part.split(",")[0].strip()
            state = location_part.split(",")[1].strip()
        else:
            city = location_part

        # Strip city from service name
        service = service_part.strip()
        if city and service.lower().endswith(city.lower()):
            service = service[: -len(city)].strip()
    else:
        service = title

    return city, state, service


def _slug_from_url(url):
    if not url:
        return ""
    return url.rstrip("/").split("/")[-1]


def _get(props, key, field_type):
    if key not in props:
        return ""
    prop = props[key]
    if field_type == "url":
        return prop.get("url") or ""
    if field_type == "rich_text":
        rt = prop.get("rich_text", [])
        return rt[0]["plain_text"] if rt else ""
    if field_type == "select":
        sel = prop.get("select")
        return sel["name"] if sel else ""
    if field_type == "title":
        t = prop.get("title", [])
        return t[0]["plain_text"] if t else ""
    if field_type == "number":
        return prop.get("number") or ""
    return ""


def _headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
