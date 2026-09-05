"""
ai_generator.py
───────────────
Gemini-powered post generator with:
  • Anti-AI-fingerprint pass (strips clichés, adds burstiness)
  • High-converting LinkedIn hook rules
  • Strict LinkedIn formatting rules (no links in body, no emojis, 1-3 hashtags, etc.)
  • Tone selection
"""

import sys
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.skills_library import (
    AI_BANNED_WORDS,
    ANTI_AI_HUMANIZER_INSTRUCTIONS,
    FOUNDER_ANGLES,
    HOOK_FORMULAS,
)

try:
    from google import genai
    from google.genai import errors as genai_errors
except ImportError:
    genai = None
    genai_errors = None


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

    def generate_post_batch(
        self,
        topic: str,
        tone: str = "Auto",
        extra_instructions: str = "",
        compact_profile: dict = None,
        recent_context: str = "",
        past_posts: list[str] = None,
        batch_size: int = 5,
        topic_is_source_of_truth: bool = False,
        hook_formula: str = "None",
        founder_angle: str = "None",
    ) -> list[dict]:
        print(f"[ai_generator] Starting batch generation. Batch size: {batch_size}, Tone: {tone}, Hook: {hook_formula}, Founder Angle: {founder_angle}")
        if not self.client:
            print("[ai_generator] ERROR: Gemini API key is missing.")
            raise ValueError("Gemini API client not configured. Set GEMINI_API_KEY.")

        comparison_posts = [p.strip() for p in (past_posts or []) if isinstance(p, str) and p.strip()]

        history_blacklist = ""
        if past_posts:
            escaped_posts = [p.replace('"', '\\"') for p in past_posts]
            history_blacklist = "\n".join(f'- "{p}"' for p in escaped_posts)

        prompt = self._build_batch_prompt(
            topic, tone, extra_instructions,
            compact_profile, recent_context,
            history_blacklist, batch_size,
            topic_is_source_of_truth=topic_is_source_of_truth,
            hook_formula=hook_formula,
            founder_angle=founder_angle,
        )

        try:
            raw_response = self._call_gemini_json(prompt)
        except Exception as api_err:
            print(f"[ai_generator] API Call Error: {api_err}")
            raise api_err
            
        raw_text = raw_response.strip()

        if raw_text.startswith("```"):
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
            print(f"[ai_generator] JSON Parsing Failure: {e}. Raw response:\n{raw_text}", file=sys.stderr)
            return []

        filtered_batch = []
        url_patterns = ["http://", "https://", "www.", ".com/", ".org/", ".net/", ".io/", ".co/", ".in/", "link in bio", "check out"]
        
        for idx, item in enumerate(batch):
            if not isinstance(item, dict) or "post_text" not in item:
                continue
            
            post_text = self._clean_ai_tells(item["post_text"].strip())
            
            contains_url = any(pat in post_text.lower() for pat in url_patterns)
            if contains_url:
                continue

            if not post_text or len(post_text) < 50:
                continue

            if "**" in post_text or "```" in post_text:
                continue

            if self._contains_emoji(post_text):
                continue

            if not topic_is_source_of_truth:
                overlap_score = self._max_similarity(post_text, comparison_posts + [entry["post_text"] for entry in filtered_batch])
                if overlap_score >= 0.55:
                    continue

            filtered_batch.append({
                "post_text": post_text,
                "reasoning": item.get("reasoning", "No reasoning provided")
            })

        return filtered_batch

    @staticmethod
    def _clean_ai_tells(text: str) -> str:
        """Strip lingering banned AI words or AI structural tells."""
        for word in AI_BANNED_WORDS:
            # Case-insensitive replacement of standalone banned phrases
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            text = pattern.sub("", text)

        # Fix double spaces caused by removal
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _contains_emoji(text: str) -> bool:
        return bool(re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text))

    @staticmethod
    def _normalise_words(text: str) -> set[str]:
        cleaned = re.sub(r"#[A-Za-z0-9_]+", " ", text.lower())
        words = re.findall(r"[a-z0-9']+", cleaned)
        return {word for word in words if len(word) > 2}

    def _max_similarity(self, text: str, other_posts: list[str]) -> float:
        if not other_posts:
            return 0.0

        current_words = self._normalise_words(text)
        if not current_words:
            return 0.0

        max_score = 0.0
        for other in other_posts:
            other_words = self._normalise_words(other)
            if not other_words:
                continue
            intersection = len(current_words & other_words)
            union = len(current_words | other_words)
            if union == 0:
                continue
            max_score = max(max_score, intersection / union)
        return max_score

    def generate_post(
        self,
        topic: str,
        tone: str = "Auto",
        extra_instructions: str = "",
        voice_profile: str = "",
        achievements: str = "",
        recent_context: str = "",
        hook_formula: str = "None",
        founder_angle: str = "None",
    ) -> str:
        from src.memory_manager import MemoryManager
        mem = MemoryManager()
        compact = mem.load_compact_profile()
        
        batch = self.generate_post_batch(
            topic=topic,
            tone=tone,
            extra_instructions=extra_instructions,
            compact_profile=compact,
            recent_context=recent_context,
            batch_size=1,
            hook_formula=hook_formula,
            founder_angle=founder_angle,
        )
        if batch:
            return batch[0]["post_text"]
        raise RuntimeError("Failed to generate post.")

    def revise_post(self, original_post: str, revision_instructions: str) -> str:
        if not self.client:
            raise ValueError("Gemini API client not configured.")

        prompt = (
            "You are refining a LinkedIn post draft.\n"
            "Keep all existing formatting rules:\n"
            "  • Strong hook (declarative, under 15 words)\n"
            "  • Short paragraph blocks (1–3 sentences each)\n"
            "  • No markdown bold/italic\n"
            "  • No links in the post body\n"
            "  • No emojis (STRICT CONSTRAINT — keep it 100% plain text, no emojis)\n"
            "  • 1–3 hashtags at the very end\n\n"
            f"{ANTI_AI_HUMANIZER_INSTRUCTIONS}\n\n"
            f"=== ORIGINAL DRAFT ===\n{original_post}\n\n"
            f"=== REVISION INSTRUCTIONS ===\n{revision_instructions}\n\n"
            "Rewrite and output ONLY the revised post. "
            "No introductory text, no code blocks."
        )

        return self._call_gemini_plain(prompt).strip()

    def _build_batch_prompt(
        self,
        topic: str,
        tone: str,
        extra_instructions: str,
        compact_profile: dict,
        recent_context: str,
        history_blacklist: str,
        batch_size: int,
        topic_is_source_of_truth: bool = False,
        hook_formula: str = "None",
        founder_angle: str = "None",
    ) -> str:
        tone_desc = TONE_GUIDELINES.get(tone, TONE_GUIDELINES["Auto"])
        banned_str = ", ".join(f'"{w}"' for w in AI_BANNED_WORDS)

        parts = []

        parts.append(
            "You are writing LinkedIn posts on behalf of Deeptanil Sinha, a 20-year-old student-founder "
            "and developer based in Bangalore, India. He co-founded Prettiva & Co. and STRAYED.\n"
            "CRITICAL TONE & IDENTITY GUIDELINES:\n"
            "- Tone: Casual, honest, down-to-earth Indian college student & founder in Bangalore. Sounds like a normal guy who builds tech, rather than a corporate executive.\n"
            "- Language: Use plain English with natural contractions. You can use casual phrases like 'tbh' or 'actually' but keep it professional. NEVER use formal corporate PR phrases.\n"
            "- STRICT FACTUAL CONSTRAINT: NEVER make up stories, events, financial numbers, or investment details from thin air. Build posts ONLY around real provided facts.\n"
            f"{ANTI_AI_HUMANIZER_INSTRUCTIONS}"
        )

        if compact_profile:
            essence = "\n".join(f"- {item}" for item in compact_profile.get("voice_essence", []))
            banned = ", ".join(compact_profile.get("banned_patterns", []))
            summary = "\n".join(f"- {item}" for item in compact_profile.get("experience_summary", []))
            facts = "\n".join(f"- {item}" for item in compact_profile.get("backlog_facts", []))

            profile_block = (
                "=== COMPACT AUTHOR BLUEPRINT ===\n"
                f"Writing Style Guidelines:\n{essence}\n\n"
                f"Banned Words / Buzzwords: {banned or 'None'}\n\n"
                f"Startup & Tech Background:\n{summary}\n\n"
                f"Backlog of Key Achievements & Experiences:\n{facts}"
            )
            parts.append(profile_block)

        # Founder Angle Integration
        if founder_angle and founder_angle in FOUNDER_ANGLES and founder_angle != "None":
            angle_info = FOUNDER_ANGLES[founder_angle]
            parts.append(
                f"=== SELECTED FOUNDER ANGLE & POSITIONING STRATEGY ===\n"
                f"Strategy: {angle_info['title']} ({angle_info['description']})\n"
                f"Instruction: {angle_info['prompt_instruction']}"
            )

        # Hook Formula Integration
        if hook_formula and hook_formula in HOOK_FORMULAS and hook_formula != "None":
            hook_info = HOOK_FORMULAS[hook_formula]
            parts.append(
                f"=== SELECTED VIRAL HOOK FORMULA ===\n"
                f"Formula: {hook_info['name']} (Goal: {hook_info['goal']})\n"
                f"Skeleton: {hook_info['skeleton']}\n"
                f"Instruction: {hook_info['instruction']}"
            )

        # 3. Recent context & Anti-repetition
        if recent_context:
            parts.append(
                f"=== RECENT CONTEXT (raw thoughts from the author) ===\n"
                f"{recent_context}\n"
                f"Extract real, specific details from this. Build the post around it."
            )

        if history_blacklist:
            parts.append(
                f"=== RECENTLY POSTED CONTENT (DO NOT REPEAT) ===\n"
                f"{history_blacklist}\n"
                f"Write posts about entirely different angles, ideas, or problems."
            )

        # 4. High-Converting LinkedIn Hook & Formatting Rules
        parts.append(
            "=== HIGH-CONVERTING LINKEDIN HOOK & FORMATTING RULES (non-negotiable) ===\n"
            "The first 1–2 lines determine 90% of a LinkedIn post's reach. They MUST compel the reader to click '...see more'.\n"
            "RULES FOR THE HOOK:\n"
            "1. Must be under 15 words and followed immediately by a blank line (\\n\\n).\n"
            "2. NEVER start with a question (e.g. 'Have you ever wondered...?').\n"
            "3. NEVER use generic AI intros (e.g. 'I've been thinking about...', 'In today's landscape...').\n"
            "4. FORMATTING & TONE CONSTRAINTS:\n"
            "   • SPACING: Every paragraph is 1–3 sentences. You MUST leave exactly one blank line between each paragraph (using escape sequence \\n\\n in the JSON string). Do NOT combine everything into a single wall of text.\n"
            "   • LINKS: NEVER put any URL, domain name, or link in the post body. Mention 'link in comments' if you need to reference something.\n"
            "   • HASHTAGS: Include 1–3 relevant hashtags at the very end of the post, on a new line (\\n\\n#hashtag1 #hashtag2).\n"
            "   • EMOJIS: STRICT CONSTRAINT: NEVER use any emojis in the post. Keep the text 100% plain text.\n"
            "   • NO MARKDOWN: Do not use **bold**, *italic*, or ``` code blocks. LinkedIn does not render markdown. Keep everything as raw text.\n"
            "   • LENGTH: 150–400 words per post. Enough to be substantial, not a wall of text.\n"
            "   • CTA: End with one specific, open-ended question that invites real replies — not 'What do you think?' or 'Drop a comment below'.\n"
            f"   • BANNED WORDS: NEVER use any of these: {banned_str}.\n"
            "   • BURSTINESS: Mix short punchy sentences with longer descriptive ones. Include specific real details."
        )

        # 5. Task & JSON wrapper instructions
        task_parts = [
            f"=== TASK ===\n"
            f"Topic: {topic}\n"
            f"Tone: {tone} — {tone_desc}"
        ]
        if topic_is_source_of_truth:
            task_parts.append(
                "Use the topic text as the primary source of truth. Build the post around that exact incident or idea. "
                "You may only pull in supporting details from the compact profile when they clearly connect to the topic. "
                "Do not broaden into unrelated backlog facts."
            )
        if extra_instructions:
            task_parts.append(f"Extra instructions: {extra_instructions}")
            
        task_parts.append(
            f"\nWrite exactly {batch_size} unique LinkedIn posts that fit all the guidelines above.\n\n"
            f"If batch_size is greater than 1, each post must use a meaningfully different angle, opening line, and primary fact cluster.\n\n"
            f"Return ONLY a valid JSON array of objects with this structure:\n"
            f"[\n"
            f"  {{\n"
            f"    \"post_text\": \"The complete raw text of the post. You MUST use escape sequence \\n\\n for paragraph breaks and hook separation so it does not render as a single continuous block of text.\",\n"
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
        """Call Gemini requesting structured JSON output with automatic model fallback."""
        models_to_try = [
            "gemini-3.1-flash-lite-preview",
            config.GEMINI_MODEL,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
        
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)
                
        last_error = None
        for model in unique_models:
            try:
                print(f"[ai_generator] Trying model: {model}")
                return self._call_with_retry(
                    model=model,
                    contents=prompt,
                    response_config={"response_mime_type": "application/json"}
                )
            except Exception as e:
                print(f"[ai_generator] Model {model} failed: {e}. Trying fallback...")
                last_error = e
                
        if genai_errors and isinstance(last_error, genai_errors.APIError):
            raise RuntimeError(f"Gemini API error (all fallbacks exhausted): {last_error}")
        raise RuntimeError(f"Unexpected error from Gemini (all fallbacks exhausted): {last_error}")

    def _call_gemini_plain(self, prompt: str) -> str:
        """Call Gemini requesting plain text output with automatic model fallback."""
        models_to_try = [
            "gemini-3.1-flash-lite-preview",
            config.GEMINI_MODEL,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
        
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)
                
        last_error = None
        for model in unique_models:
            try:
                print(f"[ai_generator] Trying model: {model}")
                return self._call_with_retry(
                    model=model,
                    contents=prompt,
                )
            except Exception as e:
                print(f"[ai_generator] Model {model} failed: {e}. Trying fallback...")
                last_error = e
                
        if genai_errors and isinstance(last_error, genai_errors.APIError):
            raise RuntimeError(f"Gemini API error (all fallbacks exhausted): {last_error}")
        raise RuntimeError(f"Unexpected error from Gemini (all fallbacks exhausted): {last_error}")


