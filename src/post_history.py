"""
post_history.py
────────────────
Logs every published post to memory/post_history.json and commits it
back to the repository so you have a permanent record.
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.memory_manager import MemoryManager


class PostHistory:
    def __init__(self):
        self.memory = MemoryManager()

    def log(
        self,
        post_text: str,
        post_urn: str,
        tone: str,
        context_date: str | None = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Add an entry to the post history log.

        Returns the new history entry dict.
        """
        history = self.memory.load_post_history()

        entry = {
            "id":           len(history) + 1,
            "posted_at":    datetime.now(timezone.utc).isoformat(),
            "post_urn":     post_urn,
            "tone":         tone,
            "context_date": context_date,
            "dry_run":      dry_run,
            "preview":      post_text[:200] + ("…" if len(post_text) > 200 else ""),
        }

        history.append(entry)
        self.memory.save_post_history(history)
        return entry

    def get_last_post_date(self) -> str | None:
        """Return the ISO date string of the last posted entry, or None."""
        history = self.memory.load_post_history()
        if not history:
            return None
        last = [e for e in history if not e.get("dry_run")]
        if not last:
            return None
        return last[-1].get("posted_at", "")[:10]  # YYYY-MM-DD

    def already_posted_today(self) -> bool:
        """True if a real (non-dry-run) post was already made today (in Asia/Kolkata timezone)."""
        history = self.memory.load_post_history()
        real = [e for e in history if not e.get("dry_run")]
        if not real:
            return False
            
        last_entry = real[-1]
        posted_at_str = last_entry.get("posted_at")
        if not posted_at_str:
            return False

        try:
            import zoneinfo
            # Parse UTC timestamp and convert to IST
            dt_utc = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00"))
            tz_ist = zoneinfo.ZoneInfo("Asia/Kolkata")
            dt_ist = dt_utc.astimezone(tz_ist)
            
            today_ist = datetime.now(tz_ist).date()
            return dt_ist.date() == today_ist
        except Exception as e:
            print(f"[post_history] Warning: failed parsing post date '{posted_at_str}': {e}")
            return posted_at_str[:10] == datetime.now(timezone.utc).date().isoformat()

    def print_recent(self, n: int = 5) -> None:
        history = self.memory.load_post_history()
        real = [e for e in history if not e.get("dry_run")]
        recent = real[-n:]
        for entry in reversed(recent):
            print(f"  [{entry['posted_at'][:10]}] #{entry['id']} ({entry['tone']}) — {entry['preview'][:80]}…")
