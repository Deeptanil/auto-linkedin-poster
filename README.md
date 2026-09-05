# 🚀 LinkedIn AI Auto-Poster (Human-in-the-Loop & Memory Compactor)

> Post authentic, high-impact LinkedIn updates daily. AI generates posts tailored to your voice, which you review, edit, or approve in a local visual dashboard. GitHub Actions automatically publishes approved posts every day—100% free with no monthly subscriptions.

---

## 📋 Table of Contents
- [✨ Key Features](#-key-features)
- [🏁 Beginner Setup Guide (Step-by-Step)](#-beginner-setup-guide-step-by-step)
  - [Step 1: Prerequisites](#step-1-prerequisites)
  - [Step 2: Get Free Gemini AI Key](#step-2-get-free-gemini-ai-key)
  - [Step 3: Create LinkedIn Developer App](#step-3-create-linkedin-developer-app)
  - [Step 4: Generate Your LinkedIn Tokens](#step-4-generate-your-linkedin-tokens)
  - [Step 5: Set Up Environment & GitHub Secrets](#step-5-set-up-environment--github-secrets)
- [💻 Using the Visual Dashboard](#-using-the-visual-dashboard)
- [🔑 LinkedIn Token Maintenance & Renewal](#-linkedin-token-maintenance--renewal)
- [⚙️ Environment Variables & Secrets Reference](#%EF%B8%8F-environment-variables--secrets-reference)
- [📁 Repository Structure](#-repository-structure)

---

## ✨ Key Features

- **🛡️ Human-in-the-Loop Safety**: Posts are *never* published without your explicit manual approval.
- **⚡ Token-Compact Memory**: Compresses voice style and achievements into `memory/compact_profile.json`, cutting AI prompt sizes by **80%+**.
- **🎯 20 Viral Hook Formulas (F1–F20)**: Built-in library of structural hook frameworks (Platform Risk Anaphora, Paid-vs-Free Reversal, Self-Proving Meta, False-Binary Dissolve, etc.) adapted from `linkedin-skills`.
- **🚀 10 Founder Positioning Angles**: Dedicated founder strategy mode (Reprice Category, Content-to-Pipeline, Audience of One, Scarce Shots Math, Learning Gate, etc.).
- **🧹 Anti-AI Fingerprint Stripper**: Removes 40+ banned AI buzzwords ("delve", "tapestry", "seamless", "game-changer") and enforces natural bursty sentence structure.
- **💻 Visual Dashboard**: Easy-to-use local web app (dark mode) to write wins, select viral hooks, approve posts, and sync to GitHub with 1 click.
- **📅 Automated Daily Posting**: Scheduled GitHub Actions workflow posts one approved update every morning at 9:00 AM IST (3:30 AM UTC).
- **🔔 Discord Notifications**: Sends instant alerts for successful posts, empty queues, or token expiry warnings.

---

## 🏁 Beginner Setup Guide (Step-by-Step)

If you've never used Python, GitHub Actions, or APIs before, follow these steps sequentially.

### Step 1: Prerequisites
Make sure you have installed:
1. **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/) *(Check "Add Python to PATH" during installation)*.
2. **Git**: Download from [git-scm.com](https://git-scm.com/).
3. **A GitHub Account**: Sign up at [github.com](https://github.com/).

Clone the repository and install dependencies:
```bash
git clone https://github.com/YOUR_USERNAME/linkedin-poster.git
cd linkedin-poster
python -m venv venv
```
Activate virtual environment:
- **Windows**: `venv\Scripts\activate`
- **Mac/Linux**: `source venv/bin/activate`

Install requirements:
```bash
pip install -r requirements.txt
```

---

### Step 2: Get Free Gemini AI Key
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with your Google account.
3. Click **Create API key**.
4. Copy the generated key. (You will save this in `.env` and GitHub Secrets later).

---

### Step 3: Create LinkedIn Developer App
To post automatically, LinkedIn requires developer API keys. Setting it up takes ~3 minutes:

1. Visit the [LinkedIn Developer Portal](https://developer.linkedin.com/).
2. Click **Create App** (top right).
3. Fill in the form:
   - **App Name**: e.g., `My Auto Poster`
   - **LinkedIn Page**: Select or search for your LinkedIn company page. *(If you don't have one, go to LinkedIn, click "Work" -> "Create a Company Page", name it anything, and select it here).*
   - **App Logo**: Upload any square PNG image.
4. Click **Create App**.
5. **Enable Products**:
   - Go to the **Products** tab in your app header.
   - Click **Request Access** for **Share on LinkedIn**.
   - Click **Request Access** for **Sign In with LinkedIn using OpenID Connect**.
6. **Configure OAuth Redirect URI**:
   - Go to the **Auth** tab.
   - Under **OAuth 2.0 settings**, click the edit icon next to **Authorized redirect URLs for your app**.
   - Add: `http://localhost:8765/callback`
   - Click **Update**.
7. **Copy App Credentials**:
   - Under the **Auth** tab, locate **Client ID** and **Client Secret** (click eye icon to reveal secret).

---

### Step 4: Generate Your LinkedIn Tokens
You can generate your tokens in 2 easy ways:

#### Option A: Via Visual Dashboard (Recommended)
1. Open the dashboard by running `run_dashboard.bat` (or `python dashboard.py`).
2. Click the **🔑 LinkedIn Token** button in the header bar (or click "Checking..." under System Status).
3. Enter your **Client ID** and **Client Secret**.
4. Click **🚀 Launch OAuth & Generate Token**. Your browser opens automatically for LinkedIn approval.
5. Once approved, the dashboard automatically saves the token to `.env` and provides a 1-click **📋 Copy GitHub Secrets** button!

#### Option B: Via Terminal Script
Run the built-in helper script:
```bash
python scripts/setup_token.py
```
1. Paste your **Client ID** and **Client Secret** when prompted.
2. Your browser will automatically open to LinkedIn's login/consent page.
3. Click **Allow**.
4. The terminal will capture the response, display your generated tokens, and offer to save them to `.env`.

---

### Step 5: Set Up Environment & GitHub Secrets

#### A. Local Setup (`.env`)
Create a file named `.env` in the root folder (or let `setup_token.py` create it) with the following variables:

```env
GEMINI_API_KEY=your_gemini_api_key_here
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here
LINKEDIN_ACCESS_TOKEN=your_access_token_here
LINKEDIN_REFRESH_TOKEN=your_refresh_token_here
LINKEDIN_MEMBER_URN=urn:li:person:YOUR_MEMBER_ID
LINKEDIN_TOKEN_EXPIRY=2026-10-30T00:00:00+00:00
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_DETAILS
```

#### B. GitHub Actions Setup (For Daily Automated Posting)
To let GitHub post automatically every day:
1. Open your repository on **GitHub.com**.
2. Go to **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** for each item below:

| Secret Name | Value |
| :--- | :--- |
| `GEMINI_API_KEY` | Your Google Gemini API Key |
| `LINKEDIN_CLIENT_ID` | LinkedIn App Client ID |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn App Client Secret |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn Access Token from Step 4 |
| `LINKEDIN_REFRESH_TOKEN` | LinkedIn Refresh Token from Step 4 |
| `LINKEDIN_MEMBER_URN` | Your `urn:li:person:XXXXX` ID |
| `LINKEDIN_TOKEN_EXPIRY` | ISO Expiry date output by Step 4 |
| `DISCORD_WEBHOOK_URL` | Optional Discord Webhook for alerts |

---

## 💻 Using the Visual Dashboard

Manage all your posts locally without opening any code.

### Launching the Dashboard
- **Windows**: Double-click **`run_dashboard.bat`**
- **Mac / Linux**: Run `python dashboard.py` in your terminal.

Your default browser will open automatically at `http://localhost:5000/`.

### Dashboard Workflow
1. **Add Context & Compress Memory**:
   - Paste notes, achievements, or voice recordings into **Add Context / Wins**.
   - Click **Compact & Save Memory**.
2. **Review Pending Drafts**:
   - **Approve**: Moves draft into the **Approved Queue**.
   - **Edit**: Adjust post text inline and click **Save Edit**.
   - **Decline**: Removes draft and automatically generates a fresh AI replacement.
3. **Sync to GitHub**:
   - Click **🚀 Sync to GitHub** (top right) to push your approved queue to GitHub.

---

## 🔑 LinkedIn Token Maintenance & Renewal

LinkedIn API tokens last for **60 days**.

### How Token Renewal Works
1. **Automatic Discord Notifications**: The system checks token health daily and sends Discord alerts **14 days** and **7 days** before expiry.
2. **Renewing Your Token (< 1 minute)**:
   When alerted, run the setup script again:
   ```bash
   python scripts/setup_token.py
   ```
3. Enter your Client ID & Secret, grant permission in the browser, copy the new `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_TOKEN_EXPIRY`, and update them in your **GitHub Repository Secrets**.

---

## ⚙️ Environment Variables & Secrets Reference

| Variable / Secret Name | Required | Description |
| :--- | :---: | :--- |
| `GEMINI_API_KEY` | Yes | Google Gemini AI key used to draft & compact posts. |
| `LINKEDIN_CLIENT_ID` | Yes | OAuth Client ID from LinkedIn Developer Portal. |
| `LINKEDIN_CLIENT_SECRET` | Yes | OAuth Client Secret from LinkedIn Developer Portal. |
| `LINKEDIN_ACCESS_TOKEN` | Yes | 60-day OAuth token used to publish posts. |
| `LINKEDIN_REFRESH_TOKEN` | Optional | Refresh token (if granted by LinkedIn). |
| `LINKEDIN_MEMBER_URN` | Yes | Unique LinkedIn Person URN (`urn:li:person:...`). |
| `LINKEDIN_TOKEN_EXPIRY` | Yes | Expiry timestamp in ISO format. |
| `DISCORD_WEBHOOK_URL` | Optional | Discord webhook link for posting status & expiry warnings. |

---

## 📁 Repository Structure

```
linkedin-poster/
├── .github/workflows/
│   ├── daily-post.yml         # Scheduled daily posting workflow
│   └── refresh-token.yml      # Daily token health & expiry warnings check
│
├── src/
│   ├── run.py                 # Core script to publish one approved post
│   ├── ai_generator.py        # Gemini AI post generator
│   ├── compactor.py           # Memory compaction engine
│   ├── memory_manager.py      # Post queue & profile manager
│   └── discord_notifier.py    # Discord webhook notifier
│
├── memory/
│   ├── compact_profile.json   # Token-compressed facts & voice guidelines
│   ├── posts_queue.json       # Approved & pending posts storage
│   ├── voice_profile.md       # Raw voice definition
│   └── achievements.md        # Raw achievements list
│
├── scripts/
│   └── setup_token.py         # OAuth2 browser setup & token generator script
├── dashboard.py               # Flask local visual dashboard
├── run_dashboard.bat          # 1-click Windows dashboard launcher
└── requirements.txt           # Python dependencies
```
