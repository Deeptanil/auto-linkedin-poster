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

    def upload_video(self, video_path_or_bytes: Path | bytes | str) -> str:
        """
        Initialize and upload a video to LinkedIn.
        """
        if isinstance(video_path_or_bytes, (str, Path)):
            with open(video_path_or_bytes, "rb") as f:
                video_bytes = f.read()
        else:
            video_bytes = video_path_or_bytes

        author_urn = self.get_member_urn()
        
        # 1. Initialize video upload session
        init_url = f"{config.LINKEDIN_API_BASE}/rest/videos?action=initializeUpload"
        init_payload = {
            "initializeUploadRequest": {
                "owner": author_urn,
                "fileSizeBytes": len(video_bytes)
            }
        }
        
        r = requests.post(
            init_url,
            headers=self._headers(),
            json=init_payload,
            timeout=30
        )
        self._raise_for_status(r)
        
        data = r.json()
        value = data.get("value", {})
        upload_instructions = value.get("uploadInstructions", [])
        upload_url = upload_instructions[0].get("uploadUrl") if upload_instructions else value.get("uploadUrl")
        video_urn = value.get("video")
        
        if not upload_url or not video_urn:
            raise LinkedInAPIError(200, f"initializeUpload video returned invalid response: {data}")
            
        # 2. PUT binary payload to uploadUrl
        put_headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        put_r = requests.put(
            upload_url,
            headers=put_headers,
            data=video_bytes,
            timeout=120
        )
        if not put_r.ok:
            raise LinkedInAPIError(put_r.status_code, f"Failed video upload to uploadUrl: {put_r.text[:500]}")
            
        return video_urn

    def create_video_post(
        self,
        text: str,
        video_urn: str,
        title: str = "Video Post",
        visibility: str = "PUBLIC",
    ) -> str:
        """
        Create a post containing a single video on LinkedIn.
        """
        author_urn = self.get_member_urn()

        payload = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "content": {
                "media": {
                    "id": video_urn,
                    "title": title
                }
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

        post_urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id", "unknown")
        return post_urn

    def upload_image(self, image_path_or_bytes: Path | bytes | str) -> str:
        """
        Initialize and upload an image to LinkedIn.
        Auto-converts WebP, BMP, TIFF, HEIC to PNG format if needed.
        """
        if isinstance(image_path_or_bytes, (str, Path)):
            path_obj = Path(image_path_or_bytes)
            with open(path_obj, "rb") as f:
                image_bytes = f.read()
            ext = path_obj.suffix.lower()
        else:
            image_bytes = image_path_or_bytes
            ext = ".png"

        # Auto-convert formats like WebP to PNG for full LinkedIn compatibility
        if ext in [".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif"]:
            try:
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(image_bytes))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
                print(f"  [linkedin_api] Auto-converted {ext} image to PNG ({len(image_bytes)} bytes)")
            except Exception as conv_err:
                print(f"  [linkedin_api] Warning: image format conversion failed: {conv_err}")

        author_urn = self.get_member_urn()
        
        # 1. Initialize upload session
        init_url = f"{config.LINKEDIN_API_BASE}/rest/images?action=initializeUpload"
        init_payload = {
            "initializeUploadRequest": {
                "owner": author_urn
            }
        }
        
        r = requests.post(
            init_url,
            headers=self._headers(),
            json=init_payload,
            timeout=30
        )
        self._raise_for_status(r)
        
        data = r.json()
        value = data.get("value", {})
        upload_url = value.get("uploadUrl")
        image_urn = value.get("image")
        
        if not upload_url or not image_urn:
            raise LinkedInAPIError(200, f"initializeUpload returned invalid response: {data}")
            
        # 2. PUT binary payload to uploadUrl
        put_headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        put_r = requests.put(
            upload_url,
            headers=put_headers,
            data=image_bytes,
            timeout=60
        )
        if not put_r.ok:
            raise LinkedInAPIError(put_r.status_code, f"Failed binary upload to uploadUrl: {put_r.text[:500]}")
            
        return image_urn

    def create_image_post(
        self,
        text: str,
        image_urn: str,
        visibility: str = "PUBLIC",
    ) -> str:
        """
        Create a post containing an image on LinkedIn.
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
            "content": {
                "media": {
                    "id": image_urn
                }
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

        post_urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id", "unknown")
        return post_urn

    def create_multi_image_post(
        self,
        text: str,
        image_urns: list[str],
        visibility: str = "PUBLIC",
    ) -> str:
        """
        Create a post containing multiple images (carousel) on LinkedIn.
        """
        author_urn = self.get_member_urn()

        images_payload = [{"id": urn} for urn in image_urns]

        payload = {
            "author":     author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution":             "MAIN_FEED",
                "targetEntities":               [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "multiImage": {
                    "images": images_payload
                }
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
