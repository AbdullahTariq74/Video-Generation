import argparse
import json
import os
import shutil

from modules.notion_reader import get_pending_pages
from modules.page_scraper import extract_page_images
from modules.image_downloader import download_images
from modules.image_generator import generate_images
from modules.script_generator import generate_script
from modules.tts import make_voiceover
from modules.assembler import assemble_video
from modules.youtube_uploader import credentials_exist, build_metadata, upload_to_youtube
from modules.schema_injector import generate_video_schema
from modules.wordpress_updater import get_post_id_by_slug, inject_video
from modules.notion_writer import update_page_status


def load_config(client_id):
    path = f"config/clients/{client_id}.json"
    with open(path) as f:
        return json.load(f)


def load_settings():
    with open("config/settings.json") as f:
        return json.load(f)


def select_broll(assets_path, vertical):
    vertical_key = vertical.lower().replace(" ", "_")
    vertical_dir = f"assets/broll/by_vertical/{vertical_key}"
    generic_dir = "assets/broll/generic"

    for broll_dir in [vertical_dir, generic_dir]:
        if os.path.isdir(broll_dir):
            clips = sorted([
                os.path.join(broll_dir, f)
                for f in os.listdir(broll_dir)
                if f.endswith(".mp4")
            ])
            if clips:
                return clips
    return []


def process_page(page, cfg, settings, no_upload=False):
    slug = page["page_slug"]
    work_dir = f"output/{slug}"
    images_dir = f"{work_dir}/images"
    os.makedirs(images_dir, exist_ok=True)

    print(f"\n{'='*55}\n  {slug}\n{'='*55}")

    try:
        # 1. Get image URLs from WordPress page
        print("  → Scraping page images...")
        image_urls = extract_page_images(page["page_url"], page["hero_image_url"])
        print(f"  → Found {len(image_urls)} image(s) on page")

        # 2. Generate missing images via Kie.ai if below threshold
        min_needed = settings["video"]["min_images_before_generate"]
        if len(image_urls) < min_needed:
            needed = min_needed - len(image_urls)
            print(f"  → Only {len(image_urls)} image(s) — generating {needed} via Kie.ai...")
            kie_key = cfg.get("kie_api_key", "")
            kie_endpoint = settings["image_generation"]["kie_api_endpoint"]
            prompt_template = settings["image_generation"]["prompt_template"]
            if kie_key:
                generated = generate_images(
                    city=page["geo_city"], state=page["geo_state"],
                    vertical=page["vertical"], count=needed,
                    output_dir=images_dir, kie_api_key=kie_key,
                    kie_endpoint=kie_endpoint, prompt_template=prompt_template
                )
                # generated returns local paths; add placeholder URLs for download step
                image_urls.extend([f"file://{p}" for p in generated])
            else:
                print("  → No Kie.ai key configured — proceeding with available images")

        # 3. Download images locally
        print("  → Downloading images...")
        local_images = download_images(
            [u for u in image_urls if not u.startswith("file://")],
            images_dir
        )
        # Include any already-local Kie.ai paths
        for url in image_urls:
            if url.startswith("file://"):
                local_images.append(url.replace("file://", ""))

        if not local_images:
            raise Exception("No images available after download + generation")

        # 4. Generate voiceover script
        print("  → Generating script...")
        anthropic_key = cfg.get("anthropic_api_key", "")
        if anthropic_key:
            scenes, voiceover_text = generate_script(
                city=page["geo_city"], state=page["geo_state"],
                vertical=page["vertical"], unique_data=page["unique_data"],
                brand_name=page["brand_name"], anthropic_api_key=anthropic_key,
                model=settings["script"]["model"]
            )
        else:
            print("  → No Anthropic key — using template script")
            voiceover_text = (
                f"Looking for {page['vertical']} in {page['geo_city']}, {page['geo_state']}? "
                f"{page['brand_name']} has you covered. "
                f"{page['unique_data']}. "
                f"Trusted, professional, and ready when you need us. "
                f"Visit our website to learn more or book today."
            )
            scenes = {"hook": "", "problem": "", "solution": "", "trust": "", "cta": ""}

        # 5. Generate voiceover audio
        print("  → Generating voiceover...")
        voiceover_path = f"{work_dir}/voiceover.mp3"
        make_voiceover(
            text=voiceover_text,
            output_path=voiceover_path,
            cartesia_api_key=cfg.get("cartesia_api_key"),
            voice_id=cfg.get("cartesia_voice_id", settings["voiceover"]["default_voice"])
        )

        # 6. Assemble video
        print("  → Assembling video...")
        assets = cfg["assets_path"]
        intro_path = f"{assets}/intro.mp4"
        outro_path = f"{assets}/outro.mp4"

        if not os.path.exists(intro_path) or not os.path.exists(outro_path):
            raise Exception(f"Missing intro/outro in {assets}/ — add intro.mp4 and outro.mp4")

        broll_clips = select_broll(assets, page["vertical"])
        final_video = f"{work_dir}/final_video.mp4"

        assemble_video(
            image_paths=local_images[:5],
            scenes=scenes,
            broll_paths=broll_clips,
            intro_path=intro_path,
            outro_path=outro_path,
            voiceover_path=voiceover_path,
            output_path=final_video,
            work_dir=work_dir,
            image_duration=settings["video"]["image_duration"]
        )
        print(f"  → Video assembled: {final_video}")

        # 7. Upload to YouTube (skipped if no credentials or --no-upload flag)
        youtube_video_id = None
        creds_path = cfg.get("youtube_credentials_path", "")

        if no_upload:
            print("  → Skipping upload (--no-upload flag)")
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], status="ready_to_upload")
            print(f"  ✅ DONE (local only): {slug}")
            return

        if not credentials_exist(creds_path):
            print("  → No YouTube credentials — marking ready_to_upload")
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], status="ready_to_upload")
            print(f"  ✅ DONE (local only): {slug}")
            return

        print("  → Uploading to YouTube...")
        title, description, tags = build_metadata(
            city=page["geo_city"], state=page["geo_state"],
            vertical=page["vertical"], brand_name=page["brand_name"],
            unique_data=page["unique_data"], page_url=page["page_url"],
            year=settings["youtube"]["year"]
        )
        youtube_video_id = upload_to_youtube(
            video_path=final_video, title=title, description=description,
            tags=tags, credentials_path=creds_path,
            category_id=settings["youtube"]["category_id"],
            privacy=cfg.get("video_privacy", "public")
        )
        print(f"  → Uploaded: https://youtube.com/watch?v={youtube_video_id}")

        # 8. Inject embed + schema into WordPress
        print("  → Injecting into WordPress...")
        schema_html = generate_video_schema(page["page_url"], youtube_video_id, title, description)
        post_id = get_post_id_by_slug(
            cfg["wordpress_url"], slug,
            cfg["wordpress_username"], cfg["wordpress_app_password"]
        )
        if post_id:
            inject_video(cfg["wordpress_url"], post_id, youtube_video_id,
                         schema_html, cfg["wordpress_username"], cfg["wordpress_app_password"])
        else:
            print(f"  [wp] Warning: could not find WordPress post for slug '{slug}'")

        # 9. Update Notion
        print("  → Updating Notion...")
        update_page_status(cfg["notion_api_key"], page["notion_page_id"],
                           youtube_video_id=youtube_video_id, status="done")
        print(f"  ✅ DONE: {slug}")

    except Exception as e:
        print(f"  ❌ FAILED: {slug} — {e}")
        try:
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], status="failed")
        except Exception:
            pass

    finally:
        if os.path.exists(images_dir):
            shutil.rmtree(images_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BamBam Video Engine")
    parser.add_argument("--client", required=True, help="Client ID (matches config/clients/<id>.json)")
    parser.add_argument("--slug", help="Process a single page by slug")
    parser.add_argument("--limit", type=int, help="Max number of pages to process")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload, produce local video only")
    args = parser.parse_args()

    cfg = load_config(args.client)
    settings = load_settings()

    pages = get_pending_pages(cfg["notion_api_key"], cfg["notion_database_id"])

    if args.slug:
        pages = [p for p in pages if p["page_slug"] == args.slug]
    if args.limit:
        pages = pages[:args.limit]

    print(f"\nBamBam Video Engine")
    print(f"Client : {args.client}")
    print(f"Pages  : {len(pages)} pending")

    for page in pages:
        process_page(page, cfg, settings, no_upload=args.no_upload)
