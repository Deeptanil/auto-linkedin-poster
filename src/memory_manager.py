"""
memory_manager.py
──────────────────
Reads and merges all persistent memory sources into a single context
object that the AI generator can use.

Memory sources (in priority order):
  1. voice_profile.md    — your personal writing style / voice
  2. achievements.md     — your running list of accomplishments
  3. contexts/           — dated context files you push (most recent wins)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


class MemoryManager:
    def __init__(self):
        self.memory_dir   = config.MEMORY_DIR
        self.contexts_dir = config.CONTEXTS_DIR

    # ─── Public API ───────────────────────────────────────────────────────────

    def load_voice_profile(self) -> str:
        """Return the voice profile markdown, or an empty string if not set."""
        path = self.memory_dir / "voice_profile.md"
        return self._read_file(path)

    def load_achievements(self) -> str:
        """Return the achievements markdown."""
        path = self.memory_dir / "achievements.md"
        return self._read_file(path)

    def load_recent_context(self, max_files: int = 3) -> str:
        """
        Load the most recent N context files and merge them.
        Returns an empty string if no context files exist.
        """
        if not self.contexts_dir.exists():
            return ""

        context_files = sorted(
            [f for f in self.contexts_dir.glob("*.md") if f.stat().st_size > 5],
            reverse=True   # newest first (YYYY-MM-DD.md sorts correctly)
        )

        if not context_files:
            return ""

        merged_parts = []
        for cf in context_files[:max_files]:
            content = self._read_file(cf)
            if content:
                date_label = cf.stem  # e.g. "2026-07-15"
                merged_parts.append(f"--- Context from {date_label} ---\n{content}")

        return "\n\n".join(merged_parts)

    def get_latest_context_date(self) -> str | None:
        """Return the date string of the most recent context file, or None."""
        if not self.contexts_dir.exists():
            return None
        files = sorted(
            [f for f in self.contexts_dir.glob("*.md") if f.stat().st_size > 5],
            reverse=True
        )
        return files[0].stem if files else None

    def save_context(self, context_text: str, for_date: str | None = None) -> Path:
        """
        Save a new context file.
        for_date: ISO date string e.g. '2026-07-15'. Defaults to today.
        """
        self.contexts_dir.mkdir(parents=True, exist_ok=True)
        date_str = for_date or date.today().isoformat()
        path = self.contexts_dir / f"{date_str}.md"
        path.write_text(context_text.strip(), encoding="utf-8")
        return path

    def load_post_history(self) -> list[dict]:
        """Load the post history JSON log."""
        path = self.memory_dir / "post_history.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save_post_history(self, history: list[dict]) -> None:
        """Write the post history JSON log."""
        path = self.memory_dir / "post_history.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load_posts_queue(self) -> dict:
        """Load the cached posts queue. Returns dict with 'approved' and 'pending' lists."""
        path = self.memory_dir / "posts_queue.json"
        default = {"approved": [], "pending": []}
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return default
            if "approved" not in data:
                data["approved"] = []
            if "pending" not in data:
                data["pending"] = []
            return data
        except Exception:
            return default

    def save_posts_queue(self, queue: dict) -> None:
        """Save the cached posts queue."""
        path = self.memory_dir / "posts_queue.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(queue, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load_compact_profile(self) -> dict:
        """Load the compacted voice and facts profile json."""
        path = self.memory_dir / "compact_profile.json"
        default = {"voice_essence": [], "banned_patterns": [], "experience_summary": [], "backlog_facts": []}
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def save_compact_profile(self, profile: dict) -> None:
        """Save the compacted voice and facts profile json."""
        path = self.memory_dir / "compact_profile.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load_recent_posts_history_text(self, limit: int = 15) -> list[str]:
        """Load the text content of the last N posted updates for anti-repetition constraint."""
        history = self.load_post_history()
        # Filter for actual published posts and get their content/preview
        actual_posts = [h.get("preview", "") for h in history if not h.get("dry_run") and h.get("preview")]
        return actual_posts[-limit:]

    def build_full_context_summary(self) -> dict:
        """
        Return a dict with all memory pieces loaded.
        This is the single object passed around the app.
        """
        q = self.load_posts_queue()
        return {
            "voice_profile":    self.load_voice_profile(),
            "achievements":     self.load_achievements(),
            "recent_context":   self.load_recent_context(),
            "latest_date":      self.get_latest_context_date(),
            "has_context":      bool(self.load_recent_context()),
            "has_voice":        bool(self.load_voice_profile()),
            "has_achievements": bool(self.load_achievements()),
            "approved_count":   len(q.get("approved", [])),
            "pending_count":    len(q.get("pending", [])),
        }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _read_file(path: Path) -> str:
        if not path.exists():
            return ""
        try:
            content = path.read_text(encoding="utf-8").strip()
            # Skip template/placeholder-only files
            if content.startswith("<!-- TEMPLATE") or content == "":
                return ""
            return content
        except Exception:
            return ""

