"""
skills_library.py
──────────────────
Extracted and adapted from sergebulaev/linkedin-skills.
Provides structured definitions for:
  • 20 Viral Hook Formulas (F1–F20)
  • 10 Founder Angles & Positioning Strategies
  • Anti-AI Stripper & Humanization Rules
"""

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
    "testament", "beacon", "multifaceted", "paramount", "pivotal",
    "realm", "fostering", "harnessing", "dive deep", "let's dive in",
    "supercharge", "demystify", "reshaping", "groundbreaking",
]

ANTI_AI_HUMANIZER_INSTRUCTIONS = """
STRICT ANTI-AI HUMANIZATION RULES:
1. NO AI CLICHÉS / BUZZWORDS: Never use words like: delve, tapestry, leverage, landscape, unlock, navigate, game-changer, seamless, cutting-edge, empower, elevate, transformational, realm, fostering, beacon, testament.
2. VARY SENTENCE LENGTH (BURSTINESS): Mix 3-word punchy sentences with longer descriptive lines. Never use monotonous rhythmic sentence lengths.
3. WRITING STYLE & TONE: Write like a seasoned human practitioner sharing hard-won knowledge, not an AI marketing assistant. Use direct, clear verbs. Avoid overly polished "corporate speech."
4. HOOK INTEGRITY: The first line must lock attention immediately without fluffy openers like "In today's fast-paced world..." or "Here's a lesson I learned today...".
5. FORMATTING: Use short paragraphs (1-3 sentences max). Use generous line breaks for scannability. Avoid walls of text. Do not over-use emojis (maximum 1-2 per post, or zero).
6. CALL TO ACTION: End with a natural reflection question or genuine discussion prompt. Never sound like a hard-sales pitch.
"""

FOUNDER_ANGLES = {
    "None": {
        "title": "General Audience",
        "description": "Standard high-value post aimed at broad professional reach.",
        "prompt_instruction": ""
    },
    "Reprice Category": {
        "title": "Reprice the Category",
        "description": "Reframe legacy high-cost services/tools with lean modern AI or streamlined alternatives.",
        "prompt_instruction": "Position this post around category repricing: show how traditional high-cost agencies/tools are being replaced by lean, high-velocity modern workflows with specific time or cost numbers."
    },
    "Content to Pipeline": {
        "title": "Content-to-Pipeline",
        "description": "Connect genuine building stories directly to high-intent customer acquisition.",
        "prompt_instruction": "Structure this post to show how sharing real behind-the-scenes building decisions directly converts into trust and high-intent inbound pipeline."
    },
    "Audience of One": {
        "title": "Audience of One",
        "description": "Speak directly to 5-10 ultra-specific high-stakes decision makers (investors, design partners, key hires).",
        "prompt_instruction": "Write specifically for an ultra-targeted decision maker (e.g. VP of Engineering or Series A investor). Prioritize deep credibility and hard truths over broad viral reach."
    },
    "Scarce Shots Math": {
        "title": "The Scarce-Shots Math",
        "description": "Break down why taking fewer, hyper-focused strategic bets wins over high-volume noise.",
        "prompt_instruction": "Emphasize quality math and focus: explain why taking 3 deliberate, high-conviction bets beats executing 50 low-conviction initiatives."
    },
    "Unglamorous Bet": {
        "title": "The Unglamorous Bet",
        "description": "Highlight the boring, manual, or unglamorous backend work that creates massive defensible moats.",
        "prompt_instruction": "Focus on the unglamorous, manual grind behind the product—the un-sexy operational details that competitors ignore but customers love."
    },
    "Limit of Delegation": {
        "title": "The Limit of Delegation",
        "description": "Identify what a founder or lead practitioner can never delegate (vision, core taste, customer intimacy).",
        "prompt_instruction": "Explore the boundary of delegation: explain what core taste, vision, or customer intimacy cannot be handed off to agents or employees."
    },
    "Designed Serendipity": {
        "title": "Designed Serendipity",
        "description": "Show how building transparently in public creates unexpected high-value inbound opportunities.",
        "prompt_instruction": "Illustrate how putting raw progress out in the open created an unexpected breakthrough, key intro, or customer discovery moment."
    },
    "Evasive Sentence Test": {
        "title": "Evasive-Sentence Test",
        "description": "Call out fluff and demand hyper-concrete, unambiguous facts and metrics.",
        "prompt_instruction": "Strip away vague marketing speak and state hyper-concrete numbers, exact failure points, and specific technical decisions."
    },
    "Learning Gate": {
        "title": "The Learning Gate",
        "description": "Share a painful mistake, what it cost, and the strict rule established because of it.",
        "prompt_instruction": "Share a clear mistake or failed hypothesis, quantify the cost in time or money, and state the exact new operational rule adopted."
    }
}

HOOK_FORMULAS = {
    "None": {
        "name": "Standard Organic Hook",
        "goal": "Balanced",
        "skeleton": "Open with a direct, intriguing statement related to the topic.",
        "instruction": ""
    },
    "F1": {
        "name": "F1 — Platform Risk Anaphora",
        "goal": "Comments & Reposts",
        "skeleton": "{Platform1} can throttle you... {Platform2} can change terms... You don't own X. Concrete horror anecdote with real numbers + solution.",
        "instruction": "Use Formula F1 (Platform Risk Anaphora): Open with repeated structural lines highlighting platform risks or fragile dependencies, followed by a concrete loss anecdote with real numbers, ending with your strategic solution."
    },
    "F2": {
        "name": "F2 — R.I.P. Category Obituary",
        "goal": "Reposts & Likes",
        "skeleton": "R.I.P. {category}. Cause of death: {mechanism + stats}. Evidence paragraphs + pivot to new winners.",
        "instruction": "Use Formula F2 (R.I.P. Category Obituary): Declare an old method or category dead in line 1, give specific cause of death with data/dates, admitted former defense, and reveal the new winning playbook."
    },
    "F3": {
        "name": "F3 — Year-over-Year Pivot",
        "goal": "Comments",
        "skeleton": "In {last year}, I {humble benchmark}. In {this year}, I'm {transformational goal}. Here is what changed...",
        "instruction": "Use Formula F3 (Year-over-Year Pivot): Contrast last year's humble benchmark vs this year's ambitious focus in the first 2 lines. Detail the mindset shift with exact metrics and end with a mirror question for comments."
    },
    "F4": {
        "name": "F4 — Time-Anchor Confession",
        "goal": "Comments & Saves",
        "skeleton": "{N} months ago, I stopped {common behavior}. Here is what happened...",
        "instruction": "Use Formula F4 (Time-Anchor Confession): Open with a time-anchored confession of stopping a popular habit. Share concrete backstory metrics, counterintuitive upsides, and ask a reflective question."
    },
    "F5": {
        "name": "F5 — Self-Proving Meta",
        "goal": "Comments",
        "skeleton": "Most LinkedIn posts die because {X}. Not because Y, but because Z. Here is the live test...",
        "instruction": "Use Formula F5 (Self-Proving Meta): Open with a bold claim about post performance or user behavior. Set up a live test where the audience's engagement proves or tests the thesis in real-time."
    },
    "F6": {
        "name": "F6 — Comment-Gate Lead Magnet",
        "goal": "Lead Gen & Comments",
        "skeleton": "[Authority stat] -> Turned workflow into [N named assets] -> Drop key takeaways -> Comment '{keyword}' for full guide.",
        "instruction": "Use Formula F6 (Value Breakdown & Lead Magnet): Open with authority metrics, list 4-6 high-value key takeaways, and invite readers to comment a specific keyword for the full asset."
    },
    "F7": {
        "name": "F7 — Odd-Precision Money Ledger",
        "goal": "Saves & Reposts",
        "skeleton": "Odd specific dollar amount ($873.47). Line-item breakdown of exact spend vs legacy cost.",
        "instruction": "Use Formula F7 (Odd-Precision Money Ledger): Start with an odd, exact dollar figure (e.g. $412.80). Provide a itemized ledger breakdown, compare against expensive legacy alternatives, and close with the core lesson."
    },
    "F8": {
        "name": "F8 — Paid-vs-Free Reversal",
        "goal": "Saves & Likes",
        "skeleton": "I charge clients $X for Y. Today it's free. Here is the exact N-step framework...",
        "instruction": "Use Formula F8 (Paid-vs-Free Reversal): State what you normally charge clients for a service, then share the exact step-by-step framework for free in a clean, bookmarkable checklist format."
    },
    "F9": {
        "name": "F9 — Curiosity-Gap Teaser",
        "goal": "Dwell Time & Likes",
        "skeleton": "Yesterday, our system did something we didn't program it to do...",
        "instruction": "Use Formula F9 (Curiosity-Gap Teaser): Open with a 2-line mysterious event or unexpected discovery. Use sensory anchors (what you saw/felt) and reveal the non-obvious insight."
    },
    "F10": {
        "name": "F10 — Contrarian + Historical Receipts",
        "goal": "Comments & Reposts",
        "skeleton": "Everyone is wrong about {topic}. In 2018, X happened. In 2022, Y happened. Here is what comes next...",
        "instruction": "Use Formula F10 (Contrarian Receipts): Challenge a widespread industry belief, back it up with chronological historical events/receipts, and present a bold 2026 prediction."
    },
    "F11": {
        "name": "F11 — Emotional Cold-Open",
        "goal": "Likes & Reach",
        "skeleton": "I almost quit {project} last Tuesday. Here is the raw truth...",
        "instruction": "Use Formula F11 (Emotional Cold-Open): Open with a raw, unfiltered emotional moment or near-failure. Move quickly from vulnerability to the strategic realization."
    },
    "F12": {
        "name": "F12 — Permission Slip",
        "goal": "Reposts & Saves",
        "skeleton": "You don't need {popular requirement} to achieve {desirable outcome}. Here is what actually matters...",
        "instruction": "Use Formula F12 (Permission Slip): Relieve the reader of an industry myth or unnecessary burden ('You don't need 50k followers to...'). List 4 core things that actually move the needle."
    },
    "F13": {
        "name": "F13 — Bait-and-Switch Reversal",
        "goal": "Likes & Comments",
        "skeleton": "We just fired our top performing X. Best decision of 2026...",
        "instruction": "Use Formula F13 (Bait-and-Switch Reversal): Use a shocking opening line that appears negative or counter-intuitive, then flip the context to reveal an inspiring or smart strategic lesson."
    },
    "F14": {
        "name": "F14 — Named Gratitude / Tribute",
        "goal": "Likes & Reposts",
        "skeleton": "The best advice I received didn't come from a textbook. It came from {Name/Role}...",
        "instruction": "Use Formula F14 (Named Gratitude/Tribute): Attribute a key breakthrough to a mentor, team member, or customer story. Detail the specific lesson and why it changed your trajectory."
    },
    "F15": {
        "name": "F15 — Explain-to-Kids Simplification",
        "goal": "Saves & Reposts",
        "skeleton": "How to explain {complex technical concept} to a 10-year-old...",
        "instruction": "Use Formula F15 (Explain-to-Kids Simplification): Take a complex technical or business concept and explain it using simple analogies, clear step-by-step logic, and zero jargon."
    },
    "F16": {
        "name": "F16 — Status-Strip Humility",
        "goal": "Likes & Comments",
        "skeleton": "Title doesn't protect you from {basic mistake}. I just spent 4 hours fixing...",
        "instruction": "Use Formula F16 (Status-Strip Humility): Show that even experienced leaders get stuck on fundamental mistakes. Detail the simple bug/oversight and what it taught about staying humble."
    },
    "F17": {
        "name": "F17 — Controlled A/B Anecdote",
        "goal": "Saves & Reposts",
        "skeleton": "Team A did X. Team B did Y. 6 months later, here are the results...",
        "instruction": "Use Formula F17 (Controlled A/B Anecdote): Compare two distinct approaches to the same problem side-by-side with clear metrics, highlighting why one approach overwhelmingly won."
    },
    "F18": {
        "name": "F18 — False-Binary Dissolve",
        "goal": "Comments & Reposts",
        "skeleton": "People argue whether you should do A or B. Both are missing the real engine: C.",
        "instruction": "Use Formula F18 (False-Binary Dissolve): Frame a popular debate (Option A vs Option B), dissolve the false tradeoff, and introduce the third hidden leverage point."
    },
    "F19": {
        "name": "F19 — Anecdote-Meets-Evidence Bridge",
        "goal": "Saves & Comments",
        "skeleton": "I thought X was just my personal experience. Then I analyzed 500 cases...",
        "instruction": "Use Formula F19 (Anecdote-Meets-Evidence Bridge): Start with a personal observation or story, then bridge it directly to macro data/case studies that prove it is a broader trend."
    },
    "F20": {
        "name": "F20 — Diverging-Curves Close",
        "goal": "Reposts & Saves",
        "skeleton": "In 2024, path A and path B looked identical. By 2026, the gap is unbridgeable...",
        "instruction": "Use Formula F20 (Diverging-Curves Close): Contrast two trajectories that start out looking similar but compound over time into wildly different outcomes."
    }
}
