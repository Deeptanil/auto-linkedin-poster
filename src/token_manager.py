"""
token_manager.py
─────────────────
Manages LinkedIn OAuth2 tokens:
  • Checks expiry of the access token and refresh token
  • Auto-refreshes the access token using the refresh token
  • Updates GitHub Secrets with the new token values
  • Sends Discord warnings before expiry

Environment variables consumed:
  LINKEDIN_ACCESS_TOKEN   — current access token
  LINKEDIN_REFRESH_TOKEN  — refresh token (expires in 365 days)
  LINKEDIN_TOKEN_EXPIRY   — ISO datetime of access token expiry
  LINKEDIN_CLIENT_ID      — your LinkedIn app client ID
  LINKEDIN_CLIENT_SECRET  — your LinkedIn app client secret
  GITHUB_TOKEN            — auto-provided by GitHub Actions
  GITHUB_REPOSITORY       — auto-provided by GitHub Actions (owner/repo)
  DISCORD_WEBHOOK_URL     — for notifications
"""

import sys
import json
import base64
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.discord_notifier import (
    notify_token_warning,
    notify_token_refreshed,
)

TOKEN_ENDPOINT = "https://www.linkedin.com/oauth/v2/accessToken"
# GitHub Secrets API
GH_SECRETS_API = "https://api.github.com/repos/{repo}/actions/secrets/{name}"
GH_PUBLIC_KEY_API = "https://api.github.com/repos/{repo}/actions/secrets/public-key"


class TokenManager:
    def __init__(self):
        self.access_token   = config.LINKEDIN_ACCESS_TOKEN
        self.refresh_token  = config.LINKEDIN_REFRESH_TOKEN
        self.token_expiry   = self._parse_expiry(config.LINKEDIN_TOKEN_EXPIRY)
        self.client_id      = config.LINKEDIN_CLIENT_ID
        self.client_secret  = config.LINKEDIN_CLIENT_SECRET
        self.github_token   = config.GITHUB_TOKEN
        self.repo           = config.GITHUB_REPOSITORY

    # ─── Public API ───────────────────────────────────────────────────────────

    def check_and_refresh(self) -> dict:
        """
        Full check-and-refresh cycle. Returns a status dict.

        Steps:
          1. Calculate days until access token expiry
          2. If within WARN threshold → send Discord warning
          3. If within REFRESH threshold → attempt auto-refresh
          4. Check refresh token expiry separately → warn if close
        """
        result = {
            "refreshed": False,
            "days_until_expiry": None,
            "warnings_sent": [],
            "errors": [],
        }

        if not self.token_expiry:
            result["errors"].append("LINKEDIN_TOKEN_EXPIRY not set — cannot check expiry.")
            return result

        now = datetime.now(timezone.utc)
        days_left = (self.token_expiry - now).days
        result["days_until_expiry"] = days_left

        print(f"[token_manager] Access token expires in {days_left} day(s).")

        # ── Warning zone ──────────────────────────────────────────────────────
        if days_left <= config.WARN_DAYS_BEFORE_EXPIRY:
            print(f"[token_manager] Sending expiry warning (≤ {config.WARN_DAYS_BEFORE_EXPIRY} days).")
            notify_token_warning(days_left, token_type="Access Token")
            result["warnings_sent"].append("access_token_warning")

        # ── Refresh zone ──────────────────────────────────────────────────────
        if days_left <= config.REFRESH_DAYS_BEFORE_EXPIRY:
            print(f"[token_manager] Attempting auto-refresh (≤ {config.REFRESH_DAYS_BEFORE_EXPIRY} days).")
            try:
                new_tokens = self._refresh_access_token()
                self._update_github_secrets(new_tokens)
                notify_token_refreshed(new_tokens["expiry_iso"])
                result["refreshed"] = True
                result["new_expiry"] = new_tokens["expiry_iso"]
            except Exception as e:
                msg = f"Auto-refresh failed: {e}"
                print(f"[token_manager] {msg}", file=sys.stderr)
                result["errors"].append(msg)

        # ── Refresh token expiry warning ──────────────────────────────────────
        # LinkedIn refresh tokens last 365 days from issuance.
        # We store the refresh token issue date implicitly via access token history.
        # As a proxy: if access token was just refreshed, refresh token is ~365 days old minus usage.
        # Best we can do without a separate expiry date: warn at 30-day intervals near year mark.
        self._check_refresh_token_expiry(result)

        return result

    def get_valid_access_token(self) -> str:
        """
        Return a valid access token. If expired or close to expiry, refresh first.
        For use by the posting flow to ensure a live token.
        """
        if not self.token_expiry:
            return self.access_token  # No expiry info, use as-is

        now = datetime.now(timezone.utc)
        days_left = (self.token_expiry - now).days

        if days_left <= 0:
            print("[token_manager] Access token expired. Refreshing...")
            new_tokens = self._refresh_access_token()
            self._update_github_secrets(new_tokens)
            return new_tokens["access_token"]

        return self.access_token

    # ─── LinkedIn OAuth Refresh ───────────────────────────────────────────────

    def _refresh_access_token(self) -> dict:
        """
        Use the refresh token to obtain a new access + refresh token pair.
        Returns dict: {access_token, refresh_token, expiry_iso}
        """
        if not self.refresh_token:
            raise ValueError("LINKEDIN_REFRESH_TOKEN not configured.")
        if not self.client_id or not self.client_secret:
            raise ValueError("LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET not configured.")

        r = requests.post(
            TOKEN_ENDPOINT,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )

        if not r.ok:
            raise RuntimeError(
                f"LinkedIn token refresh failed ({r.status_code}): {r.text[:300]}"
            )

        data = r.json()
        new_access  = data.get("access_token")
        new_refresh = data.get("refresh_token", self.refresh_token)  # may not be rotated
        expires_in  = data.get("expires_in", 5183944)  # default ~60 days in seconds

        if not new_access:
            raise RuntimeError(f"Refresh response missing access_token: {data}")

        expiry_dt  = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        expiry_iso = expiry_dt.isoformat()

        # Update internal state
        self.access_token  = new_access
        self.refresh_token = new_refresh
        self.token_expiry  = expiry_dt

        print(f"[token_manager] Token refreshed. New expiry: {expiry_iso}")
        return {
            "access_token":  new_access,
            "refresh_token": new_refresh,
            "expiry_iso":    expiry_iso,
        }

    # ─── GitHub Secrets Update ────────────────────────────────────────────────

    def _update_github_secrets(self, new_tokens: dict) -> None:
        """
        Update GitHub repository secrets with the new token values.
        Requires GITHUB_TOKEN with `secrets: write` permission.
        """
        if not self.github_token or not self.repo:
            print(
                "[token_manager] GITHUB_TOKEN or GITHUB_REPOSITORY not set — "
                "cannot auto-update secrets. Update them manually.",
                file=sys.stderr,
            )
            return

        pub_key_info = self._get_github_public_key()
        pub_key_id   = pub_key_info["key_id"]
        pub_key_val  = pub_key_info["key"]

        secrets_to_update = {
            "LINKEDIN_ACCESS_TOKEN":  new_tokens["access_token"],
            "LINKEDIN_REFRESH_TOKEN": new_tokens["refresh_token"],
            "LINKEDIN_TOKEN_EXPIRY":  new_tokens["expiry_iso"],
        }

        for secret_name, secret_value in secrets_to_update.items():
            encrypted = self._encrypt_secret(pub_key_val, secret_value)
            self._put_github_secret(secret_name, encrypted, pub_key_id)
            print(f"[token_manager] Updated GitHub Secret: {secret_name}")

    def _get_github_public_key(self) -> dict:
        url = GH_PUBLIC_KEY_API.format(repo=self.repo)
        r = requests.get(url, headers=self._gh_headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    def _put_github_secret(self, name: str, encrypted_value: str, key_id: str) -> None:
        url = GH_SECRETS_API.format(repo=self.repo, name=name)
        r = requests.put(
            url,
            headers=self._gh_headers(),
            json={"encrypted_value": encrypted_value, "key_id": key_id},
            timeout=15,
        )
        r.raise_for_status()

    def _gh_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
        """
        Encrypt a secret value using the repo's public key (libsodium sealed box).
        Required by the GitHub Secrets API.
        """
        try:
            from nacl import encoding, public as nacl_public
            pk_bytes = base64.b64decode(public_key_b64)
            pub_key  = nacl_public.PublicKey(pk_bytes)
            sealed   = nacl_public.SealedBox(pub_key)
            encrypted = sealed.encrypt(secret_value.encode("utf-8"))
            return base64.b64encode(encrypted).decode("utf-8")
        except ImportError:
            raise RuntimeError(
                "PyNaCl is required for secret encryption. "
                "Install it: pip install PyNaCl"
            )

    # ─── Refresh Token Expiry Warning ─────────────────────────────────────────

    def _check_refresh_token_expiry(self, result: dict) -> None:
        """
        LinkedIn refresh tokens last 365 days. We can't know the exact issue date
        without storing it, so we warn based on LINKEDIN_REFRESH_TOKEN_EXPIRY env var
        if set, or skip this check.
        """
        rt_expiry_str = __import__("os").getenv("LINKEDIN_REFRESH_TOKEN_EXPIRY", "")
        if not rt_expiry_str:
            return

        rt_expiry = self._parse_expiry(rt_expiry_str)
        if not rt_expiry:
            return

        now = datetime.now(timezone.utc)
        days_left = (rt_expiry - now).days

        print(f"[token_manager] Refresh token expires in {days_left} day(s).")

        if days_left <= config.WARN_DAYS_BEFORE_REFRESH_EXPIRY:
            print(f"[token_manager] Sending refresh token warning (≤ {config.WARN_DAYS_BEFORE_REFRESH_EXPIRY} days).")
            notify_token_warning(days_left, token_type="Refresh Token")
            result["warnings_sent"].append("refresh_token_warning")

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_expiry(expiry_str: str) -> datetime | None:
        if not expiry_str:
            return None
        try:
            dt = datetime.fromisoformat(expiry_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            print(f"[token_manager] Could not parse LINKEDIN_TOKEN_EXPIRY: {expiry_str!r}")
            return None
