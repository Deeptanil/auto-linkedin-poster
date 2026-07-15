"""
linkedin_api.py
────────────────
Official LinkedIn REST API client (Posts API — no browser, no Playwright).
Used by GitHub Actions for fully headless, reliable posting.

Docs: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


POSTS_URL   = f"{config.LINKEDIN_API_BASE}/rest/posts"
USERINFO_URL = f"{config.LINKEDIN_API_BASE}/v2/userinfo"


class LinkedInAPIError(Exception):
    """Raised when the LinkedIn API returns a non-2xx status."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"LinkedIn API error {status_code}: {message}")


class LinkedInAPI:
    def __init__(self, access_token: str | None = None, member_urn: str | None = None):
        self.access_token = access_token or config.LINKEDIN_ACCESS_TOKEN
        self.member_urn   = member_urn   or config.LINKEDIN_MEMBER_URN

        if not self.access_token:
            raise ValueError(
                "LinkedIn access token not set. "
                "Set LINKEDIN_ACCESS_TOKEN in your environment / GitHub Secrets."
            )

    # ─── Public Methods ───────────────────────────────────────────────────────

    def get_member_urn(self) -> str:
        """
        Fetch and return the member URN (urn:li:person:XXXX).
        Caches to self.member_urn so we don't call the API twice.
        """
        if self.member_urn:
            return self.member_urn

        r = requests.get(
            USERINFO_URL,
            headers=self._headers(),
            timeout=15,
        )
        self._raise_for_status(r)

        data = r.json()
        sub = data.get("sub")
        if not sub:
            raise LinkedInAPIError(200, f"userinfo returned no 'sub' field: {data}")

        self.member_urn = f"urn:li:person:{sub}"
        return self.member_urn

    def create_text_post(
        self,
        text: str,
        visibility: str = "PUBLIC",
    ) -> str:
        """
        Create a text-only post on LinkedIn.

        Parameters
        ----------
        text       : The post body (max ~3000 chars).
        visibility : "PUBLIC" or "CONNECTIONS".

        Returns
        -------
        str : The LinkedIn post URN (e.g. urn:li:share:XXXX)
        """
        author_urn = self.get_member_urn()

        payload = {
            "author":     author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution":             "MAIN_FEED",
                "targetEntities":               [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        r = requests.post(
            POSTS_URL,
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        self._raise_for_status(r)

        # The post URN is returned in the X-RestLi-Id header
        post_urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id", "unknown")
        return post_urn

    def add_first_comment(self, post_urn: str, comment_text: str) -> str:
        """
        Add a comment to a post (useful for dropping links — never put them in the body).

        Returns the comment URN.
        """
        # The comments endpoint uses the encoded post URN
        encoded_urn = requests.utils.quote(post_urn, safe="")
        url = f"{config.LINKEDIN_API_BASE}/rest/socialActions/{encoded_urn}/comments"

        author_urn = self.get_member_urn()
        payload = {
            "actor": author_urn,
            "message": {
                "text": comment_text,
            },
        }

        r = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        self._raise_for_status(r)
        return r.headers.get("x-restli-id", "unknown")

    # ─── Private Helpers ──────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization":            f"Bearer {self.access_token}",
            "LinkedIn-Version":         config.LINKEDIN_REST_VER,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type":             "application/json",
        }

    @staticmethod
    def _raise_for_status(r: requests.Response) -> None:
        if not r.ok:
            try:
                msg = r.json()
            except Exception:
                msg = r.text[:500]
            raise LinkedInAPIError(r.status_code, str(msg))
