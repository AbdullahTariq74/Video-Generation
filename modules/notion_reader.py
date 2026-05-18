import requests


def get_pending_pages(notion_api_key, database_id, field_map=None):
    """Fetch all rows where Video Status is 'queued'."""
    status_field = "Video Status"
    status_value = "queued"

    if field_map and "video_status" in field_map:
        status_field = field_map["video_status"]

    return _query(notion_api_key, database_id, field_map=field_map, filter_body={
        "property": status_field,
        "select": {"equals": status_value}
    })


def get_page_by_notion_id(notion_api_key, notion_page_id, field_map=None):
    """Fetch a single row by its Notion page ID."""
    headers = _headers(notion_api_key)
    r = requests.get(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=headers, timeout=15
    )
    r.raise_for_status()
    return [_parse_row(r.json(), field_map, notion_api_key)]


def _query(notion_api_key, database_id, filter_body=None, field_map=None):
    headers = _headers(notion_api_key)
    body = {"page_size": 100}
    if filter_body:
        body["filter"] = filter_body
    r = requests.post(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        headers=headers, json=body, timeout=15
    )
    r.raise_for_status()
    return [_parse_row(row, field_map, notion_api_key) for row in r.json().get("results", [])]


def _parse_row(row, field_map=None, api_key=None):
    props = row["properties"]
    fm = field_map or {}

    # Field name resolution with defaults
    title_key      = fm.get("title",           "Title")
    url_key        = fm.get("page_url",         "WordPress URL")
    cms_id_key     = fm.get("cms_post_id",      "WordPress Post ID")
    status_key     = fm.get("video_status",     "Video Status")
    hero_key       = fm.get("hero_image_url",   "Image URL")
    loc_key        = fm.get("location_relation","Location")
    svc_key        = fm.get("service_relation", "Service")

    title_raw  = _get(props, title_key, "title")
    page_url   = _get(props, url_key, "url")
    hero_image = _get(props, hero_key, "url")
    wp_post_id = _get(props, cms_id_key, "number")

    # Resolve city/state from Location relation, fall back to title parse
    city, state = _resolve_location(props, loc_key, api_key)
    if not city:
        city, state, _ = _parse_title(title_raw, page_url)

    # Resolve service from Service relation, fall back to title parse
    vertical = _resolve_service(props, svc_key, api_key)
    if not vertical:
        _, _, vertical = _parse_title(title_raw, page_url)

    return {
        "notion_page_id": row["id"],
        "page_url":       page_url or "",
        "page_slug":      _slug_from_url(page_url) or _slugify(title_raw),
        "geo_city":       city,
        "geo_state":      state,
        "vertical":       vertical,
        "unique_data":    "",
        "brand_name":     "",
        "hero_image_url": hero_image or "",
        "wp_post_id":     wp_post_id,
        "video_status":   _get(props, status_key, "select"),
    }


def _resolve_location(props, loc_key, api_key):
    """Fetch the linked Location page and return (city, state)."""
    if not api_key:
        return "", ""
    relation = props.get(loc_key, {}).get("relation", [])
    if not relation:
        return "", ""
    try:
        page_id = relation[0]["id"]
        r = requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers(api_key), timeout=10
        )
        r.raise_for_status()
        p = r.json()["properties"]
        city  = (p.get("City Name", {}).get("title") or [{}])
        state = (p.get("State", {}).get("rich_text") or [{}])
        return (
            city[0].get("plain_text", "") if city else "",
            state[0].get("plain_text", "") if state else "",
        )
    except Exception as e:
        print(f"  [notion] Location resolve failed: {e}")
        return "", ""


def _resolve_service(props, svc_key, api_key):
    """Fetch the linked Service page and return the service name."""
    if not api_key:
        return ""
    relation = props.get(svc_key, {}).get("relation", [])
    if not relation:
        return ""
    try:
        page_id = relation[0]["id"]
        r = requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers(api_key), timeout=10
        )
        r.raise_for_status()
        p = r.json()["properties"]
        svc = (p.get("Service Name", {}).get("title") or [{}])
        return svc[0].get("plain_text", "") if svc else ""
    except Exception as e:
        print(f"  [notion] Service resolve failed: {e}")
        return ""


def _parse_title(title, url):
    """Fallback: parse 'Service | City, State' into (city, state, service)."""
    city, state, service = "", "", ""
    if "|" in title:
        service_part, location_part = title.split("|", 1)
        location_part = location_part.strip()
        if "," in location_part:
            city  = location_part.split(",")[0].strip()
            state = location_part.split(",")[1].strip()
        else:
            city = location_part
        service = service_part.strip()
        if city and service.lower().endswith(city.lower()):
            service = service[: -len(city)].strip()
    else:
        service = title
    return city, state, service


def _slugify(text):
    return text.lower().replace(" ", "-").replace("/", "-") if text else ""


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
