"""
ai_generator.py  (src/ version — upgraded for GitHub Actions)
───────────────────────────────────────────────────────────────
Upgraded Gemini-powered post generator with:
  • Voice-profile awareness (your personal style)
  • Achievement context injection
  • Anti-AI-fingerprint pass (strips clichés, adds burstiness)
  • Strict LinkedIn formatting rules (no links in body, 1-3 hashtags, etc.)
  • Tone selection
"""

import sys
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

try:
    from google import genai
    from google.genai import errors as genai_errors
except ImportError:
    genai = None
    genai_errors = None


# ─── Words/phrases that scream "AI wrote this" ────────────────────────────────
AI_BANNED_WORDS = [
    "delve", "tapestry", "leverage", "leveraging", "seamless", "seamlessly",
    "game-changer", "game changer", "landscape", "unlock", "unlocking",
    "navigate", "navigating", "in today's fast-paced", "in the ever-evolving",
    "it's no secret", "cutting-edge", "at the forefront", "paradigm", "synergy",
    "holistic", "robust", "empower", "empowering", "transformative", "innovative",
    "revolutionize", "revolutionizing", "unprecedented", "elevate", "elevating",
    "skyrocket", "game plan", "thought leader", "thought leadership",
    "in conclusion", "to summarize", "as we know", "needless to say",
    "it goes without saying", "at the end of the day", "move the needle",
    "circle back", "low-hanging fruit", "bandwidth", "ping me",
]

TONE_GUIDELINES = {
    "Auto": (
        "Pick the most suitable tone based on the context provided. "
        "Default to Storytelling for personal wins, Technical for code/engineering topics, "
        "and Thought Leadership for opinion/industry commentary."
    ),
    "Professional": (
        "Authoritative, insightful, and objective. Sounds like a sharp practitioner "
        "sharing hard-won knowledge — not a LinkedIn influencer. No motivational fluff."
    ),
    "Technical": (
        "Detail-oriented, educational, and developer-friendly. Focuses on specifics: "
        "what broke, what you tried, what worked, and what you'd do differently. "
        "Uses precise technical terms without over-explaining them."
    ),
    "Thought Leadership": (
        "Challenges conventional wisdom or makes a bold, specific prediction. "
        "States a strong opinion and defends it with data or personal experience. "
        "Provocative but credible — never preachy."
    ),
    "Casual/Conversational": (
        "Warm, relatable, and real. Written like a WhatsApp voice note to a smart friend. "
        "Uses natural contractions, occasional self-deprecating humour, and imperfect prose."
    ),
    "Storytelling": (
        "Narrative-driven. Opens with a scene or conflict, not a statement. "
        "Describes the struggle honestly, then the resolution. "
        "The lesson comes from the story — it's never spelled out like a LinkedIn lesson post."
    ),
}


class AIGenerator:
    def __init__(self):
        if not config.is_gemini_configured():
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=config.GEMINI_API_KEY)
            except Exception as e:
                self.client = None
                print(f"[ai_generator] Error initialising Gemini: {e}", file=sys.stderr)

    # ─── Main generation ──────────────────────────────────────────────────────

    def generate_post_batch(
        self,
        topic: str,
        tone: str = "Auto",
        extra_instructions: str = "",
        compact_profile: dict = None,
        recent_context: str = "",
        past_posts: list[str] = None,
        batch_size: int = 5,
    ) -> list[dict]:
        """
        Generate a batch of LinkedIn posts as structured JSON.
        Applies anti-repetition memory and filters out invalid posts (e.g. posts containing URLs).

        Returns:
            list[dict]: Array of parsed post dicts, each with "post_text" and "reasoning"
        """
        if not self.client:
            raise ValueError("Gemini API client not configured. Set GEMINI_API_KEY.")

        # Format anti-repetition negative constraints
        history_blacklist = ""
        if past_posts:
            # Escape double quotes for JSON safety in prompt
            escaped_posts = [p.replace('"', '\\"') for p in past_posts]
            history_blacklist = "\n".join(f'- "{p}"' for p in escaped_posts)

        prompt = self._build_batch_prompt(
            topic, tone, extra_instructions,
            compact_profile, recent_context,
            history_blacklist, batch_size
        )

        raw_response = self._call_gemini_json(prompt)
        raw_text = raw_response.strip()

        # Clean JSON if wrapped in markdown code blocks
        if raw_text.startswith("```"):
            # Strip first line e.g., ```json
            first_newline = raw_text.find("\n")
            if first_newline != -1:
                raw_text = raw_text[first_newline:].strip()
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        try:
            batch = json.loads(raw_text)
            if not isinstance(batch, list):
                raise ValueError("AI response is not a JSON list.")
        except Exception as e:
            print(f"[ai_generator] Failed to parse JSON response: {e}. Raw response:\n{raw_text}", file=sys.stderr)
            # Return empty list so caller can retry or handle
            return []

        # Apply hard URL and safety filters
        filtered_batch = []
        url_patterns = [".co", ".in", ".com", "http", "link in bio", "check the site", "www.", ".org", ".net"]
        
        for idx, item in enumerate(batch):
            if not isinstance(item, dict) or "post_text" not in item:
                continue
            
            post_text = item["post_text"].strip()
            
            # URL constraint filter
            contains_url = any(pat in post_text.lower() for pat in url_patterns)
            if contains_url:
                print(f"[ai_generator] Filtered post index {idx} because it contained a URL or link phrasing.")
                continue

            # Hard safety filter (simple checks to prevent brand damage)
            if not post_text or len(post_text) < 50:
                print(f"[ai_generator] Filtered post index {idx} because it was too short.")
                continue

            # Double check for markdown formatting
            # Check for double asterisks or triple backticks
            if "**" in post_text or "```" in post_text:
                print(f"[ai_generator] Filtered post index {idx} because it contained markdown symbols (** or ```).")
                continue

            filtered_batch.append({
                "post_text": post_text,
                "reasoning": item.get("reasoning", "No reasoning provided")
            })

        return filtered_batch

    def generate_post(
        self,
        topic: str,
        tone: str = "Auto",
        extra_instructions: str = "",
        voice_profile: str = "",
        achievements: str = "",
        recent_context: str = "",
    ) -> str:
        """Helper to generate a single post (used by local CLI). Loads compact profile internally."""
        from src.memory_manager import MemoryManager
        mem = MemoryManager()
        compact = mem.load_compact_profile()
        
        batch = self.generate_post_batch(
            topic=topic,
            tone=tone,
            extra_instructions=extra_instructions,
            compact_profile=compact,
            recent_context=recent_context,
            batch_size=1
        )
        if batch:
            return batch[0]["post_text"]
        raise RuntimeError("Failed to generate post.")

    def revise_post(self, original_post: str, revision_instructions: str) -> str:
        """Revise an existing draft based on feedback."""
        if not self.client:
            raise ValueError("Gemini API client not configured.")

        prompt = (
            "You are refining a LinkedIn post draft.\n"
            "Keep all existing formatting rules:\n"
            "  • Strong hook (declarative, under 15 words)\n"
            "  • Short paragraph blocks (1–3 sentences each)\n"
            "  • No markdown bold/italic\n"
            "  • No links in the post body\n"
            "  • 1–3 hashtags at the very end\n\n"
            f"=== ORIGINAL DRAFT ===\n{original_post}\n\n"
            f"=== REVISION INSTRUCTIONS ===\n{revision_instructions}\n\n"
            "Rewrite and output ONLY the revised post. "
            "No introductory text, no code blocks."
        )

        # Call with plain text response mode
        return self._call_gemini_plain(prompt).strip()

    # ─── Prompt Builder ───────────────────────────────────────────────────────

    def _build_batch_prompt(
        self,
        topic: str,
        tone: str,
        extra_instructions: str,
        compact_profile: dict,
        recent_context: str,
        history_blacklist: str,
        batch_size: int,
    ) -> str:
        tone_desc = TONE_GUIDELINES.get(tone, TONE_GUIDELINES["Auto"])
        banned_str = ", ".join(f'"{w}"' for w in AI_BANNED_WORDS)

        parts = []

        # 1. Role
        parts.append(
            "You are a world-class LinkedIn ghostwriter. "
            "Your job is to write posts that sound like they came from a real, "
            "thoughtful professional — not from an AI content tool.\n"
            "You write for someone who is building in public, shares genuine lessons, "
            "and has a distinct voice. You never write generic career content."
        )

        # 2. Compact Profile Facts & Voice (Highly Token-Efficient)
        if compact_profile:
            essence = "\n".join(f"- {item}" for item in compact_profile.get("voice_essence", []))
            banned = ", ".join(compact_profile.get("banned_patterns", []))
            summary = "\n".join(f"- {item}" for item in compact_profile.get("experience_summary", []))
            facts = "\n".join(f"- {item}" for item in compact_profile.get("backlog_facts", []))

            profile_block = (
                "=== COMPACT AUTHOR BLUEPRINT ===\n"
                f"Writing Style Guidelines:\n{essence}\n\n"
                f"Banned Words / Buzzwords to Avoid: {banned or 'None'}\n\n"
                f"Startup & Tech Background:\n{summary}\n\n"
                f"Backlog of Key Achievements & Experiences (Use for post inspiration):\n{facts}"
            )
            parts.append(profile_block)

        # 3. Recent context (if available)
        if recent_context:
            parts.append(
                f"=== RECENT CONTEXT (raw thoughts from the author) ===\n"
                f"{recent_context}\n"
                f"Extract real, specific details from this. "
                f"This is the most important input — build the posts around it."
            )

        # 4. Anti-Repetition constraint
        if history_blacklist:
            parts.append(
                f"=== RECENTLY POSTED CONTENT (DO NOT REPEAT OR REWRITE THESE TOPICS) ===\n"
                f"{history_blacklist}\n"
                f"Write posts about entirely different angles, ideas, or problems."
            )

        # 6. Formatting rules
        parts.append(
            "=== LINKEDIN FORMATTING RULES (non-negotiable) ===\n"
            "1. HOOK: First line must be under 15 words. Use tension, a specific number, "
            "   or a counterintuitive claim. NEVER start with a question.\n"
            "2. SPACING: Every paragraph is 1–3 sentences. Leave a blank line between each.\n"
            "3. LINKS: NEVER put any URL, domain name, or link in the post body. Mention 'link in comments' "
            "   if you need to reference something.\n"
            "4. HASHTAGS: 1–3 hashtags only. Place them on the last line. No hashtag spam.\n"
            "5. EMOJIS: Max 2–3 total. Use only where they add emphasis, not decoration.\n"
            "6. NO MARKDOWN: Do not use **bold**, *italic*, or ``` code blocks. "
            "   LinkedIn does not render markdown. Keep everything as raw text.\n"
            "7. LENGTH: 150–400 words per post. Enough to be substantial, not a wall of text.\n"
            "8. CTA: End with one specific, open-ended question that invites real replies — "
            "   not 'What do you think?' or 'Drop a comment below'.\n"
        )

        # 7. Anti-AI rules
        parts.append(
            f"=== BANNED WORDS & PHRASES ===\n"
            f"NEVER use any of these: {banned_str}.\n"
            f"Also avoid:\n"
            f"  • Predictable 3-bullet 'lesson' structures\n"
            f"  • The phrase 'I've been thinking about...'\n"
            f"  • Any version of 'In today's world...'\n"
            f"  • Overly dramatic humble-brags ('From nothing to everything...')\n"
            f"  • Starting a line with 'Remember:' or 'The truth is:'\n"
            f"Inject BURSTINESS: mix short punchy sentences with longer descriptive ones. "
            f"Include at least one specific detail (a date, a number, a name, a tool) "
            f"that makes the post impossible for anyone else to have written."
        )

        # 8. Task & JSON wrapper instructions
        task_parts = [
            f"=== TASK ===\n"
            f"Topic: {topic}\n"
            f"Tone: {tone} — {tone_desc}"
        ]
        if extra_instructions:
            task_parts.append(f"Extra instructions: {extra_instructions}")
            
        task_parts.append(
            f"\nWrite exactly {batch_size} unique LinkedIn posts that fit all the guidelines above.\n\n"
            f"Return ONLY a valid JSON array of objects with this structure:\n"
            f"[\n"
            f"  {{\n"
            f"    \"post_text\": \"The complete raw text of the post\",\n"
            f"    \"reasoning\": \"A short explanation of why this post fits the persona/context\"\n"
            f"  }}\n"
            f"]"
        )
        parts.append("\n".join(task_parts))

        return "\n\n".join(parts)

    # ─── Gemini API Calls ─────────────────────────────────────────────────────

    def _call_with_retry(self, model: str, contents: str, response_config: dict = None) -> str:
        import time
        max_retries = 3
        delay = 2
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=response_config,
                )
                return response.text
            except Exception as e:
                # If it's the last attempt, raise it
                if attempt == max_retries - 1:
                    raise e
                
                err_msg = str(e)
                # Check for transient errors (503, 429, RESOURCE_EXHAUSTED, UNAVAILABLE)
                is_transient = any(code in err_msg for code in ["503", "429", "UNAVAILABLE", "ResourceExhausted", "Resource exhausted"])
                if is_transient:
                    print(f"[ai_generator] Gemini experiencing high demand/rate limits (Attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise e

    def _call_gemini_json(self, prompt: str) -> str:
        """Call Gemini requesting structured JSON output."""
        try:
            return self._call_with_retry(
                model=config.GEMINI_MODEL,
                contents=prompt,
                response_config={"response_mime_type": "application/json"}
            )
        except Exception as e:
            if genai_errors and isinstance(e, genai_errors.APIError):
                raise RuntimeError(f"Gemini API error: {e}")
            raise RuntimeError(f"Unexpected error from Gemini: {e}")

    def _call_gemini_plain(self, prompt: str) -> str:
        """Call Gemini requesting plain text output."""
        try:
            return self._call_with_retry(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
        except Exception as e:
            if genai_errors and isinstance(e, genai_errors.APIError):
                raise RuntimeError(f"Gemini API error: {e}")
            raise RuntimeError(f"Unexpected error from Gemini: {e}")


