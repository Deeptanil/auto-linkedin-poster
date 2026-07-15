# LinkedIn AI Auto-Poster

> Post high-quality, human-sounding LinkedIn content daily — AI-generated from *your* voice, *your* recent context, *your* achievements. Runs on GitHub Actions. 100% free.

---

## What This Does

- **Daily automated post** to your LinkedIn profile at 9:00 AM IST
- **AI-powered** (Gemini 2.5 Flash) — generates posts that don't sound like AI
- **You stay in control** — feed it your raw thoughts, it structures them
- **Persistent memory** — remembers your voice, achievements, and recent wins
- **Discord alerts** — warns you before tokens expire, notifies every post
- **Auto token refresh** — handles LinkedIn's 60-day access token expiry automatically

---

## Architecture

```
You (GitHub UI)
    │
    ├── [Add Context workflow]  → memory/contexts/YYYY-MM-DD.md
    ├── [Daily Post workflow]   → reads memory/ → Gemini → LinkedIn API
    └── [Token Refresh workflow] → auto-refreshes + updates GitHub Secrets
```

---

## Setup Guide

### Prerequisites
- A GitHub account with this repo (public or private)
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key (Gemini — free)
- A Discord server with a webhook URL (for notifications)

---

### Step 1: Create a LinkedIn Developer App

1. Go to [developer.linkedin.com](https://developer.linkedin.com/) → **Create App**
2. Give it a name (e.g. "My Auto Poster") and link to any company page
3. Under **Products** tab → add:
   - ✅ **Share on LinkedIn**
   - ✅ **Sign In with LinkedIn using OpenID Connect**
4. Under **Auth** tab → scroll to **OAuth 2.0 Settings** → add this redirect URI:
   ```
   http://localhost:8765/callback
   ```
5. Note down your **Client ID** and **Client Secret**

---

### Step 2: Run the OAuth Setup Script (once)

On your local machine:

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/linkedin-poster.git
cd linkedin-poster

# Install dependencies
pip install -r requirements.txt

# Run the setup script
python scripts/setup_token.py
```

The script will:
1. Ask for your Client ID and Client Secret
2. Open your browser to LinkedIn's auth page
3. Catch the callback automatically
4. Print all the values you need to add as GitHub Secrets

---

### Step 3: Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add ALL of these:

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | From [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `LINKEDIN_CLIENT_ID` | From your LinkedIn App |
| `LINKEDIN_CLIENT_SECRET` | From your LinkedIn App |
| `LINKEDIN_ACCESS_TOKEN` | From `setup_token.py` output |
| `LINKEDIN_REFRESH_TOKEN` | From `setup_token.py` output |
| `LINKEDIN_TOKEN_EXPIRY` | From `setup_token.py` output (ISO datetime) |
| `LINKEDIN_REFRESH_TOKEN_EXPIRY` | From `setup_token.py` output |
| `LINKEDIN_MEMBER_URN` | From `setup_token.py` output (e.g. `urn:li:person:XXXX`) |
| `DISCORD_WEBHOOK_URL` | From Discord → Server Settings → Integrations → Webhooks |

---

### Step 4: Fill In Your Voice Profile

Edit `memory/voice_profile.md` — this is the most important file.
It defines how the AI writes *as you*. Fill in:
- Who you are professionally
- Your writing style (3-5 descriptors)
- Words/phrases you'd never say
- Words/phrases you actually use
- What topics you post about

The more specific, the better. See the template for guidance.

---

### Step 5: Fill In Your Achievements

Edit `memory/achievements.md` with:
- Projects you've built
- Your professional background
- Notable wins (with dates)

The AI uses this as background credibility. Update it when you hit new milestones.

---

### Step 6: Test with a Dry Run

Go to **GitHub Actions** → **"📅 Daily LinkedIn Post"** → **Run workflow**

Set `dry_run = true` and optionally add some context. This generates a post but **doesn't publish it** — you'll see it in the Action logs.

---

## Daily Usage

### Option A: Add Context (Most Common)
Go to **Actions** → **"🧠 Add Context / Memory"** → **Run workflow**

Fill in the text box with whatever you've been up to:
```
Just shipped the authentication system for my app.
Took 3 weeks of debugging JWT refresh tokens.
The key lesson: silent token rotation is the way.
Also got 2 new beta users today.
```

The AI will pick this up and post about it tomorrow morning.

### Option B: Post Right Now
Go to **Actions** → **"📅 Daily LinkedIn Post"** → **Run workflow**

Fill in:
- `context`: what you want to post about
- `tone`: Storytelling / Technical / Professional / etc.
- `extra_notes`: any specific instructions

### Option C: Fully Automatic
Just leave it. Every day at 9:00 AM IST, the workflow runs automatically.
It picks up the most recent context file you've added and generates a post from it.

---

## Token Management

LinkedIn access tokens expire every **60 days**. The system handles this automatically:

1. **Weekly health check** (every Monday) — `refresh-token.yml` runs automatically
2. If the token is within 14 days of expiry → Discord warning sent
3. If within 10 days → access token auto-refreshed using refresh token
4. **Refresh token** (365 days) → Discord warning sent 30 days before expiry
5. When refresh token expires, run `python scripts/setup_token.py` again (once per year)

> **You never need to think about tokens** — just watch for Discord alerts.

---

## Memory Structure

```
memory/
├── voice_profile.md      ← Your personal writing style (fill this in)
├── achievements.md       ← Your background and wins (fill this in)
├── contexts/
│   ├── 2026-07-15.md    ← Context you added on July 15
│   └── 2026-07-16.md    ← Context you added on July 16
└── post_history.json     ← Auto-generated log of all posts
```

---

## Cost

| Service | Cost |
|---|---|
| GitHub Actions | Free (2,000 min/month on private repos — this uses ~2 min/day) |
| Gemini 2.5 Flash | Free tier (1M tokens/day) |
| LinkedIn API | Free |
| Discord Webhooks | Free |
| **Total** | **$0** |

---

## Local CLI

The original interactive CLI (`main.py`) still works for local use:

```bash
python main.py
```

Options:
1. Authenticate & setup session (Playwright browser)
2. Generate post with AI
3. Post custom text

---

## LinkedIn Best Practices (Built In)

The AI is pre-configured with all current best practices:

- ✅ **Hooks under 15 words** — uses tension/numbers, not questions
- ✅ **No links in post body** — links go in the first comment
- ✅ **1-3 hashtags only** — no spam
- ✅ **Short paragraphs** — mobile-optimized
- ✅ **No AI buzzwords** — "leverage", "delve", "tapestry" etc. are banned
- ✅ **Specificity injection** — real dates, numbers, names make posts unique
- ✅ **Burstiness** — varied sentence lengths for human-sounding rhythm
