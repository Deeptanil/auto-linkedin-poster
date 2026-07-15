import os
import sys
from google import genai
from google.genai import errors
import config

class AIGenerator:
    def __init__(self):
        if not config.is_configured():
            self.client = None
        else:
            try:
                # Initialize the Google GenAI client using the configured key
                self.client = genai.Client(api_key=config.GEMINI_API_KEY)
            except Exception as e:
                self.client = None
                print(f"Error initializing Gemini Client: {e}", file=sys.stderr)

    def generate_post(self, topic: str, tone: str = "Professional", extra_instructions: str = "") -> str:
        """
        Generate a LinkedIn post based on a topic, tone, and optional extra instructions.
        """
        if not self.client:
            raise ValueError("Gemini API Client is not configured. Please set GEMINI_API_KEY in your .env file.")

        # System-like instructions embedded in the prompt to guide the model on LinkedIn formatting rules
        system_instruction = (
            "You are an expert LinkedIn content creator and ghostwriter. Your goal is to write highly engaging, "
            "professional, and high-converting LinkedIn posts that resonate with industry professionals, founders, and developers.\n\n"
            "LinkedIn Formatting Constraints:\n"
            "1. Hook: Start with a strong, single-line opening hook. Leave a blank line after it.\n"
            "2. Spacing: Break paragraphs into single sentences or short 2-line blocks to make it highly readable and scannable on mobile/web.\n"
            "3. Formatting: Use bullet points (using clean emojis or unicode symbols) for lists.\n"
            "4. Tone: Keep it authentic, avoiding overly corporate speak or cheesy hype.\n"
            "5. Call to Action (CTA): End with a thought-provoking question or clear call to action to spark comments.\n"
            "6. Hashtags: Include 2-4 relevant, high-traffic hashtags at the very end.\n"
            "7. Emojis: Use emojis sparingly and taste-fully to emphasize points (max 1-2 per section), never spam them.\n"
            "8. Markdown: Do NOT use markdown bold/italic syntax (like **text**) for formatting words, as LinkedIn does not render markdown. Keep the text raw, or use standard capitalization/emojis for emphasis."
        )

        tone_guidelines = {
            "Professional": "Authoritative, insightful, objective, and industry-focused. Sounds like an experienced executive or researcher.",
            "Technical": "Detail-oriented, educational, pragmatic, and developer-friendly. Focuses on code, architecture, solutions, and lessons learned.",
            "Thought Leadership": "Visionary, challenging the status quo, sharing contrarian viewpoints, or predicting trends with strong reasons.",
            "Casual/Conversational": "Friendly, relatable, humble, and warm. Sounds like chatting with a colleague over coffee. Uses self-deprecating humor or personal anecdotes.",
            "Storytelling": "Narrative-driven. Starts with a conflict/problem, describes the journey/struggle, and ends with the resolution/lesson learned (the classic hero's journey framework)."
        }

        tone_desc = tone_guidelines.get(tone, tone_guidelines["Professional"])

        full_prompt = (
            f"{system_instruction}\n\n"
            f"--- TASK ---\n"
            f"Create a LinkedIn post on the following topic:\n"
            f"Topic: \"{topic}\"\n\n"
            f"Tone: {tone} ({tone_desc})\n"
        )

        if extra_instructions:
            full_prompt += f"Additional Guidelines: {extra_instructions}\n"

        full_prompt += "\nOutput ONLY the text of the LinkedIn post. Do not include markdown code block syntax (like ```) or introductory notes like 'Here is your post:'."

        try:
            # We use gemini-2.5-flash as the default model
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            return response.text.strip()
        except errors.APIError as e:
            raise RuntimeError(f"Gemini API error occurred: {e}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while generating: {e}")

    def revise_post(self, original_post: str, revision_instructions: str) -> str:
        """
        Revise an existing post based on user feedback.
        """
        if not self.client:
            raise ValueError("Gemini API Client is not configured. Please set GEMINI_API_KEY in your .env file.")

        prompt = (
            "You are editing a draft LinkedIn post. Keep the general formatting rules (strong hook, single-sentence spacing, taste-ful emojis, no markdown bold/italics).\n\n"
            f"--- ORIGINAL DRAFT ---\n"
            f"{original_post}\n\n"
            f"--- REVISION INSTRUCTIONS ---\n"
            f"{revision_instructions}\n\n"
            "Apply these instructions to rewrite the draft. Output ONLY the revised post. Do not include markdown code blocks or introductory text."
        )

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text.strip()
        except errors.APIError as e:
            raise RuntimeError(f"Gemini API error occurred: {e}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while revising: {e}")
