import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Playwright session directory (for storing login cookies/state)
SESSION_DIR = BASE_DIR / ".playwright_session"

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# LinkedIn URLs
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"

def is_configured() -> bool:
    """Check if the Gemini API key is configured."""
    return bool(GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY != "your_gemini_api_key_here")
