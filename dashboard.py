"""
dashboard.py
─────────────
Local web server for the human-in-the-loop LinkedIn review dashboard.
Run this script locally to approve, edit, reject, and sync posts to GitHub.

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
from src.compactor import MemoryCompactor
from src.post_history import PostHistory

class DualLogger:
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # Clear log file on server start
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
compactor = MemoryCompactor()


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    summary = mem.build_full_context_summary()
    compact = mem.load_compact_profile()
    history = mem.load_post_history()
    return jsonify({
        "summary": summary,
        "compact": compact,
        "history": history[-5:]  # last 5 logs
    })


@app.route("/api/queue", methods=["GET"])
def get_queue():
    return jsonify(mem.load_posts_queue())


@app.route("/api/queue/save", methods=["POST"])
def save_queue():
    data = request.json
    mem.save_posts_queue(data)
    # Trigger auto-sync in background thread
    trigger_background_sync()
    return jsonify({"status": "success", "message": "Queue updated. Sync triggered in background."})


def bg_replenish_task():
    try:
        print("\n[replenish] >>> Background replenishment worker thread started.")
        queue = mem.load_posts_queue()
        pending = queue.get("pending", [])
        needed = 10 - len(pending)
        print(f"[replenish] Current drafts in queue: {len(pending)}/10. Needed: {needed}")
        
        if needed <= 0:
            print("[replenish] Queue is already full (10 drafts). No generation needed.")
            return
            
        print("[replenish] Gathering profile and context to build generation prompt...")
        summary = mem.build_full_context_summary()
        topic = "See the recent context below — extract the most compelling story or insight." if summary["recent_context"] else "Share an insight from my professional background and achievements."
        
        print("[replenish] Loading recent post history to prevent AI repeating past topics...")
        past_posts_text = mem.load_recent_posts_history_text(limit=15)
        print(f"[replenish] Loaded {len(past_posts_text)} past posts for repetition blacklist.")
        
        print("[replenish] Loading compact profile (experiences, banned buzzwords, voice guidelines)...")
        compact_data = mem.load_compact_profile()
        
        print("[replenish] Initializing Google Gemini AIGenerator client...")
        ai = AIGenerator()
        
        print(f"[replenish] Requesting Gemini to generate {needed} brand-new drafts...")
        batch = ai.generate_post_batch(
            topic=topic,
            compact_profile=compact_data,
            recent_context=summary["recent_context"],
            past_posts=past_posts_text,
            batch_size=needed
        )
        
        if batch:
            print(f"[replenish] Gemini generated {len(batch)} valid draft(s). Storing to posts_queue.json...")
            queue = mem.load_posts_queue() # reload to prevent race condition overrides
            queue["pending"].extend(batch)
            mem.save_posts_queue(queue)
            print(f"[replenish] Success! Appended {len(batch)} drafts. New drafts total: {len(queue['pending'])}")
            
            # Trigger background sync to state branch on GitHub if token is set
            trigger_background_sync()
        else:
            print("[replenish] WARNING: Gemini replenishment returned 0 valid drafts after filters. Check Gemini API key validity or prompt constraints.")
    except Exception as e:
        print(f"[replenish] ERROR during draft replenishment: {e}")
        import traceback
        traceback.print_exc()

def trigger_background_replenish():
    threading.Thread(target=bg_replenish_task, daemon=True).start()


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
        
        # 1. Fetch current file SHA from state branch
        r = requests.get(f"{url}?ref=state", headers=headers, timeout=10)
        sha = None
        if r.ok:
            sha = r.json().get("sha")
            
        # 2. Upload file content to state branch
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
            
        put_r = requests.put(url, headers=headers, json=payload, timeout=15)
        if put_r.ok:
            print("[sync] Successfully auto-synced queue to GitHub state branch.")
        else:
            print(f"[sync] Failed to auto-sync queue: {put_r.text}")
    except Exception as e:
        print(f"[sync] Error during auto-sync: {e}")

def trigger_background_sync():
    threading.Thread(target=sync_to_github_api, daemon=True).start()


@app.route("/api/post/approve", methods=["POST"])
def approve_post():
    """Move a post from pending list to approved list, applying optional text updates first."""
    data = request.json or {}
    idx = int(data.get("index", 0))
    edited_text = data.get("post_text", "").strip()
    
    queue = mem.load_posts_queue()
    if idx < 0 or idx >= len(queue["pending"]):
        return jsonify({"status": "error", "message": "Invalid draft index."}), 400

    approved_item = queue["pending"].pop(idx)
    if edited_text:
        approved_item["post_text"] = edited_text
        
    queue["approved"].append(approved_item)
    mem.save_posts_queue(queue)
    
    # Trigger auto-sync and replenishment in background threads
    trigger_background_sync()
    trigger_background_replenish()
    
    return jsonify({"status": "success", "message": "Post approved. Sync and replenishment triggered in background."})


@app.route("/api/post/reject", methods=["POST"])
def reject_post():
    """Discard a pending draft and trigger a replenishment in the background."""
    idx = int(request.json.get("index", 0))
    queue = mem.load_posts_queue()
    
    if idx < 0 or idx >= len(queue["pending"]):
        return jsonify({"status": "error", "message": "Invalid draft index."}), 400

    # Pop/Discard it
    queue["pending"].pop(idx)
    mem.save_posts_queue(queue)

    # Trigger auto-sync and replenishment in background threads
    trigger_background_sync()
    trigger_background_replenish()

    return jsonify({
        "status": "success",
        "message": "Draft rejected. Sync and replenishment triggered in background."
    })


@app.route("/api/post/replenish", methods=["POST"])
def replenish_queue():
    """Replenish the pending drafts list back up to a target size of 10 in the background."""
    trigger_background_replenish()
    return jsonify({"status": "success", "message": "Replenishment triggered in background."})


@app.route("/api/memory/add", methods=["POST"])
def add_memory():
    """
    Accepts raw voice note text or thoughts, saves it as context,
    runs the compaction engine, and updates compact_profile.json.
    """
    data = request.json
    text = data.get("text", "").strip()
    
    if not text:
        return jsonify({"status": "error", "message": "No memory text provided."}), 400

    try:
        # 1. Save new text as context file YYYY-MM-DD
        mem.save_context(text)
        
        # 2. Trigger Memory Compacter
        compactor.compact_all(new_raw_input=text)
        
        return jsonify({"status": "success", "message": "Memory added and compacted successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Memory compaction failed: {e}"}), 500


@app.route("/api/github/sync", methods=["POST"])
def sync_github():
    """Runs git commands to commit queues & memory, and pushes to GitHub Actions."""
    try:
        # Check if it's a git repo
        if not Path(".git").exists():
            return jsonify({"status": "error", "message": "Project is not initialized as a Git Repository."}), 400

        # Stage files
        subprocess.run(["git", "add", "memory/"], check=True)
        
        # Commit (silently ignore if nothing to commit)
        result = subprocess.run(["git", "commit", "-m", "chore: sync approved queue from dashboard [skip ci]"], capture_output=True, text=True)
        
        # Push to remote branch
        push_res = subprocess.run(["git", "push"], capture_output=True, text=True)
        
        if push_res.returncode != 0:
            return jsonify({"status": "error", "message": f"Git Push failed: {push_res.stderr}"}), 500

        return jsonify({
            "status": "success",
            "message": "Approved updates committed and pushed to GitHub Actions successfully!"
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
        # Read last 1000 lines for efficiency
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            # return only the last 200 lines to keep request lightweight
            last_lines = "".join(lines[-200:])
            return jsonify({"logs": last_lines})
    except Exception as e:
        return jsonify({"logs": f"Error reading log file: {e}"})


@app.route("/api/image/upload", methods=["POST"])
def upload_image():
    """Uploads an image file, saves it to memory/images/, and returns its local path."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part in request."}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file."}), 400
        
    # Ensure folder exists
    img_dir = Path("memory/images")
    img_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file with a safe filename
    import time
    from werkzeug.utils import secure_filename
    
    filename = f"{int(time.time())}_{secure_filename(file.filename)}"
    file_path = img_dir / filename
    file.save(file_path)
    
    # Return relative path for posts_queue.json
    relative_path = f"memory/images/{filename}"
    return jsonify({
        "status": "success",
        "image_path": relative_path
    })

@app.route("/memory/images/<path:filename>")
def serve_image(filename):
    """Serves uploaded images statically for card previews in local mode."""
    return send_from_directory("memory/images", filename)


# ─── Launcher Helper ──────────────────────────────────────────────────────────

def launch_server():
    # Attempt to start the server on localhost:5000
    # Auto-open browser
    webbrowser.open("http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    launch_server()
