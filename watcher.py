"""
BamBam Watcher — Background worker that polls Notion every X minutes
to find new pages and trigger video generation.

Usage:
  python watcher.py --client simplecarship --interval 300
"""
import argparse
import time
import sys
import os

from main import load_config, load_settings, process_page
from modules.notion_reader import get_pending_pages
from modules.assembler import set_ffmpeg_path

def run_watcher(client_id, interval):
    print(f"--- BamBam Watcher Started for Client: {client_id} ---")
    print(f"--- Polling interval: {interval} seconds ---\n")
    
    try:
        cfg = load_config(client_id)
        settings = load_settings()
        set_ffmpeg_path(settings.get("ffmpeg_path", "ffmpeg"))
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return

    field_map = cfg.get("notion_field_map")

    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Checking Notion for pending pages...")
            
            # Fetch pages that are ready for video
            pages = get_pending_pages(
                cfg["notion_api_key"], 
                cfg["notion_database_id"], 
                field_map=field_map
            )
            
            if not pages:
                print(f"  -> No pending pages found. Sleeping for {interval}s...")
            else:
                print(f"  -> Found {len(pages)} pending page(s). Processing...")
                for page in pages:
                    try:
                        process_page(page, cfg, settings)
                    except Exception as pg_err:
                        print(f"  [ERROR] Failed to process page {page.get('page_slug')}: {pg_err}")
                
                print(f"\n  -> Batch complete. Sleeping for {interval}s...")

        except Exception as e:
            print(f"  [CRITICAL ERROR] Watcher loop encountered an issue: {e}")
            print("  Retrying in 60 seconds...")
            time.sleep(60)
            continue
            
        time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BamBam Background Watcher")
    parser.add_argument("--client", required=True, help="Client ID from config/clients/")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds (default 300)")
    args = parser.parse_args()

    run_watcher(args.client, args.interval)
