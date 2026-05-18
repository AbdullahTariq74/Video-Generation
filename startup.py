"""
Railway entry point — sync assets from R2, then start the webhook server.
"""
import os
import sys


def main():
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

    print("[startup] Starting webhook server...")
    os.execv(sys.executable, [sys.executable, "webhook.py"])


if __name__ == "__main__":
    main()
