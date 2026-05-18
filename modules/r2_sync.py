"""
Cloudflare R2 asset sync — download assets at startup, upload videos after generation.

Required env vars:
  R2_ENDPOINT_URL   https://<account_id>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET         bucket name (default: simplecarshop)
"""
import os

import boto3
from botocore.client import Config


def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _bucket():
    return os.environ.get("R2_BUCKET", "simplecarshop")


def download_assets(local_root=".", prefixes=None):
    """Download R2 objects under each prefix into local_root (skips existing files)."""
    prefixes = prefixes or ["assets/"]
    client = _client()
    bucket = _bucket()

    for prefix in prefixes:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                local_path = os.path.join(local_root, key)
                if os.path.exists(local_path):
                    continue
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                print(f"  [r2] {key}")
                client.download_file(bucket, key, local_path)


def upload_video(local_path, key=None):
    """Upload a video file to R2 and return a presigned URL (valid 7 days)."""
    client = _client()
    bucket = _bucket()

    if key is None:
        slug_dir = os.path.basename(os.path.dirname(local_path))
        filename = os.path.basename(local_path)
        key = f"output/{slug_dir}/{filename}"

    print(f"  [r2] Uploading → {key}")
    client.upload_file(
        local_path, bucket, key,
        ExtraArgs={"ContentType": "video/mp4"},
    )

    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=7 * 24 * 3600,
    )
    return url
