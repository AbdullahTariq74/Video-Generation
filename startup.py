"""
Railway/Render entry point:
  1. Sync assets from R2
  2. Start watcher (polls Notion every N seconds for queued pages)
  3. Start webhook server (Flask)
"""
import os
import threading


def main():
    # 1. Sync assets from R2
    if os.environ.get("R2_ENDPOINT_URL"):
        print("[startup] Syncing assets from R2...")
        try:
            from modules.r2_sync import download_assets
            download_assets()
            print("[startup] Assets ready.")
        except Exception as e:
            print(f"[startup] R2 sync warning: {e} — continuing with local assets")
    else:
        print("[startup] R2 not configured — using local assets")

    # 2. Start watcher in background thread
    client_id = os.environ.get("CLIENT_ID", "simplecarship")
    interval = int(os.environ.get("POLL_INTERVAL", "300"))

    from watcher import run_watcher
    watcher_thread = threading.Thread(
        target=run_watcher, args=(client_id, interval), daemon=True
    )
    watcher_thread.start()
    print(f"[startup] Watcher started for '{client_id}' (every {interval}s)")

    # 3. Start webhook server (main thread)
    from webhook import app
    port = int(os.environ.get("PORT", 8080))
    print(f"[startup] Webhook server listening on :{port}")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
