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
import urllib.parse
import http.server
from datetime import datetime, timezone, timedelta
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


# ─── OAuth Token Generation Endpoints & Callback Server ──────────────────────
CALLBACK_PORT = 8765
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
AUTH_URL_BASE = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
REQUIRED_SCOPES = ["w_member_social", "openid", "profile", "email"]

oauth_lock = threading.Lock()
oauth_state = {
    "status": "idle",
    "auth_code": None,
    "error": None,
    "result": None,
    "client_id": "",
    "client_secret": ""
}


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global oauth_state
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        with oauth_lock:
            if "code" in params:
                oauth_state["auth_code"] = params["code"][0]
                oauth_state["status"] = "exchanging"
                body = b"<!DOCTYPE html><html><head><title>LinkedIn Auth</title></head><body style='font-family:sans-serif;text-align:center;padding:50px;background:#0b0c10;color:#66fcf1;'><h2>Success! LinkedIn Authorization Received.</h2><p style='color:#f5f7fa;'>You can close this tab and return to the Dashboard.</p></body></html>"
            elif "error" in params:
                err_desc = params.get("error_description", ["Authorization denied"])[0]
                oauth_state["error"] = err_desc
                oauth_state["status"] = "error"
                body = f"<!DOCTYPE html><html><body style='font-family:sans-serif;text-align:center;padding:50px;background:#0b0c10;color:#ff4757;'><h2>Authorization Error</h2><p style='color:#f5f7fa;'>{err_desc}</p></body></html>".encode("utf-8")
            else:
                body = b"<!DOCTYPE html><html><body><h2>Unexpected Callback</h2></body></html>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def update_env_file(env_keys: dict):
    env_path = Path(__file__).resolve().parent / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key_part = line.split("=")[0].strip()
            if key_part in env_keys:
                val = env_keys[key_part]
                new_lines.append(f'{key_part}="{val}"')
                updated_keys.add(key_part)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key, val in env_keys.items():
        if key not in updated_keys:
            new_lines.append(f'{key}="{val}"')

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    for k, v in env_keys.items():
        os.environ[k] = str(v)
        if hasattr(config, k):
            setattr(config, k, str(v))


def run_oauth_flow_background(client_id: str, client_secret: str):
    global oauth_state
    
    server = None
    try:
        server = http.server.HTTPServer(("localhost", CALLBACK_PORT), OAuthCallbackHandler)
        server.timeout = 1.0
        start_time = datetime.now()
        
        while True:
            with oauth_lock:
                if oauth_state["status"] in ("exchanging", "error"):
                    break
            if (datetime.now() - start_time).total_seconds() > 300:
                with oauth_lock:
                    oauth_state["status"] = "error"
                    oauth_state["error"] = "Authorization timed out (5 minutes)."
                break
            server.handle_request()
            
    except Exception as e:
        with oauth_lock:
            oauth_state["status"] = "error"
            oauth_state["error"] = f"Failed to start callback server on port {CALLBACK_PORT}: {e}"
        if server:
            try:
                server.server_close()
            except Exception:
                pass
        return

    with oauth_lock:
        code = oauth_state.get("auth_code")
        status = oauth_state.get("status")

    if status == "exchanging" and code:
        try:
            import requests
            token_res = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )

            if not token_res.ok:
                with oauth_lock:
                    oauth_state["status"] = "error"
                    oauth_state["error"] = f"Token exchange failed ({token_res.status_code}): {token_res.text[:200]}"
                return

            t_data = token_res.json()
            access_token = t_data.get("access_token")
            refresh_token = t_data.get("refresh_token", "")
            expires_in = int(t_data.get("expires_in", 5183944))
            refresh_expires_in = int(t_data.get("refresh_token_expires_in", 31536000))

            now = datetime.now(timezone.utc)
            access_expiry = (now + timedelta(seconds=expires_in)).isoformat()
            refresh_expiry = (now + timedelta(seconds=refresh_expires_in)).isoformat()

            member_urn = ""
            userinfo_res = requests.get(
                USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "LinkedIn-Version": "202606",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                timeout=15,
            )
            if userinfo_res.ok:
                sub = userinfo_res.json().get("sub", "")
                if sub:
                    member_urn = f"urn:li:person:{sub}"

            env_keys = {
                "LINKEDIN_CLIENT_ID": client_id,
                "LINKEDIN_CLIENT_SECRET": client_secret,
                "LINKEDIN_ACCESS_TOKEN": access_token,
                "LINKEDIN_REFRESH_TOKEN": refresh_token,
                "LINKEDIN_TOKEN_EXPIRY": access_expiry,
                "LINKEDIN_REFRESH_TOKEN_EXPIRY": refresh_expiry,
                "LINKEDIN_MEMBER_URN": member_urn,
            }
            update_env_file(env_keys)

            with oauth_lock:
                oauth_state["status"] = "success"
                oauth_state["result"] = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expiry": access_expiry,
                    "member_urn": member_urn,
                    "secrets_summary": env_keys
                }
        except Exception as e:
            with oauth_lock:
                oauth_state["status"] = "error"
                oauth_state["error"] = f"Token exchange process error: {e}"

    if server:
        try:
            server.server_close()
        except Exception:
            pass


@app.route("/api/token/info", methods=["GET"])
def get_token_info():
    """Retrieve current LinkedIn token status from environment/.env."""
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    expiry_str = os.getenv("LINKEDIN_TOKEN_EXPIRY", "")
    member_urn = os.getenv("LINKEDIN_MEMBER_URN", "")
    
    is_expired = False
    days_left = 0
    if expiry_str:
        try:
            expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            delta = expiry_dt - now_dt
            days_left = delta.days
            if delta.total_seconds() <= 0:
                is_expired = True
        except Exception:
            pass
            
    masked_token = f"{access_token[:8]}...{access_token[-6:]}" if len(access_token) > 15 else ""

    return jsonify({
        "client_id": client_id,
        "has_client_secret": bool(client_secret),
        "has_access_token": bool(access_token),
        "masked_access_token": masked_token,
        "token_expiry": expiry_str,
        "member_urn": member_urn,
        "is_expired": is_expired,
        "days_left": days_left,
        "redirect_uri": REDIRECT_URI
    })


@app.route("/api/token/start", methods=["POST"])
def start_token_auth():
    """Initiates the OAuth token flow."""
    global oauth_state
    data = request.json or {}
    client_id = data.get("client_id", "").strip() or os.getenv("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = data.get("client_secret", "").strip() or os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        return jsonify({
            "status": "error",
            "message": "LinkedIn Client ID and Client Secret are required."
        }), 400

    update_env_file({
        "LINKEDIN_CLIENT_ID": client_id,
        "LINKEDIN_CLIENT_SECRET": client_secret
    })

    with oauth_lock:
        oauth_state = {
            "status": "waiting",
            "auth_code": None,
            "error": None,
            "result": None,
            "client_id": client_id,
            "client_secret": client_secret
        }

    t = threading.Thread(target=run_oauth_flow_background, args=(client_id, client_secret), daemon=True)
    t.start()

    scope_str = " ".join(REQUIRED_SCOPES)
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": scope_str,
        "state": "linkedin_poster_dashboard",
    }
    auth_url = AUTH_URL_BASE + "?" + urllib.parse.urlencode(auth_params)

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    return jsonify({
        "status": "started",
        "auth_url": auth_url,
        "message": "OAuth server started on port 8765. Browser opened for LinkedIn authorization."
    })


@app.route("/api/token/poll", methods=["GET"])
def poll_token_auth():
    """Polls the background OAuth flow status."""
    with oauth_lock:
        st = oauth_state.copy()

    return jsonify({
        "status": st.get("status", "idle"),
        "error": st.get("error"),
        "result": st.get("result")
    })


@app.route("/api/token/save_manual", methods=["POST"])
def save_token_manual():
    """Manually saves token values to .env."""
    data = request.json or {}
    env_updates = {}
    
    for key in ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_ACCESS_TOKEN", "LINKEDIN_REFRESH_TOKEN", "LINKEDIN_MEMBER_URN", "LINKEDIN_TOKEN_EXPIRY"]:
        val = data.get(key, "").strip()
        if val:
            env_updates[key] = val

    if not env_updates:
        return jsonify({"status": "error", "message": "No valid token fields provided."}), 400

    update_env_file(env_updates)
    return jsonify({"status": "success", "message": "Token configuration updated and saved to .env!"})


def launch_server():
    webbrowser.open("http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    launch_server()

