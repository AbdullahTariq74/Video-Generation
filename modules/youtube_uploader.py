import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials


def credentials_exist(credentials_path):
    return credentials_path and os.path.exists(credentials_path)


def build_metadata(city, state, vertical, brand_name, unique_data, page_url, year=2026):
    title = f"{vertical} {city} {state} | {year} | {brand_name}"
    description = (
        f"Looking for {vertical} in {city}, {state}?\n\n"
        f"{unique_data}\n\n"
        f"{brand_name} serves {city} and surrounding areas — trusted, professional, ready.\n\n"
        f"Learn more: {page_url}\n\n"
        f"#{vertical.replace(' ','')} #{city}{vertical.replace(' ','')} "
        f"#{state.replace(' ','')}Services #{brand_name.replace(' ','')}"
    )
    tags = [
        f"{vertical} {city}", f"{vertical} {state}",
        f"best {vertical} in {city}", f"{vertical} near me",
        city, state, vertical, brand_name,
    ]
    return title, description, tags


def upload_to_youtube(video_path, title, description, tags,
                      credentials_path, category_id="19", privacy="public"):
    creds = Credentials.from_authorized_user_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy}
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4",
                            chunksize=5 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response["id"]
