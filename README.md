# LinkedIn AI Poster 🚀

A Python-based AI agent that helps you generate, refine, and automatically post content to your personal LinkedIn profile using Gemini API (via the official `google-genai` SDK) and Playwright browser automation.

---

## Features

- **Gemini AI Generation**: Tailor posts using 5 distinct tones (Professional, Technical, Thought Leadership, Casual, Storytelling).
- **Interactive Review & Revision**: Revise posts with iterative AI instructions or edit them manually using Notepad directly from the CLI.
- **Robust Playwright Posting**: Reuses login sessions securely, avoiding credentials-entry on every run, skipping MFA and verification blocks.
- **Diagnostics**: Auto-captures screenshots in a local `screenshots/` directory if posting fails or encounters layout changes.

---

## Setup Instructions

### 1. Installation

Open your terminal (PowerShell or Command Prompt) and run the following:

```bash
# Navigate to this project folder
cd "c:\Users\deep1\Documents\Pupu\linkedin-poster"

# (Recommended) Create and activate a python virtual environment
python -m venv venv
venv\Scripts\activate

# Install the Python dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 2. Configure Environment Variables

1. Open the `.env` file in the project directory.
2. Enter your Gemini API key:
   ```env
   GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere...
   ```
   *Note: If you don't have one, get a free key from [Google AI Studio](https://aistudio.google.com/).*

---

## How to Use

Run the main application:
```bash
python main.py
```

### Step 1: Session Authentication (Do this once)
1. Select **Option 1 (Authenticate & Setup Session)** in the CLI.
2. A headed Chrome/Chromium browser will open.
3. Manually log in to your personal LinkedIn account.
4. If you have MFA/M2FA enabled, complete the verification code.
5. Once you are redirected to the homepage feed, return to the CLI console and press **[ENTER]**.
6. The session cookie state will be stored locally inside the `.playwright_session/` folder. You will not need to log in again.

### Step 2: Write & Post
1. Choose **Option 2 (Generate Post with AI)** or **Option 3 (Post Custom Text)**.
2. Provide a topic, select a tone, and add constraints.
3. Review the generated draft.
4. Choose to **Post it now**, **Revise with AI** (e.g. "make it punchier", "shorten"), or **Edit manually** (this will pop up Windows Notepad for editing. Save and close to sync back).
5. Confirm if you want to watch the browser (headed) or let it post silently (headless).
6. Success! Your post is live on LinkedIn.

---

## File Structure

- `main.py`: Interactive command-line menu loop.
- `ai_generator.py`: Connects with Gemini to draft and revise text.
- `poster.py`: Automates browser login checks and post creation flow.
- `config.py`: Configuration and environment path initialization.
- `requirements.txt`: Python package requirements.
- `.env`: Holds your secret credentials.
- `screenshots/`: Holds visual feedback if errors occur during automation.
