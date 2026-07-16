"""
discord_notifier.py
────────────────────
Sends rich Discord embed notifications via a webhook URL.
Used for:
  • Token expiry warnings
  • Successful post confirmations
  • Error alerts
All notifications are no-ops if DISCORD_WEBHOOK_URL is not configured.
"""

import sys
import requests
from datetime import datetime

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import config


# ─── Colour constants (Discord embed colours) ─────────────────────────────────
COLOUR_SUCCESS = 0x57F287  # Green
COLOUR_WARNING = 0xFEE75C  # Yellow
COLOUR_DANGER  = 0xED4245  # Red
COLOUR_INFO    = 0x5865F2  # Blurple


def _send(payload: dict) -> bool:
    """
    Send a raw payload to the configured Discord webhook.
    Returns True on success, False on failure (never raises).
    """
    if not config.is_discord_configured():
        return False

    try:
        r = requests.post(
            config.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[discord_notifier] Failed to send notification: {e}", file=sys.stderr)
        return False


def _build_embed(
    title: str,
    description: str,
    colour: int,
    fields: list[dict] | None = None,
    footer: str = "LinkedIn Auto-Poster",
) -> dict:
    embed: dict = {
        "title": title,
        "description": description,
        "color": colour,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": footer},
    }
    if fields:
        embed["fields"] = fields
    return embed


# ─── Public notification functions ────────────────────────────────────────────

def notify_post_success(post_preview: str, post_urn: str = None) -> bool:
    """Notify that a LinkedIn post was published successfully."""
    preview = post_preview[:300] + ("…" if len(post_preview) > 300 else "")
    
    fields = []
    if post_urn and post_urn != "DRY_RUN" and post_urn != "unknown":
        post_url = f"https://www.linkedin.com/feed/update/{post_urn}"
        fields.append({
            "name": "🔗 Link",
            "value": f"[Open LinkedIn Post]({post_url})",
            "inline": False
        })
        
    payload = {
        "embeds": [
            _build_embed(
                title="✅ LinkedIn Post Published!",
                description=f"```\n{preview}\n```",
                colour=COLOUR_SUCCESS,
                fields=fields if fields else None
            )
        ]
    }
    return _send(payload)


def notify_queue_warning(remaining_days: int) -> bool:
    """Notify that the approved queue is running low."""
    payload = {
        "embeds": [
            _build_embed(
                title="⚠️ Approved Post Queue Running Low",
                description=(
                    f"You have only **{remaining_days} day(s)** of posts remaining in the approved queue.\n\n"
                    "Please log into the dashboard, review pending drafts, and approve more posts to prevent scheduling gaps!"
                ),
                colour=COLOUR_WARNING,
            )
        ]
    }
    return _send(payload)


def notify_queue_empty_reminder() -> bool:
    """Send a daily reminder that there are 0 approved posts in the queue."""
    payload = {
        "embeds": [
            _build_embed(
                title="🚨 Approved Post Queue is EMPTY!",
                description=(
                    "The daily LinkedIn posting workflow ran but skipped posting because there are **0 approved posts** left.\n\n"
                    "Please log into the dashboard and approve new drafts immediately to resume scheduled posting!"
                ),
                colour=COLOUR_DANGER,
            )
        ]
    }
    return _send(payload)


def notify_post_error(error_msg: str) -> bool:
    """Notify that the posting workflow failed."""
    payload = {
        "embeds": [
            _build_embed(
                title="❌ LinkedIn Post FAILED",
                description=(
                    "The daily LinkedIn posting workflow encountered an error.\n"
                    "**Check your GitHub Actions logs for details.**"
                ),
                colour=COLOUR_DANGER,
                fields=[{"name": "Error", "value": f"```{error_msg[:500]}```", "inline": False}],
            )
        ]
    }
    return _send(payload)


def notify_token_warning(days_left: int, token_type: str = "Access Token") -> bool:
    """Warn that a LinkedIn OAuth token is expiring soon."""
    if days_left <= 7:
        colour = COLOUR_DANGER
        urgency = "🚨 URGENT"
    else:
        colour = COLOUR_WARNING
        urgency = "⚠️ Warning"

    payload = {
        "embeds": [
            _build_embed(
                title=f"{urgency}: LinkedIn {token_type} Expiring in {days_left} Days",
                description=(
                    f"Your LinkedIn **{token_type}** will expire in **{days_left} day(s)**.\n\n"
                    + _get_token_action_text(token_type, days_left)
                ),
                colour=colour,
                fields=[
                    {
                        "name": "📋 What to do",
                        "value": (
                            "Run `python scripts/setup_token.py` locally, then update "
                            "your GitHub Secrets:\n"
                            "`LINKEDIN_ACCESS_TOKEN`\n"
                            "`LINKEDIN_REFRESH_TOKEN`\n"
                            "`LINKEDIN_TOKEN_EXPIRY`"
                        ),
                        "inline": False,
                    }
                ],
            )
        ]
    }
    return _send(payload)


def notify_token_refreshed(new_expiry: str) -> bool:
    """Confirm that the access token was auto-refreshed successfully."""
    payload = {
        "embeds": [
            _build_embed(
                title="🔄 LinkedIn Access Token Auto-Refreshed",
                description=(
                    "Your LinkedIn access token was refreshed automatically.\n"
                    f"New expiry: **{new_expiry}**"
                ),
                colour=COLOUR_INFO,
            )
        ]
    }
    return _send(payload)


def notify_no_context() -> bool:
    """Warn that no context was found for today's post."""
    payload = {
        "embeds": [
            _build_embed(
                title="📭 No Context for Today's Post",
                description=(
                    "The daily LinkedIn poster ran but found **no context file** for today.\n\n"
                    "To add context, go to **GitHub Actions → Add Context / Memory** "
                    "and fill in what you've been up to.\n\n"
                    "The post will be skipped today to avoid generic content."
                ),
                colour=COLOUR_WARNING,
            )
        ]
    }
    return _send(payload)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_token_action_text(token_type: str, days_left: int) -> str:
    if "Refresh" in token_type:
        return (
            "The refresh token is used to automatically renew your access token. "
            "Once it expires, **automatic posting will stop** until you re-authenticate.\n\n"
            "You will need to run the OAuth setup script manually **once per year**."
        )
    if days_left <= 10:
        return (
            "The system will attempt an **automatic refresh** using your refresh token. "
            "If that fails, you must re-authenticate manually."
        )
    return (
        "The system will attempt an automatic refresh soon. "
        "No action needed unless the refresh fails."
    )
