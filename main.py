import argparse
import json
import os
import shutil

from modules.notion_reader import get_pending_pages, get_page_by_notion_id
from modules.page_scraper import extract_page_images, extract_page_text
from modules.image_downloader import download_images
from modules.image_generator import generate_images
from modules.script_generator import generate_script
from modules.tts import make_voiceover
from modules.assembler import assemble_video, set_ffmpeg_path
from modules.youtube_uploader import credentials_exist, build_metadata, upload_to_youtube
from modules.schema_injector import generate_video_schema
from modules.wordpress_updater import inject_video
from modules.notion_writer import update_page_status


def load_config(client_id):
    cfg = {}
    config_path = f"config/clients/{client_id}.json"
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
    else:
        cfg["client_id"] = client_id

    # Railway / production: env vars override anything in the JSON file
    env_map = {
        "notion_api_key":      "NOTION_API_KEY",
        "notion_database_id":  "NOTION_DATABASE_ID",
        "cartesia_api_key":    "CARTESIA_API_KEY",
        "anthropic_api_key":   "ANTHROPIC_API_KEY",
        "openai_api_key":      "OPENAI_API_KEY",
        "brand_name":          "BRAND_NAME",
        "broll_vertical":      "BROLL_VERTICAL",
        "wordpress_url":       "WORDPRESS_URL",
        "wordpress_username":  "WORDPRESS_USERNAME",
        "wordpress_app_password": "WORDPRESS_APP_PASSWORD",
    }
    for cfg_key, env_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val

    # Notion field map can come from env as JSON string
    if not cfg.get("notion_field_map") and os.environ.get("NOTION_FIELD_MAP"):
        cfg["notion_field_map"] = json.loads(os.environ["NOTION_FIELD_MAP"])

    if not cfg.get("assets_path"):
        cfg["assets_path"] = f"assets/clients/{client_id}"

    return cfg


def load_settings():
    with open("config/settings.json") as f:
        settings = json.load(f)
    # Allow ffmpeg path override via env var (Railway uses system ffmpeg)
    ffmpeg_env = os.environ.get("FFMPEG_PATH")
    if ffmpeg_env:
        settings["ffmpeg_path"] = ffmpeg_env
    return settings


def select_broll(vertical, override=None):
    broll_base = "assets/broll/by_vertical"

    # 1. Config override (e.g. "auto_transport" for any auto-related service)
    if override:
        d = os.path.join(broll_base, override)
        clips = _mp4s(d)
        if clips:
            return clips

    # 2. Exact slug match
    vertical_key = vertical.lower().replace(" ", "_")
    clips = _mp4s(os.path.join(broll_base, vertical_key))
    if clips:
        return clips

    # 3. Keyword fallback — find any broll dir whose name shares a word with the vertical
    if os.path.isdir(broll_base):
        words = set(vertical_key.split("_"))
        for dirname in os.listdir(broll_base):
            if words & set(dirname.split("_")):
                clips = _mp4s(os.path.join(broll_base, dirname))
                if clips:
                    return clips

    # 4. Generic fallback
    clips = _mp4s("assets/broll/generic")
    if clips:
        return clips

    # 5. Any available broll at all
    if os.path.isdir(broll_base):
        for dirname in os.listdir(broll_base):
            clips = _mp4s(os.path.join(broll_base, dirname))
            if clips:
                return clips

    return []


def _mp4s(directory):
    if not os.path.isdir(directory):
        return []
    return sorted([os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".mp4")])


def select_stock_images(vertical, count):
    vertical_key = vertical.lower().replace(" ", "_")
    images = []
    # Check assets/stock_images/by_vertical/[vertical]
    # It might have subfolders (like Nick's: aerial highways, etc.)
    base_dir = f"assets/stock_images/by_vertical/{vertical_key}"
    if os.path.isdir(base_dir):
        # Walk and find all images
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    images.append(os.path.join(root, f))
    
    import random
    if images:
        random.shuffle(images)
        return images[:count]
    return []


def process_page(page, cfg, settings, no_upload=False):
    slug = page["page_slug"] or page["notion_page_id"]
    work_dir = f"output/{slug}"
    images_dir = f"{work_dir}/images"
    os.makedirs(images_dir, exist_ok=True)

    # Brand name comes from client config
    brand_name = cfg.get("brand_name", "")
    page["brand_name"] = brand_name

    print(f"\n{'='*55}\n  {slug}\n{'='*55}")

    # Check for YouTube credentials FIRST if not in no_upload mode
    creds_path = cfg.get("youtube_credentials_path", "")
    if not no_upload and not credentials_exist(creds_path):
        print(f"  -> [SKIP] No YouTube credentials for {cfg['client_id']}. Skipping generation.")
        return

    try:
        # 1. Scrape images + text from page
        image_urls = []
        page_text = ""
        if page.get("page_url"):
            print("  -> Scraping page content...")
            image_urls = extract_page_images(page["page_url"], page["hero_image_url"])
            page_text = extract_page_text(page["page_url"])
            print(f"  -> Found {len(image_urls)} image(s), {len(page_text.split())} words of content")
        elif page.get("hero_image_url"):
            print("  -> No page URL — using Notion image URL directly")
            image_urls = [page["hero_image_url"]]

        # 2. Generate or use stock images if below threshold
        min_needed = settings["video"]["min_images_before_generate"]
        if len(image_urls) < min_needed:
            needed = min_needed - len(image_urls)
            print(f"  -> Only {len(image_urls)} image(s) — getting {needed} more...")
            
            # Try local stock first
            stock = select_stock_images(page["vertical"], needed)
            if stock:
                print(f"  -> Found {len(stock)} local stock images")
                image_urls.extend([f"file://{p}" for p in stock])
                needed -= len(stock)
            
            # Then generate via Kie.ai if still needed
            if needed > 0:
                kie_key = cfg.get("kie_api_key", "")
                if kie_key:
                    print(f"  -> Generating {needed} via Kie.ai...")
                    generated = generate_images(
                        city=page["geo_city"], state=page["geo_state"],
                        vertical=page["vertical"], count=needed,
                        output_dir=images_dir,
                        kie_api_key=kie_key,
                        kie_endpoint=settings["image_generation"]["kie_api_endpoint"],
                        prompt_template=settings["image_generation"]["prompt_template"]
                    )
                    image_urls.extend([f"file://{p}" for p in generated])
                else:
                    print("  -> No Kie.ai key — proceeding with available images")

        # 3. Download images
        print("  -> Downloading images...")
        local_images = download_images(
            [u for u in image_urls if not u.startswith("file://")], images_dir
        )
        for url in image_urls:
            if url.startswith("file://"):
                local_images.append(url.replace("file://", ""))

        if not local_images:
            raise Exception("No images available")

        all_images = local_images[:4]

        # 4. Generate script (Claude preferred, OpenAI fallback)
        print("  -> Generating script...")
        script_ok = False
        try:
            scenes, voiceover_text = generate_script(
                city=page["geo_city"], state=page["geo_state"],
                vertical=page["vertical"],
                unique_data=page_text or page.get("unique_data", ""),
                brand_name=brand_name,
                anthropic_api_key=cfg.get("anthropic_api_key") or None,
                openai_api_key=cfg.get("openai_api_key") or None,
                model=settings["script"]["model"]
            )
            script_ok = True
        except Exception as script_err:
            print(f"  -> Script generation failed ({script_err}) — using template fallback")
        if not script_ok:
            city = page["geo_city"]
            state = page["geo_state"]
            vertical = page["vertical"]
            scenes = {
                "hook":     f"Searching for {vertical} in {city}?",
                "problem":  f"Most people struggle to find someone they can actually trust.",
                "solution": f"{brand_name} delivers results that speak for themselves.",
                "trust":    f"Proudly serving {city}, {state} with proven expertise.",
                "cta":      f"Visit {brand_name} online and get started today.",
            }
            voiceover_text = " ".join(scenes.values())

        # 5. Voiceover
        print("  -> Generating voiceover...")
        voiceover_path = f"{work_dir}/voiceover.mp3"
        make_voiceover(
            text=voiceover_text,
            output_path=voiceover_path,
            cartesia_api_key=cfg.get("cartesia_api_key"),
            voice_id=cfg.get("cartesia_voice_id", settings["voiceover"]["default_voice"])
        )

        # 6. Assemble video
        print("  -> Assembling video...")
        assets = cfg["assets_path"]
        intro_path = f"{assets}/intro.mp4"
        outro_path = f"{assets}/outro.mp4"
        if not os.path.exists(intro_path) or not os.path.exists(outro_path):
            raise Exception(f"Missing intro/outro in {assets}/ — run: python setup_demo.py --client {cfg['client_id']} --brand \"{brand_name}\"")

        final_video = f"{work_dir}/final_video.mp4"
        assemble_video(
            image_paths=all_images,
            scenes=scenes,
            broll_paths=select_broll(page["vertical"], override=cfg.get("broll_vertical")),
            intro_path=intro_path,
            outro_path=outro_path,
            voiceover_path=voiceover_path,
            output_path=final_video,
            work_dir=work_dir,
            image_duration=settings["video"]["image_duration"],
            openai_api_key=cfg.get("openai_api_key")
        )
        print(f"  -> Video assembled: {final_video}")

        # 6b. Back up to R2
        r2_video_url = None
        if os.environ.get("R2_ENDPOINT_URL"):
            try:
                from modules.r2_sync import upload_video as r2_upload
                r2_video_url = r2_upload(final_video)
                print(f"  -> R2 URL: {r2_video_url}")
            except Exception as r2_err:
                print(f"  -> R2 upload failed: {r2_err}")

        # 7. Upload to YouTube
        youtube_video_id = None
        creds_path = cfg.get("youtube_credentials_path", "")

        if no_upload:
            print("  -> Skipping upload (--no-upload)")
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], 
                               status="ready_to_upload", field_map=cfg.get("notion_field_map"))
            print(f"  [OK] DONE (local): {final_video}")
            return

        if not credentials_exist(creds_path):
            print("  -> No YouTube credentials — marking ready_to_upload")
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], 
                               status="ready_to_upload", field_map=cfg.get("notion_field_map"))
            print(f"  [OK] DONE (local): {final_video}")
            return

        print("  -> Uploading to YouTube...")
        title, description, tags = build_metadata(
            city=page["geo_city"], state=page["geo_state"],
            vertical=page["vertical"], brand_name=brand_name,
            unique_data=page.get("unique_data", ""),
            page_url=page["page_url"],
            year=settings["youtube"]["year"]
        )
        youtube_video_id = upload_to_youtube(
            video_path=final_video, title=title, description=description,
            tags=tags, credentials_path=creds_path,
            category_id=settings["youtube"]["category_id"],
            privacy=cfg.get("video_privacy", "public")
        )
        print(f"  -> Uploaded: https://youtube.com/watch?v={youtube_video_id}")

        # 8. Inject into WordPress
        print("  -> Injecting into WordPress...")
        schema_html = generate_video_schema(page["page_url"], youtube_video_id, title, description)
        wp_post_id = page.get("wp_post_id") or None
        if wp_post_id:
            inject_video(cfg["wordpress_url"], wp_post_id, youtube_video_id,
                         schema_html, cfg["wordpress_username"], cfg["wordpress_app_password"])
        else:
            print("  [wp] No post ID — skipping WP injection")

        # 9. Write back to Notion
        print("  -> Updating Notion...")
        update_page_status(cfg["notion_api_key"], page["notion_page_id"],
                           youtube_video_id=youtube_video_id, status="done",
                           field_map=cfg.get("notion_field_map"))
        print(f"  [OK] DONE: {slug}")

    except Exception as e:
        print(f"  [FAIL] FAILED: {slug} — {e}")
        try:
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], 
                               status="failed", field_map=cfg.get("notion_field_map"))
        except Exception:
            pass

    finally:
        # Keep output folder when --no-upload so user can view the video
        if not no_upload and os.path.exists(work_dir):
            shutil.rmtree(work_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BamBam Video Engine")
    parser.add_argument("--client", required=True)
    parser.add_argument("--slug", help="Process single page by slug")
    parser.add_argument("--notion-id", help="Process single page by Notion page ID (demo mode)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.client)
    settings = load_settings()
    set_ffmpeg_path(settings.get("ffmpeg_path", "ffmpeg"))

    if args.notion_id:
        pages = get_page_by_notion_id(cfg["notion_api_key"], args.notion_id, field_map=cfg.get("notion_field_map"))
    else:
        pages = get_pending_pages(cfg["notion_api_key"], cfg["notion_database_id"], field_map=cfg.get("notion_field_map"))
        if args.slug:
            pages = [p for p in pages if p["page_slug"] == args.slug]
        if args.limit:
            pages = pages[:args.limit]

    print(f"\nBamBam Video Engine")
    print(f"Client : {args.client}")
    print(f"Pages  : {len(pages)}")

    for page in pages:
        process_page(page, cfg, settings, no_upload=args.no_upload)
