import argparse
import json
import os
import shutil

from modules.notion_reader import get_pending_pages, get_page_by_notion_id
from modules.page_scraper import extract_page_images
from modules.image_downloader import download_images
from modules.image_generator import generate_images
from modules.script_generator import generate_script
from modules.tts import make_voiceover
from modules.assembler import assemble_video, set_ffmpeg_path
from modules.youtube_uploader import credentials_exist, build_metadata, upload_to_youtube
from modules.schema_injector import generate_video_schema
from modules.wordpress_updater import inject_video
from modules.notion_writer import update_page_status
from modules.service_image import get_or_create_service_image, slugify
from modules.caption_overlay import add_title_overlay


def load_config(client_id):
    with open(f"config/clients/{client_id}.json") as f:
        return json.load(f)


def load_settings():
    with open("config/settings.json") as f:
        return json.load(f)


def select_broll(vertical):
    vertical_key = vertical.lower().replace(" ", "_")
    for broll_dir in [f"assets/broll/by_vertical/{vertical_key}", "assets/broll/generic"]:
        if os.path.isdir(broll_dir):
            clips = sorted([
                os.path.join(broll_dir, f)
                for f in os.listdir(broll_dir) if f.endswith(".mp4")
            ])
            if clips:
                return clips
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

    try:
        # 1. Scrape images from WordPress page
        print("  -> Scraping page images...")
        image_urls = extract_page_images(page["page_url"], page["hero_image_url"])
        print(f"  -> Found {len(image_urls)} image(s) on page")

        # 2. Generate missing images via Kie.ai if below threshold
        min_needed = settings["video"]["min_images_before_generate"]
        if len(image_urls) < min_needed:
            needed = min_needed - len(image_urls)
            print(f"  -> Only {len(image_urls)} image(s) — generating {needed} via Kie.ai...")
            kie_key = cfg.get("kie_api_key", "")
            if kie_key:
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

        # 3b. Service image — 1 professional cover per service, cached + reused
        service_slug = slugify(page["vertical"])
        service_img_dir = f"assets/services/{cfg['client_id']}/{service_slug}"
        print("  -> Getting service image...")
        service_img = get_or_create_service_image(
            service=page["vertical"],
            output_dir=service_img_dir,
            kie_api_key=cfg.get("kie_api_key") or None,
            kie_endpoint=settings["image_generation"]["kie_api_endpoint"],
        )

        # Build title card: service image + city/state translucent overlay
        title_card_path = os.path.join(work_dir, "title_card.jpg")
        add_title_overlay(
            service_img,
            page["vertical"],
            f"{page['geo_city']}, {page['geo_state']}",
            title_card_path,
        )

        # Title card is Scene 1; scraped images fill scenes 2-5
        all_images = [title_card_path] + local_images[:4]

        # 4. Generate script
        print("  -> Generating script...")
        anthropic_key = cfg.get("anthropic_api_key", "")
        script_ok = False
        if anthropic_key:
            try:
                scenes, voiceover_text = generate_script(
                    city=page["geo_city"], state=page["geo_state"],
                    vertical=page["vertical"],
                    unique_data=page.get("unique_data", ""),
                    brand_name=brand_name,
                    anthropic_api_key=anthropic_key,
                    model=settings["script"]["model"]
                )
                script_ok = True
            except Exception as script_err:
                print(f"  -> Script API failed ({script_err}) — using template fallback")
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
            broll_paths=select_broll(page["vertical"]),
            intro_path=intro_path,
            outro_path=outro_path,
            voiceover_path=voiceover_path,
            output_path=final_video,
            work_dir=work_dir,
            image_duration=settings["video"]["image_duration"]
        )
        print(f"  -> Video assembled: {final_video}")

        # 7. Upload to YouTube
        youtube_video_id = None
        creds_path = cfg.get("youtube_credentials_path", "")

        if no_upload:
            print("  -> Skipping upload (--no-upload)")
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], status="ready_to_upload")
            print(f"  [OK] DONE (local): {final_video}")
            return

        if not credentials_exist(creds_path):
            print("  -> No YouTube credentials — marking ready_to_upload")
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], status="ready_to_upload")
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
                           youtube_video_id=youtube_video_id, status="done")
        print(f"  [OK] DONE: {slug}")

    except Exception as e:
        print(f"  [FAIL] FAILED: {slug} — {e}")
        try:
            update_page_status(cfg["notion_api_key"], page["notion_page_id"], status="failed")
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
        pages = get_page_by_notion_id(cfg["notion_api_key"], args.notion_id)
    else:
        pages = get_pending_pages(cfg["notion_api_key"], cfg["notion_database_id"])
        if args.slug:
            pages = [p for p in pages if p["page_slug"] == args.slug]
        if args.limit:
            pages = pages[:args.limit]

    print(f"\nBamBam Video Engine")
    print(f"Client : {args.client}")
    print(f"Pages  : {len(pages)}")

    for page in pages:
        process_page(page, cfg, settings, no_upload=args.no_upload)
