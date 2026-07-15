# LinkedIn AI Auto-Poster (Human-in-the-Loop & Memory Compactor)

> Post high-quality, authentic-sounding LinkedIn updates daily. Content is generated from your voice/background and compiled into a **token-efficient memory database** to optimize costs. Posts only publish after you manually approve them in your local visual dashboard.

---

## Key Features

- **🛡️ 100% Control (Human-in-the-Loop)**: Posts are *never* published automatically without your manual approval. The schedule loop *only* posts updates you have reviewed and moved to the Approved Queue.
- **⚡ Token-Compact Memory (Cost Saving)**: Consolidates voice styles and achievements from `voice_profile.md` and `achievements.md` into a structured, highly compressed JSON database (`memory/compact_profile.json`). Reduces API prompt sizes from 1,500+ tokens to ~200 tokens, saving **80%+ on API credits**.
- **💻 Local Review Dashboard**: A beautiful local web application (Vanilla CSS dark theme) to review, edit, approve, reject, replenish drafts, add context wins, and sync code to GitHub with 1 click.
- **📅 Daily Automated Post**: Pushes the next approved post from your queue to LinkedIn daily at 9:00 AM IST (3:30 AM UTC). If your approved list is empty, it skips posting and alerts you on Discord.
- **🔄 Auto Expiry Alerts**: Warns you on Discord 14 and 7 days before your 60-day LinkedIn API key expires, so you only have to re-auth once every 2 months.

---

## Visual Dashboard Setup

We've developed a local launcher for you. To open and start editing:

### Step 1: Open the Dashboard locally
Double-click **`run_dashboard.bat`** in the project root. This will:
1. Activate your virtual environment automatically.
2. Verify you have `flask` installed (it will auto-install if missing).
3. Start the server on `http://localhost:5000/`.
4. Open the dashboard in your default browser.

---

## How to use the Dashboard

### 1. Add Context & Compile Memory
On the right sidebar of the Dashboard:
- Write or paste raw voice-to-text transcriptions, notes, or recent wins into the **Add Context / Wins** text area.
- Click **Compact & Save Memory**.
- **What happens:** The system updates your date-stamped context and invokes the AI Compactor to compress your style guidelines, startups, and backlog achievements into the token-efficient `compact_profile.json` database.

### 2. Review and Regenerate Drafts
On the main panel under **Pending Drafts**:
- The AI will always keep a list of **10 drafts** available for you.
- Read through the drafts:
  - **Approve**: Moves the draft into the **Approved Queue** (which the daily poster reads from).
  - **Edit**: Make quick adjustments directly in the text card and click **Save Edit**.
  - **Decline**: Discards the draft. The dashboard will automatically trigger Gemini to generate a fresh replacement draft at the bottom of the list.

### 3. Sync to GitHub
When you are happy with your approved queue:
- Click the **🚀 Sync to GitHub** button at the top right of the dashboard.
- This will automatically stage your queues, commit them, and push them to your repository remote branch.
- Your daily GitHub Actions workflow will instantly see the new approved queue.

---

## Code/Repo Architecture

```
linkedin-poster/
├── .github/workflows/
│   ├── daily-post.yml         # Scheduled runner (posts only approved drafts)
│   └── refresh-token.yml      # Expiry checks & warning alerts
│
├── src/
│   ├── run.py                 # Action entrypoint (posts one approved draft)
│   ├── ai_generator.py        # Prompts Gemini utilizing compact profile
│   ├── compactor.py           # Compresses memories to compact_profile.json
│   ├── memory_manager.py      # App queue & profile database controller
│   └── discord_notifier.py    # Discord webhooks (success/failure/expiry alerts)
│
├── memory/
│   ├── compact_profile.json   # Token-compressed facts and voice rules
│   ├── posts_queue.json       # Holds approved and pending post content lists
│   ├── voice_profile.md       # Raw voice definition
│   └── achievements.md        # Raw achievements list
│
├── dashboard.py               # Local Flask server
├── run_dashboard.bat          # 1-click Windows launcher
└── scripts/setup_token.py     # OAuth token setup utility
```

---

## Token Expiry Cycle
Standard LinkedIn API applications do not receive programmatic refresh tokens. To keep the project 100% free:
1. The system alerts you via Discord **14 days** and **7 days** before your access token expires.
2. When warned, run the script locally to get a fresh 60-day token:
   ```bash
   python scripts/setup_token.py
   ```
3. Copy the output values and update your Repository Secrets.
