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

    def generate_post(
        self,
        topic: str,
        tone: str = "Auto",
        extra_instructions: str = "",
        voice_profile: str = "",
        achievements: str = "",
        recent_context: str = "",
    ) -> str:
        """
        Generate a LinkedIn post.

        Parameters
        ----------
        topic              : The core idea or event to post about.
        tone               : One of TONE_GUIDELINES keys.
        extra_instructions : Free-form extra constraints from the user.
        voice_profile      : Contents of memory/voice_profile.md.
        achievements       : Contents of memory/achievements.md.
        recent_context     : Merged recent context files.
        """
        if not self.client:
            raise ValueError(
                "Gemini API client not configured. Set GEMINI_API_KEY."
            )

        prompt = self._build_prompt(
            topic, tone, extra_instructions,
            voice_profile, achievements, recent_context
        )

        raw = self._call_gemini(prompt)
        return raw.strip()

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

        return self._call_gemini(prompt).strip()

    # ─── Prompt Builder ───────────────────────────────────────────────────────

    def _build_prompt(
        self,
        topic: str,
        tone: str,
        extra_instructions: str,
        voice_profile: str,
        achievements: str,
        recent_context: str,
    ) -> str:
        tone_desc = TONE_GUIDELINES.get(tone, TONE_GUIDELINES["Auto"])
        banned_str = ", ".join(f'"{w}"' for w in AI_BANNED_WORDS)

        parts = []

        # 1. Role
        parts.append(
            "You are a world-class LinkedIn ghostwriter. "
            "Your job is to write a post that sounds like it came from a real, "
            "thoughtful professional — not from an AI content tool.\n"
            "You write for someone who is building in public, shares genuine lessons, "
            "and has a distinct voice. You never write generic career content."
        )

        # 2. Voice profile (if available)
        if voice_profile:
            parts.append(
                f"=== AUTHOR VOICE PROFILE ===\n"
                f"{voice_profile}\n"
                f"Follow this voice closely. It overrides any default style you would apply."
            )

        # 3. Achievements (if available)
        if achievements:
            parts.append(
                f"=== AUTHOR ACHIEVEMENTS & BACKGROUND ===\n"
                f"{achievements}\n"
                f"Use this as background credibility. Reference specific items naturally "
                f"if they're relevant to the topic."
            )

        # 4. Recent context (if available)
        if recent_context:
            parts.append(
                f"=== RECENT CONTEXT (raw thoughts from the author) ===\n"
                f"{recent_context}\n"
                f"Extract real, specific details from this. "
                f"This is the most important input — build the post around it."
            )

        # 5. Formatting rules
        parts.append(
            "=== LINKEDIN FORMATTING RULES (non-negotiable) ===\n"
            "1. HOOK: First line must be under 15 words. Use tension, a specific number, "
            "   or a counterintuitive claim. NEVER start with a question.\n"
            "2. SPACING: Every paragraph is 1–3 sentences. Leave a blank line between each.\n"
            "3. LINKS: NEVER put any URL or link in the post body. Mention 'link in comments' "
            "   if you need to reference something.\n"
            "4. HASHTAGS: 1–3 hashtags only. Place them on the last line. No hashtag spam.\n"
            "5. EMOJIS: Max 2–3 total. Use only where they add emphasis, not decoration.\n"
            "6. NO MARKDOWN: Do not use **bold**, *italic*, or ``` code blocks. "
            "   LinkedIn does not render markdown.\n"
            "7. LENGTH: 150–400 words. Enough to be substantial, not a wall of text.\n"
            "8. CTA: End with one specific, open-ended question that invites real replies — "
            "   not 'What do you think?' or 'Drop a comment below'.\n"
        )

        # 6. Anti-AI rules
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

        # 7. Task
        task_parts = [
            f"=== TASK ===\n"
            f"Topic: {topic}\n"
            f"Tone: {tone} — {tone_desc}"
        ]
        if extra_instructions:
            task_parts.append(f"Extra instructions: {extra_instructions}")
        task_parts.append(
            "\nWrite the LinkedIn post now. "
            "Output ONLY the post text. "
            "No intro like 'Here is your post:', no code fences, nothing extra."
        )
        parts.append("\n".join(task_parts))

        return "\n\n".join(parts)

    # ─── Gemini API Call ──────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if genai_errors and isinstance(e, genai_errors.APIError):
                raise RuntimeError(f"Gemini API error: {e}")
            raise RuntimeError(f"Unexpected error from Gemini: {e}")
