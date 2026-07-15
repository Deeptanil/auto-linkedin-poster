"""
compactor.py
─────────────
Compacts memory files (voice_profile.md, achievements.md, and new raw text notes)
into a highly token-optimized JSON file: memory/compact_profile.json.

Saves 80%+ on daily API tokens by keeping context sizes under 200 tokens.
"""

import sys
import json
from pathlib import Path
from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.memory_manager import MemoryManager


class MemoryCompactor:
    def __init__(self):
        self.mem = MemoryManager()
        if config.is_gemini_configured():
            self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        else:
            self.client = None

    def compact_all(self, new_raw_input: str = "") -> dict:
        """
        Gathers raw text memory, uses Gemini to merge and compress them
        into a token-optimized JSON schema, and saves to compact_profile.json.
        """
        if not self.client:
            raise ValueError("Gemini API client not configured.")

        print("[compactor] Beginning memory compaction...")
        
        # Load raw files
        voice_profile = self.mem.load_voice_profile()
        achievements  = self.mem.load_achievements()
        current_compact = self.mem.load_compact_profile()

        # If we have absolutely no raw input files and no new text, we skip or clean
        if not voice_profile and not achievements and not new_raw_input:
            print("[compactor] No raw memory resources found. Keeping existing compact profile.")
            return current_compact

        prompt = self._build_compaction_prompt(
            voice_profile,
            achievements,
            new_raw_input,
            current_compact
        )

        try:
            response = self.client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            
            raw_json = response.text.strip()
            
            # Clean markdown JSON wrapping if present
            if raw_json.startswith("```"):
                first_newline = raw_json.find("\n")
                if first_newline != -1:
                    raw_json = raw_json[first_newline:].strip()
                if raw_json.endswith("```"):
                    raw_json = raw_json[:-3].strip()

            compact_data = json.loads(raw_json)
            
            # Basic schema validation
            schema_keys = ["voice_essence", "banned_patterns", "experience_summary", "backlog_facts"]
            for key in schema_keys:
                if key not in compact_data or not isinstance(compact_data[key], list):
                    compact_data[key] = current_compact.get(key, [])

            # Save the new compact profile
            self.mem.save_compact_profile(compact_data)
            print("[compactor] Successfully compacted memory to compact_profile.json.")
            return compact_data

        except Exception as e:
            print(f"[compactor] Compaction API call failed: {e}", file=sys.stderr)
            raise e

    def _build_compaction_prompt(
        self,
        voice_profile: str,
        achievements: str,
        new_raw_input: str,
        current_compact: dict
    ) -> str:
        
        current_compact_str = json.dumps(current_compact, indent=2)

        prompt = f"""
You are an expert database memory compiler for an AI agent.
Your task is to merge new raw notes and structured files into a highly compressed, token-optimized JSON profile.
Your output must be optimized to occupy as few input tokens as possible (~150-250 tokens total) while preserving core details.

=== CURRENT COMPACT MEMORY ===
{current_compact_str}

=== NEW RAW DATA INPUTS ===
1. Raw Voice Profile:
{voice_profile or "(None)"}

2. Raw Achievements/Bio:
{achievements or "(None)"}

3. New Raw Voice Note/Text Input (if any):
{new_raw_input or "(None)"}

=== INSTRUCTIONS ===
1. Analyze the inputs and consolidate/merge all facts and writing guidelines.
2. Structure the output into the following four lists, keeping every list item extremely concise (aim for maximum information density):
   - "voice_essence": Max 5 bullets describing tone, rhythm, and style guidelines (e.g. "Pragmatic, short paragraphs, UX > UI").
   - "banned_patterns": Max 8 specific phrases or buzzwords to avoid (e.g. "leverage", "delve", "hustle hard").
   - "experience_summary": Max 6 bullets of tech stack, co-founded startups (STRAYED, Prettiva & Co.), and active roles.
   - "backlog_facts": Max 12 bullet points of specific, quantitative, or unique technical achievements, challenges, or stories (e.g., "Spent 3 weeks debugging mobile checkout & Razorpay webhook integration for STRAYED", "Wrote Odoo script to automate variant uploads via Excel sheets").
3. DO NOT lose facts from the CURRENT COMPACT MEMORY. Merge and update them with the new details.

Output ONLY a valid JSON object matching the keys above. No markup markdown code blocks, no intros, no notes.
"""
        return prompt
