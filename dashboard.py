"""
dashboard.py
─────────────
Local web server for the LinkedIn review & post scheduling dashboard.
Run this script locally to create, approve, edit, reject, and sync posts to GitHub.

Technology Stack: Flask, HTML, CSS, JavaScript.
Launch via run_dashboard.bat.
"""

import sys
import os
import subprocess
import webbrowser
import threading
from pathlib import Path
from flask import Flask, jsonify, request, render_template, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
from src.memory_manager import MemoryManager
from src.ai_generator import AIGenerator
from src.post_history import PostHistory

class DualLogger:
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(f"--- Dashboard Local Server Log Started: {__import__('datetime').datetime.now()} ---\n")

    def write(self, message):
        try:
            self.terminal.write(message)
        except UnicodeEncodeError:
            try:
                encoding = self.terminal.encoding or 'utf-8'
                self.terminal.write(message.encode(encoding, errors='replace').decode(encoding))
            except Exception:
                pass
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def flush(self):
        self.terminal.flush()

# Redirect output streams
log_file = Path("memory/dashboard.log")
sys.stdout = DualLogger(log_file)
sys.stderr = sys.stdout

app = Flask(__name__, template_folder=".")
mem = MemoryManager()


def collect_blacklist_posts(queue: dict, exclude_pending_index: int | None = None) -> list[str]:
    """Build a repetition blacklist from posted history plus current queue contents."""
    blacklist = mem.load_recent_posts_history_text(limit=15)
    for section in ("approved", "pending"):
        for idx, item in enumerate(queue.get(section, [])):
            if section == "pending" and exclude_pending_index is not None and idx == exclude_pending_index:
                continue
            text = item.get("post_text", "").strip()
            if text:
                blacklist.append(text)
    return blacklist


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    summary = mem.build_full_context_summary()
    history = mem.load_post_history()
    return jsonify({
        "summary": summary,
        "history": history[-5:]
    })


@app.route("/api/queue", methods=["GET"])
def get_queue():
    return jsonify(mem.load_posts_queue())


@app.route("/api/queue/save", methods=["POST"])
def save_queue():
    data = request.json
    mem.save_posts_queue(data)
    trigger_background_sync()
    return jsonify({"status": "success", "message": "Queue updated. Sync triggered in background."})


def sync_to_github_api():
    """Uploads memory/posts_queue.json directly to the state branch via GitHub API if GITHUB_TOKEN is set."""
    token = config.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")
    repo = config.GITHUB_REPOSITORY or os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[sync] GitHub token or repository path not configured. Skipping background auto-sync.")
        return
        
    try:
        import base64
        import requests
        
        file_path = "memory/posts_queue.json"
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        
        r = requests.get(f"{url}?ref=state", headers=headers, timeout=10)
        sha = None
        if r.ok:
            sha = r.json().get("sha")
            
        with open(file_path, "r", encoding="utf-8") as f:
            content_str = f.read()
            
        encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
        
        payload = {
            "message": "chore: sync queue from local dashboard [skip ci]",
            "content": encoded,
            "branch": "state"
        }
        if sha:
            payload["sha"] = sha
            
        r_put = requests.put(url, headers=headers, json=payload, timeout=15)
        if r_put.ok:
            print("[sync] Successfully auto-synced posts_queue.json to GitHub state branch.")
        else:
            print(f"[sync] Auto-sync failed with status {r_put.status_code}: {r_put.text[:200]}")
    except Exception as e:
        print(f"[sync] Error during background auto-sync: {e}")


def trigger_background_sync():
    threading.Thread(target=sync_to_github_api, daemon=True).start()


@app.route("/api/post/generate_from_topic", methods=["POST"])
def generate_from_topic():
    """
    Given a topic or prompt, generate a single LinkedIn post draft and return it.
    """
    data = request.json or {}
    topic = data.get("topic", "").strip()
    target_index = data.get("index")
    
    if not topic:
        return jsonify({"status": "error", "message": "No topic or prompt text provided."}), 400

    try:
        queue = mem.load_posts_queue()
        exclude_pending_index = int(target_index) if target_index is not None else None
        blacklist_posts = collect_blacklist_posts(queue, exclude_pending_index=exclude_pending_index)
        
        ai = AIGenerator()
        batch = ai.generate_post_batch(
            topic=topic,
            tone="Auto",
            past_posts=blacklist_posts,
            batch_size=1,
            topic_is_source_of_truth=True,
        )
        
        if not batch:
            return jsonify({"status": "error", "message": "Gemini generation returned 0 valid drafts."}), 500
            
        generated_post = batch[0]
        
        return jsonify({
            "status": "success",
            "post_text": generated_post["post_text"],
            "reasoning": generated_post.get("reasoning", "Generated on-demand from topic.")
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Failed to generate post: {e}"}), 500


@app.route("/api/github/sync", methods=["POST"])
def sync_github():
    """Runs git commands to commit queues and push to remote repository."""
    try:
        if not Path(".git").exists():
            return jsonify({"status": "error", "message": "Project is not initialized as a Git Repository."}), 400

        subprocess.run(["git", "add", "memory/"], check=True)
        result = subprocess.run(["git", "commit", "-m", "chore: sync approved queue from dashboard [skip ci]"], capture_output=True, text=True)
        push_res = subprocess.run(["git", "push"], capture_output=True, text=True)
        
        if push_res.returncode != 0:
            return jsonify({"status": "error", "message": f"Git Push failed: {push_res.stderr}"}), 500

        return jsonify({
            "status": "success",
            "message": "Approved updates committed and pushed successfully!"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Sync process encountered an error: {e}"}), 500


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Retrieve the log file text output."""
    log_path = Path("memory/dashboard.log")
    if not log_path.exists():
        return jsonify({"logs": "No log file found."})
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            last_lines = "".join(lines[-200:])
            return jsonify({"logs": last_lines})
    except Exception as e:
        return jsonify({"logs": f"Error reading log file: {e}"})


@app.route("/api/image/upload", methods=["POST"])
def upload_image():
    """Uploads an image or video file, saves it to memory/images/, and returns its local path."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part in request."}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file."}), 400
        
    img_dir = Path("memory/images")
    img_dir.mkdir(parents=True, exist_ok=True)
    
    import time
    from werkzeug.utils import secure_filename
    
    filename = f"{int(time.time())}_{secure_filename(file.filename)}"
    file_path = img_dir / filename
    file.save(file_path)
    
    relative_path = f"memory/images/{filename}"
    return jsonify({
        "status": "success",
        "image_path": relative_path
    })


@app.route("/memory/images/<path:filename>")
def serve_image(filename):
    """Serves uploaded images/videos statically for card previews in local mode."""
    return send_from_directory("memory/images", filename)


def launch_server():
    webbrowser.open("http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    launch_server()
