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
)


def main():
    print("=" * 60)
    print("  LinkedIn AI Auto-Poster")
    print("=" * 60)

    # ── Read inputs from environment ──────────────────────────────────────────
    context_input   = os.getenv("CONTEXT", "").strip()
    tone            = os.getenv("TONE", "Auto").strip()
    extra_notes     = os.getenv("EXTRA_NOTES", "").strip()
    dry_run         = os.getenv("DRY_RUN", "false").strip().lower() == "true"
    force           = os.getenv("FORCE", "false").strip().lower() == "true"
    skip_token_check = os.getenv("SKIP_TOKEN_CHECK", "false").strip().lower() == "true"

    print(f"  Tone:     {tone}")
    print(f"  Dry run:  {dry_run}")
    print(f"  Force:    {force}")
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

    print(f"  Voice profile:  {'✓' if ctx_summary['has_voice'] else '✗ (not set)'}")
    print(f"  Achievements:   {'✓' if ctx_summary['has_achievements'] else '✗ (not set)'}")
    print(f"  Recent context: {'✓' if ctx_summary['has_context'] else '✗ (none found)'}")
    print()

    # ── Guard: no context and not forced → skip posting ───────────────────────
    if not ctx_summary["has_context"] and not force:
        print("[!] No context available. Skipping post to avoid generic content.")
        print("    Run 'Add Context' workflow first, or use --force to post anyway.")
        notify_no_context()
        sys.exit(0)

    # ── Generate post ─────────────────────────────────────────────────────────
    print("[3/5] Generating post with Gemini...")

    # Build topic: use context as raw material, fall back to achievements snippet
    if ctx_summary["recent_context"]:
        topic = "See the recent context below — extract the most compelling story or insight."
    else:
        topic = "Share an insight from my professional background and achievements."

    try:
        ai = AIGenerator()
        post_text = ai.generate_post(
            topic            = topic,
            tone             = tone,
            extra_instructions = extra_notes,
            voice_profile    = ctx_summary["voice_profile"],
            achievements     = ctx_summary["achievements"],
            recent_context   = ctx_summary["recent_context"],
        )
    except Exception as e:
        error_msg = f"AI generation failed: {e}"
        print(f"[ERROR] {error_msg}")
        notify_post_error(error_msg)
        sys.exit(1)

    print()
    print("─" * 60)
    print("GENERATED POST:")
    print("─" * 60)
    print(post_text)
    print("─" * 60)
    print()

    # ── Dry run exit ─────────────────────────────────────────────────────────
    if dry_run:
        print("[4/5] DRY RUN mode — not posting to LinkedIn.")
        history = PostHistory()
        history.log(
            post_text    = post_text,
            post_urn     = "DRY_RUN",
            tone         = tone,
            context_date = ctx_summary["latest_date"],
            dry_run      = True,
        )
        print("[5/5] Logged dry-run entry to post_history.json.")
        print()
        print("✅ Dry run complete. Review the post above.")
        sys.exit(0)

    # ── Post to LinkedIn ──────────────────────────────────────────────────────
    print("[4/5] Posting to LinkedIn...")
    try:
        li = LinkedInAPI()
        post_urn = li.create_text_post(post_text)
        print(f"  ✓ Post published! URN: {post_urn}")
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

    # ── Log & notify ──────────────────────────────────────────────────────────
    print("[5/5] Logging and notifying...")
    history = PostHistory()
    history.log(
        post_text    = post_text,
        post_urn     = post_urn,
        tone         = tone,
        context_date = ctx_summary["latest_date"],
        dry_run      = False,
    )

    notify_post_success(post_text)

    print()
    print("🎉 All done! Post is live on LinkedIn.")


if __name__ == "__main__":
    main()
