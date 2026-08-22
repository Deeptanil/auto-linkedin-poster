"""
run.py — GitHub Actions entrypoint
────────────────────────────────────
This script is called by the daily-post.yml GitHub Actions workflow.
It orchestrates the full pipeline:

  1. Parse inputs from environment variables set by the workflow
  2. Check / refresh the LinkedIn access token
  3. Load memory (voice profile, achievements, context)
  4. Guard: skip if no context and not forced
  5. Generate post via Gemini
  6. Post to LinkedIn (unless DRY_RUN=true)
  7. Log to post_history.json and commit it back
  8. Notify via Discord

Environment variables (set by the GitHub Actions workflow):
  CONTEXT          — raw context text (from workflow_dispatch input)
  TONE             — post tone (default: Auto)
  EXTRA_NOTES      — additional instructions
  DRY_RUN          — 'true' to skip actual posting (print only)
  FORCE            — 'true' to post even without context
  SKIP_TOKEN_CHECK — 'true' to skip token refresh logic
  + All secrets from config.py
"""

import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.memory_manager   import MemoryManager
from src.ai_generator     import AIGenerator
from src.linkedin_api     import LinkedInAPI, LinkedInAPIError
from src.token_manager    import TokenManager
from src.post_history     import PostHistory
from src.discord_notifier import (
    notify_post_success,
    notify_post_error,
    notify_no_context,
    notify_queue_warning,
    notify_queue_empty_reminder,
)


def collect_blacklist_posts(mem: MemoryManager, approved_list: list[dict], pending_list: list[dict]) -> list[str]:
    """Combine recent history and queued drafts to reduce repeated angles."""
    blacklist_posts = mem.load_recent_posts_history_text(limit=15)
    for group in (approved_list, pending_list):
        for item in group:
            text = item.get("post_text", "").strip()
            if text:
                blacklist_posts.append(text)
    return blacklist_posts


class DualLogger:
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(f"--- Posting Pipeline Run Started: {__import__('datetime').datetime.now()} ---\n")

    def write(self, message):
        try:
            self.terminal.write(message)
        except UnicodeEncodeError:
            try:
                encoding = self.terminal.encoding or 'utf-8'
                self.terminal.write(message.encode(encoding, errors='replace').decode(encoding))
            except Exception:
                pass
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def flush(self):
        self.terminal.flush()



def main():
    # Redirect output streams to local or remote state log
    log_file = config.MEMORY_DIR / "dashboard.log"
    sys.stdout = DualLogger(log_file)
    sys.stderr = sys.stdout

    print("=" * 60)
    print("  LinkedIn AI Auto-Poster (Batch Queue & Memory Engine)")
    print("=" * 60)

    # ── Fast-exit: already posted today? (IST) ────────────────────────────────
    # Check this FIRST before any slow work (token refresh, memory load, etc.)
    # This is the primary guard for the multi-cron retry schedule.
    replenish_only = os.getenv("REPLENISH_ONLY", "false").strip().lower() == "true"
    force          = os.getenv("FORCE", "false").strip().lower() == "true"

    if not replenish_only and not force:
        mem = MemoryManager()
        queue = mem.load_posts_queue()
        settings = queue.get("settings", {})
        post_interval_days = int(settings.get("post_interval_days", 1))

        history = PostHistory()
        days_since = history.get_days_since_last_post()
        if days_since is not None and days_since < post_interval_days:
            print(f"[!] Last post was {days_since} days ago. Current interval is {post_interval_days} days. Skipping posting.")
            sys.exit(0)

    # ── Read inputs from environment ──────────────────────────────────────────
    context_input    = os.getenv("CONTEXT", "").strip()
    tone             = os.getenv("TONE", "Auto").strip()
    extra_notes      = os.getenv("EXTRA_NOTES", "").strip()
    dry_run          = os.getenv("DRY_RUN", "false").strip().lower() == "true"
    skip_token_check = os.getenv("SKIP_TOKEN_CHECK", "false").strip().lower() == "true"
    # (replenish_only and force already read above for the fast-exit guard)

    print(f"  Tone:     {tone}")
    print(f"  Dry run:  {dry_run}")
    print(f"  Force:    {force}")
    print(f"  Replenish Only: {replenish_only}")
    print()

    # ── Token check / refresh ─────────────────────────────────────────────────
    if not skip_token_check and config.LINKEDIN_REFRESH_TOKEN:
        print("[1/5] Checking LinkedIn token...")
        try:
            tm = TokenManager()
            tm.check_and_refresh()
        except Exception as e:
            print(f"  Token check warning: {e}")
    else:
        print("[1/5] Token check skipped.")

    # ── Load memory ───────────────────────────────────────────────────────────
    print("[2/5] Loading memory...")
    mem = MemoryManager()

    # If context was passed as a workflow input, save it first
    if context_input:
        saved_path = mem.save_context(context_input)
        print(f"  Context saved to: {saved_path.name}")

    ctx_summary = mem.build_full_context_summary()

    print(f"  Voice profile:  {'[OK]' if ctx_summary['has_voice'] else '[X] (not set)'}")
    print(f"  Achievements:   {'[OK]' if ctx_summary['has_achievements'] else '[X] (not set)'}")
    print(f"  Recent context: {'[OK]' if ctx_summary['has_context'] else '[X] (none found)'}")
    print(f"  Approved posts: {ctx_summary['approved_count']}")
    print(f"  Pending drafts: {ctx_summary['pending_count']}")
    print()

    # ── 1. Check Approved Queue ───────────────────────────────────────────────
    queue = mem.load_posts_queue()
    approved_list = queue.get("approved", [])
    pending_list = queue.get("pending", [])

    if replenish_only:
        print("[!] Replenish Only mode active. Skipping publishing logic.")
        if len(pending_list) < 10:
            print(f"    Replenishing pending drafts queue (current: {len(pending_list)}, target: 10)...")
            try:
                topic = "See the recent context below — extract the most compelling story or insight." if ctx_summary["recent_context"] else "Share an insight from my professional background and achievements."
                blacklist_posts = collect_blacklist_posts(mem, approved_list, pending_list)
                
                compact = mem.load_compact_profile()
                ai = AIGenerator()
                needed = 10 - len(pending_list)
                batch = ai.generate_post_batch(
                    topic=topic,
                    tone=tone,
                    extra_instructions=extra_notes,
                    compact_profile=compact,
                    recent_context=ctx_summary["recent_context"],
                    past_posts=blacklist_posts,
                    batch_size=needed
                )
                if batch:
                    pending_list.extend(batch)
                    queue["pending"] = pending_list
                    mem.save_posts_queue(queue)
                    print(f"    Added {len(batch)} new drafts to pending queue.")
            except Exception as e:
                print(f"    Failed to replenish drafts queue: {e}")
        else:
            print("    Pending queue is already full (10 drafts). No action needed.")
        sys.exit(0)

    if not approved_list:
        print("[!] No approved posts in queue. Skipping schedule execution.")
        print("    Please run the local dashboard, approve some drafts, and sync to GitHub.")
        
        # Only send the Discord reminder once per day (on the first morning run only).
        # We detect this by checking if the current UTC hour is in the first morning window
        # (before 6 AM UTC = before ~11:30 AM IST), preventing repeat pings on retries.
        from datetime import datetime, timezone
        current_utc_hour = datetime.now(timezone.utc).hour
        if current_utc_hour < 6:
            notify_queue_empty_reminder()
        
        # If we have less than 10 pending drafts, let's proactively generate some so the user has choices
        if len(pending_list) < 10:
            print("    Proactively replenishing pending drafts queue (target: 10)...")
            try:
                topic = "See the recent context below — extract the most compelling story or insight." if ctx_summary["recent_context"] else "Share an insight from my professional background and achievements."
                blacklist_posts = collect_blacklist_posts(mem, approved_list, pending_list)
                
                compact = mem.load_compact_profile()
                ai = AIGenerator()
                needed = 10 - len(pending_list)
                batch = ai.generate_post_batch(
                    topic=topic,
                    tone=tone,
                    extra_instructions=extra_notes,
                    compact_profile=compact,
                    recent_context=ctx_summary["recent_context"],
                    past_posts=blacklist_posts,
                    batch_size=needed
                )
                if batch:
                    pending_list.extend(batch)
                    queue["pending"] = pending_list
                    mem.save_posts_queue(queue)
                    print(f"    Added {len(batch)} new drafts to pending queue.")
            except Exception as e:
                print(f"    Failed to replenish drafts queue: {e}")
        
        sys.exit(0)

    # already_posted_today was already checked at startup (fast-exit guard above).
    # Instantiate history here for use in logging below.
    history = PostHistory()

    # Pop the first approved post
    current_item = approved_list[0]
    post_text = current_item["post_text"]

    # Alert if we are posting the last remaining approved post (1 day before running out)
    if len(approved_list) == 1:
        print("[!] Only 1 approved post remaining in queue. Alerting Discord...")
        notify_queue_warning(remaining_days=1)

    print()
    print("─" * 60)
    print("CURRENT APPROVED POST TO PUBLISH:")
    print("─" * 60)
    print(post_text)
    print("─" * 60)
    print()

    # ── Dry run exit ─────────────────────────────────────────────────────────
    if dry_run:
        print("[4/5] DRY RUN mode — not posting to LinkedIn.")
        # history already instantiated above
        history.log(
            post_text    = post_text,
            post_urn     = "DRY_RUN",
            tone         = tone,
            context_date = ctx_summary["latest_date"],
            dry_run      = True,
        )
        print("[5/5] Logged dry-run entry to post_history.json. Queues unchanged.")
        sys.exit(0)

    # ── Post to LinkedIn ──────────────────────────────────────────────────────
    print("[4/5] Posting to LinkedIn...")
    try:
        li = LinkedInAPI()
        
        # Retrieve image paths array, falling back to legacy single image_path
        image_paths = current_item.get("image_paths")
        if not image_paths:
            legacy_path = current_item.get("image_path")
            image_paths = [legacy_path] if legacy_path else []
            
        valid_paths = []
        for img_p in image_paths:
            if not img_p:
                continue
            path_obj = Path(img_p)
            if not path_obj.is_absolute():
                path_obj = Path(__file__).resolve().parent.parent / img_p
            if path_obj.exists():
                valid_paths.append(path_obj)
            else:
                print(f"  [WARNING] Attachment path does not exist: {path_obj}")

        if not valid_paths:
            if image_paths:
                print("  [WARNING] None of the specified image paths exist. Falling back to text-only post.")
            post_urn = li.create_text_post(post_text)
        elif len(valid_paths) == 1:
            print(f"  [image] Found 1 image attachment at: {valid_paths[0]}")
            print("  [image] Uploading to LinkedIn...")
            image_urn = li.upload_image(valid_paths[0])
            print(f"  [image] Upload complete. Image URN: {image_urn}")
            print("  [image] Creating LinkedIn post with image...")
            post_urn = li.create_image_post(post_text, image_urn)
        else:
            print(f"  [image] Found {len(valid_paths)} image attachments.")
            image_urns = []
            for i, p_obj in enumerate(valid_paths, 1):
                print(f"  [image] Uploading image {i}/{len(valid_paths)}: {p_obj}...")
                urn = li.upload_image(p_obj)
                print(f"  [image] Image {i} uploaded. URN: {urn}")
                image_urns.append(urn)
            print("  [image] Creating LinkedIn post with multiple images...")
            post_urn = li.create_multi_image_post(post_text, image_urns)
            
        print(f"  [OK] Post published! URN: {post_urn}")
    except LinkedInAPIError as e:
        error_msg = str(e)
        print(f"[ERROR] {error_msg}")
        notify_post_error(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error posting: {e}"
        print(f"[ERROR] {error_msg}")
        notify_post_error(error_msg)
        sys.exit(1)

    # ── Update queues & notify ────────────────────────────────────────────────
    print("[5/5] Updating queues and logging history...")
    
    # Remove the posted item from approved list
    approved_list.pop(0)
    queue["approved"] = approved_list

    # Ensure pending queue maintains at least 10 items
    if len(pending_list) < 10:
        print("  Replenishing pending queue back up to 10...")
        try:
            topic = "See the recent context below — extract the most compelling story or insight." if ctx_summary["recent_context"] else "Share an insight from my professional background and achievements."
            blacklist_posts = collect_blacklist_posts(mem, approved_list, pending_list)
            
            compact = mem.load_compact_profile()
            ai = AIGenerator()
            needed = 10 - len(pending_list)
            batch = ai.generate_post_batch(
                topic=topic,
                tone=tone,
                extra_instructions=extra_notes,
                compact_profile=compact,
                recent_context=ctx_summary["recent_context"],
                past_posts=blacklist_posts,
                batch_size=needed
            )
            if batch:
                pending_list.extend(batch)
                queue["pending"] = pending_list
                print(f"  Added {len(batch)} new drafts to pending queue.")
        except Exception as e:
            print(f"  Could not automatically replenish pending drafts: {e}")

    # Stamp the post time so the dashboard coverage-date calculation
    # knows whether today's post has already been sent.
    from datetime import datetime, timezone
    queue["last_posted_at"] = datetime.now(timezone.utc).isoformat()

    # Save queues
    mem.save_posts_queue(queue)

    # Log history
    # history already instantiated above
    history.log(
        post_text    = post_text,
        post_urn     = post_urn,
        tone         = tone,
        context_date = ctx_summary["latest_date"],
        dry_run      = False,
    )

    notify_post_success(post_text, post_urn)

    print()
    print("🎉 All done! Post is live on LinkedIn. Cache queue updated.")


if __name__ == "__main__":
    main()

