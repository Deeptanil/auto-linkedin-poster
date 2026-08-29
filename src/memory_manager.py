"""
memory_manager.py
──────────────────
Manages persistent state for posts queue and post execution history.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


class MemoryManager:
    def __init__(self):
        self.memory_dir = config.MEMORY_DIR

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
        """Load the cached posts queue."""
        path = self.memory_dir / "posts_queue.json"
        default = {"approved": [], "pending": [], "settings": {"post_interval_days": 3}}
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
            if "settings" not in data:
                data["settings"] = {"post_interval_days": 3}
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

    def load_recent_posts_history_text(self, limit: int = 15) -> list[str]:
        """Load the text content of the last N posted updates for anti-repetition constraint."""
        history = self.load_post_history()
        actual_posts = [h.get("preview", "") for h in history if not h.get("dry_run") and h.get("preview")]
        return actual_posts[-limit:]

    def build_full_context_summary(self) -> dict:
        """Return basic count stats for status APIs."""
        q = self.load_posts_queue()
        return {
            "approved_count": len(q.get("approved", [])),
            "pending_count":  len(q.get("pending", [])),
        }
