"""
BamBam webhook server — receives page-published events and triggers video generation.

Start: python webhook.py
POST /webhook/page-published  {"client_id": "winbigmarketing", "notion_page_id": "xxx"}
GET  /health
"""
import os
import threading

from flask import Flask, request, jsonify

from main import load_config, load_settings, process_page
from modules.notion_reader import get_page_by_notion_id
from modules.assembler import set_ffmpeg_path

app = Flask(__name__)


def _run_pipeline(client_id, notion_page_id):
    try:
        cfg = load_config(client_id)
        settings = load_settings()
        set_ffmpeg_path(settings.get("ffmpeg_path", "ffmpeg"))
        
        field_map = cfg.get("notion_field_map")
        pages = get_page_by_notion_id(cfg["notion_api_key"], notion_page_id, field_map=field_map)
        
        if not pages:
            print(f"[webhook] No page found for {notion_page_id}")
            return
        process_page(pages[0], cfg, settings)
    except Exception as e:
        print(f"[webhook] Pipeline error for {notion_page_id}: {e}")


@app.route("/webhook/page-published", methods=["POST"])
def page_published():
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id")
    notion_page_id = data.get("notion_page_id")

    if not client_id or not notion_page_id:
        return jsonify({"error": "client_id and notion_page_id are required"}), 400

    thread = threading.Thread(
        target=_run_pipeline, args=(client_id, notion_page_id), daemon=True
    )
    thread.start()

    return jsonify({"status": "processing", "notion_page_id": notion_page_id}), 202


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"BamBam webhook listening on :{port}")
    app.run(host="0.0.0.0", port=port)
