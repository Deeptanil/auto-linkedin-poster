#!/usr/bin/env python3
"""
setup_token.py
───────────────
One-time local script to set up your LinkedIn OAuth2 tokens.
Run this on your local machine — it opens a browser so you can log in.

Usage:
    python scripts/setup_token.py

What it does:
  1. Prompts you for your LinkedIn App credentials
  2. Launches a temporary local server on port 8765
  3. Opens your browser to the LinkedIn authorization URL
  4. Catches the OAuth callback automatically
  5. Exchanges the code for access + refresh tokens
  6. Prints out all the values to store as GitHub Secrets

Requirements:
    pip install requests
"""

import sys
import os
import json
import webbrowser
import threading
import urllib.parse
import http.server
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

# ─── Constants ────────────────────────────────────────────────────────────────
CALLBACK_PORT    = 8765
REDIRECT_URI     = f"http://localhost:{CALLBACK_PORT}/callback"
AUTH_URL_BASE    = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL        = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL     = "https://api.linkedin.com/v2/userinfo"
REQUIRED_SCOPES  = ["w_member_social", "openid", "profile", "email"]

# ─── Shared state for the callback server ────────────────────────────────────
_auth_code  = None
_auth_error = None
_server_done = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth callback."""

    def do_GET(self):
        global _auth_code, _auth_error
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            body = b"<h2>Success! You can close this tab and return to the terminal.</h2>"
        elif "error" in params:
            _auth_error = params.get("error_description", ["Unknown error"])[0]
            body = f"<h2>Error: {_auth_error}</h2>".encode()
        else:
            body = b"<h2>Unexpected callback. Check your terminal.</h2>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _server_done.set()

    def log_message(self, *args):
        pass  # Suppress access log noise


def _run_callback_server():
    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.handle_request()  # Handle one request then stop
    server.server_close()


# ─── Main flow ────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 65)
    print("  LinkedIn OAuth Token Setup")
    print("  (Run once — tokens last 60 days, auto-refresh handles the rest)")
    print("=" * 65)
    print()

    # Step 1: Get credentials
    print("Step 1: LinkedIn App Credentials")
    print("-" * 40)
    print("You need a LinkedIn App to use the API. If you don't have one:")
    print("  1. Go to https://developer.linkedin.com/")
    print("  2. Create an App (associate with any company page, even a dummy one)")
    print("  3. Under 'Products', add 'Share on LinkedIn' + 'Sign In with LinkedIn'")
    print("  4. Under 'Auth', add this redirect URI:", REDIRECT_URI)
    print()

    client_id = input("Enter your LinkedIn App Client ID:     ").strip()
    if not client_id:
        print("Error: Client ID is required.")
        sys.exit(1)

    client_secret = input("Enter your LinkedIn App Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required.")
        sys.exit(1)

    # Step 2: Build auth URL
    scope_str = " ".join(REQUIRED_SCOPES)
    auth_params = {
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  REDIRECT_URI,
        "scope":         scope_str,
        "state":         "linkedin_poster_setup",
    }
    auth_url = AUTH_URL_BASE + "?" + urllib.parse.urlencode(auth_params)

    print()
    print("Step 2: Authorize the Application")
    print("-" * 40)
    print("Starting local callback server on port", CALLBACK_PORT)

    # Start callback server in a background thread
    t = threading.Thread(target=_run_callback_server, daemon=True)
    t.start()

    print("Opening browser for LinkedIn login...")
    webbrowser.open(auth_url)
    print()
    print("If the browser didn't open, go to this URL manually:")
    print(auth_url)
    print()
    print("Waiting for authorization callback...")

    # Wait for callback (up to 5 minutes)
    _server_done.wait(timeout=300)
    t.join(timeout=2)

    if _auth_error:
        print(f"\nError during authorization: {_auth_error}")
        sys.exit(1)

    if not _auth_code:
        print("\nError: No authorization code received. Did you complete the login?")
        sys.exit(1)

    print("✓ Authorization code received!")

    # Step 3: Exchange code for tokens
    print()
    print("Step 3: Exchanging code for tokens...")
    print("-" * 40)

    token_response = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "code":          _auth_code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if not token_response.ok:
        print(f"Error: Token exchange failed ({token_response.status_code})")
        print(token_response.text)
        sys.exit(1)

    token_data = token_response.json()
    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", 5183944)
    refresh_expires_in = token_data.get("refresh_token_expires_in", 31536000)  # 365 days default

    if not access_token:
        print("Error: No access_token in response:", token_data)
        sys.exit(1)

    # Calculate expiry datetimes
    now = datetime.now(timezone.utc)
    access_expiry  = now + timedelta(seconds=int(expires_in))
    refresh_expiry = now + timedelta(seconds=int(refresh_expires_in))

    access_expiry_iso  = access_expiry.isoformat()
    refresh_expiry_iso = refresh_expiry.isoformat()

    print("✓ Tokens received!")

    # Step 4: Get member URN
    print()
    print("Step 4: Fetching your LinkedIn Member URN...")
    print("-" * 40)

    userinfo_response = requests.get(
        USERINFO_URL,
        headers={
            "Authorization":             f"Bearer {access_token}",
            "LinkedIn-Version":          "202501",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        timeout=15,
    )

    member_urn = ""
    if userinfo_response.ok:
        sub = userinfo_response.json().get("sub", "")
        if sub:
            member_urn = f"urn:li:person:{sub}"
            print(f"✓ Member URN: {member_urn}")
        else:
            print("Warning: Could not extract member URN from userinfo response.")
            print("Response:", userinfo_response.json())
    else:
        print("Warning: Could not fetch member URN. You'll need to set it manually.")
        print(f"Status: {userinfo_response.status_code}")

    # Step 5: Print output
    print()
    print("=" * 65)
    print("  ✅ SUCCESS! Add these as GitHub Repository Secrets")
    print("  Go to: GitHub → Your Repo → Settings → Secrets → Actions → New")
    print("=" * 65)
    print()

    secrets = {
        "GEMINI_API_KEY":                "(get from aistudio.google.com/app/apikey — FREE)",
        "LINKEDIN_CLIENT_ID":            client_id,
        "LINKEDIN_CLIENT_SECRET":        client_secret,
        "LINKEDIN_ACCESS_TOKEN":         access_token,
        "LINKEDIN_REFRESH_TOKEN":        refresh_token or "(NOT PROVIDED — re-check your app's token settings)",
        "LINKEDIN_TOKEN_EXPIRY":         access_expiry_iso,
        "LINKEDIN_REFRESH_TOKEN_EXPIRY": refresh_expiry_iso,
        "LINKEDIN_MEMBER_URN":           member_urn or "(SET THIS MANUALLY — see above)",
        "DISCORD_WEBHOOK_URL":           "(get from Discord → Server Settings → Integrations → Webhooks)",
    }

    for key, value in secrets.items():
        print(f"  {key}:")
        print(f"    {value}")
        print()

    print()
    print("─" * 65)
    print("Token expiry summary:")
    print(f"  Access Token expires:  {access_expiry.strftime('%Y-%m-%d')} (~{expires_in // 86400} days)")
    print(f"  Refresh Token expires: {refresh_expiry.strftime('%Y-%m-%d')} (~{refresh_expires_in // 86400} days)")
    print()
    print("The system will auto-refresh your access token weekly.")
    print("You'll get a Discord warning 30 days before the refresh token expires.")
    print("─" * 65)
    print()

    # Save to local .env for local testing
    save = input("Save to local .env file for local testing? (y/N): ").strip().lower()
    if save == "y":
        env_path = Path(__file__).parent.parent / ".env"
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        # Update or append each key
        env_keys = {
            "LINKEDIN_CLIENT_ID":            client_id,
            "LINKEDIN_CLIENT_SECRET":        client_secret,
            "LINKEDIN_ACCESS_TOKEN":         access_token,
            "LINKEDIN_REFRESH_TOKEN":        refresh_token,
            "LINKEDIN_TOKEN_EXPIRY":         access_expiry_iso,
            "LINKEDIN_REFRESH_TOKEN_EXPIRY": refresh_expiry_iso,
            "LINKEDIN_MEMBER_URN":           member_urn,
        }

        updated_keys = set()
        new_lines = []
        for line in lines:
            key_part = line.split("=")[0].strip() if "=" in line else ""
            if key_part in env_keys:
                new_lines.append(f'{key_part}="{env_keys[key_part]}"')
                updated_keys.add(key_part)
            else:
                new_lines.append(line)

        for key, val in env_keys.items():
            if key not in updated_keys:
                new_lines.append(f'{key}="{val}"')

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"✓ Saved to {env_path}")

    print()
    print("Setup complete! 🎉")


if __name__ == "__main__":
    main()
