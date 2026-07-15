import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (local dev only)
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / ".playwright_session"
MEMORY_DIR = BASE_DIR / "memory"
CONTEXTS_DIR = MEMORY_DIR / "contexts"
SRC_DIR = BASE_DIR / "src"

# ─── Gemini (AI) ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"

# ─── LinkedIn API ─────────────────────────────────────────────────────────────
LINKEDIN_ACCESS_TOKEN  = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_REFRESH_TOKEN = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
LINKEDIN_TOKEN_EXPIRY  = os.getenv("LINKEDIN_TOKEN_EXPIRY", "")   # ISO datetime str
LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_MEMBER_URN    = os.getenv("LINKEDIN_MEMBER_URN", "")     # urn:li:person:XXXX

LINKEDIN_API_BASE   = "https://api.linkedin.com"
LINKEDIN_REST_VER   = "202501"     # bump this ~monthly if needed
LINKEDIN_FEED_URL   = "https://www.linkedin.com/feed/"

# ─── GitHub (for auto-updating Secrets) ───────────────────────────────────────
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN", "")         # built-in in Actions
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")    # owner/repo

# ─── Discord Notifications ────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ─── Automation Settings ──────────────────────────────────────────────────────
# Days before token expiry to start warning
WARN_DAYS_BEFORE_EXPIRY         = int(os.getenv("WARN_DAYS_BEFORE_EXPIRY", "14"))
REFRESH_DAYS_BEFORE_EXPIRY      = int(os.getenv("REFRESH_DAYS_BEFORE_EXPIRY", "10"))
WARN_DAYS_BEFORE_REFRESH_EXPIRY = int(os.getenv("WARN_DAYS_BEFORE_REFRESH_EXPIRY", "30"))

# ─── Validation Helpers ───────────────────────────────────────────────────────
def is_gemini_configured() -> bool:
    return bool(GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY != "your_gemini_api_key_here")

def is_linkedin_configured() -> bool:
    return bool(LINKEDIN_ACCESS_TOKEN and LINKEDIN_ACCESS_TOKEN.strip())

def is_discord_configured() -> bool:
    return bool(DISCORD_WEBHOOK_URL and DISCORD_WEBHOOK_URL.strip())

# Legacy alias used by old main.py
def is_configured() -> bool:
    return is_gemini_configured()
