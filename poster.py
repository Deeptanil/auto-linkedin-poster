import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import config

class LinkedInPoster:
    def __init__(self, headed: bool = False):
        self.headed = headed
        self.session_dir = str(config.SESSION_DIR)
        
        # Ensure session directory exists
        config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create screenshots folder inside session dir or parent dir
        self.screenshots_dir = config.BASE_DIR / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)

    def setup_session(self):
        """
        Launches a headed browser to let the user log in manually.
        Once the user is logged in, they can press Enter in the CLI to save the state.
        """
        print("\n" + "="*60)
        print("LINKEDIN INITIAL SESSION SETUP")
        print("="*60)
        print("This will launch a headed browser. Please perform the following steps:")
        print("1. Log in to your personal LinkedIn account in the browser window.")
        print("2. Complete any Multi-Factor Authentication (MFA) or CAPTCHAs if prompted.")
        print("3. Verify you are redirected to your LinkedIn Feed homepage.")
        print("4. Return to this console and press [ENTER] to save the login session.")
        print("="*60 + "\n")

        with sync_playwright() as p:
            # We use launch_persistent_context to store cookies and session state
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=False,
                channel="chrome",  # Attempt to use installed Chrome for maximum realism
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            page = context.new_page()
            
            try:
                page.goto("https://www.linkedin.com/login")
            except Exception as e:
                # If Chrome channel is not found, fallback to default chromium
                context.close()
                print("Defaulting to standard Chromium browser bundle...")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    headless=False,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.new_page()
                page.goto("https://www.linkedin.com/login")

            input("Press [ENTER] here in the console once you have successfully logged in and are on the Feed page...")
            
            # Save cookies/state and close browser
            context.close()
            print("Session saved successfully!")

    def post_to_linkedin(self, text: str) -> bool:
        """
        Logs into LinkedIn automatically using the saved session and posts the text.
        """
        print("Starting automated posting process...")
        
        success = False
        screenshot_path = self.screenshots_dir / f"post_attempt_{int(time.time())}.png"

        with sync_playwright() as p:
            # Launch persistent context using saved cookies/state
            # Set headless depending on preferences (default True for automation, false for viewing)
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    headless=not self.headed,
                    channel="chrome",
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )
            except Exception:
                # Fallback to standard chromium if Chrome is not available
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    headless=not self.headed,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )

            page = context.new_page()
            
            # Optional: modify navigator.webdriver property to bypass basic detection
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                print("Navigating to LinkedIn Feed...")
                page.goto(config.LINKEDIN_FEED_URL, wait_until="domcontentloaded")
                
                # Wait for navigation / load
                page.wait_for_timeout(3000)

                # Check if we are logged in (look for search bar, profile photo, or post triggers)
                is_logged_in = False
                login_indicators = [
                    "input.search-global-typeahead__input",
                    "button.share-box-feed-entry__trigger",
                    "div.feed-identity-module",
                    "a[data-global-nav-item='home']"
                ]
                
                for selector in login_indicators:
                    try:
                        if page.locator(selector).first.is_visible(timeout=2000):
                            is_logged_in = True
                            break
                    except Exception:
                        continue
                
                if not is_logged_in:
                    print("Error: Could not verify active LinkedIn session. You may need to log in again.")
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved diagnostic screenshot to {screenshot_path}")
                    context.close()
                    return False

                print("Session verified! Initiating post creation...")

                # 1. Click "Start a post"
                # We try multiple selectors to handle changes in LinkedIn's layout
                post_trigger = None
                selectors_trigger = [
                    "button.share-box-feed-entry__trigger",  # Desktop feed input trigger
                    "button:has-text('Start a post')",
                    "span:has-text('Start a post')",
                    "div.share-box-feed-entry__avatar + button"
                ]
                
                for sel in selectors_trigger:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=3000):
                            post_trigger = loc
                            break
                    except Exception:
                        continue
                
                if not post_trigger:
                    raise Exception("Could not find 'Start a post' button trigger.")

                post_trigger.click()
                print("Clicked 'Start a post'. Waiting for editor modal...")

                # 2. Wait for editor to appear and enter text
                # Typically a div with class ql-editor, or role=textbox
                editor = None
                selectors_editor = [
                    "div.ql-editor",
                    "div[role='textbox'][aria-label='Editor content; type text here...']",
                    "div[role='textbox']",
                    ".share-editor__textbox"
                ]
                
                for sel in selectors_editor:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=4000):
                            editor = loc
                            break
                    except Exception:
                        continue

                if not editor:
                    raise Exception("Could not locate LinkedIn text editor box in modal.")

                editor.click()
                
                # Fill content. Type it slowly/realistically or use fill
                # fill is faster and usually reliable
                editor.fill(text)
                print("Draft inserted into editor.")
                page.wait_for_timeout(1500) # Wait a bit for UI to process

                # 3. Locate and click the "Post" button
                post_button = None
                selectors_post = [
                    "button.share-actions__post-button",  # standard post button
                    "button:has-text('Post')",
                    "div.share-box_actions button",
                    "button.share-box_actions__post-button"
                ]
                
                for sel in selectors_post:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=3000) and loc.is_enabled():
                            post_button = loc
                            break
                    except Exception:
                        continue

                if not post_button:
                    raise Exception("Could not locate enabled 'Post' button.")

                print("Clicking 'Post' button...")
                post_button.click()
                
                # 4. Wait for post to complete (modal closing or success toast)
                print("Waiting for post confirmation...")
                # We can check if the editor becomes hidden or if a toast appears
                page.wait_for_timeout(3000)
                
                # Verify that the modal is closed (the editor is no longer visible)
                if not editor.is_visible(timeout=5000):
                    print("Post successfully shared on LinkedIn!")
                    success = True
                else:
                    # Let's take a screenshot and double check
                    page.screenshot(path=str(screenshot_path))
                    # Try clicking post once more just in case
                    if post_button.is_visible() and post_button.is_enabled():
                        print("Modal still open. Retrying post click...")
                        post_button.click()
                        page.wait_for_timeout(3000)
                        if not editor.is_visible(timeout=3000):
                            print("Post successfully shared on retry!")
                            success = True
                        else:
                            print("Could not verify post completion. Checking screenshots...")
                    else:
                        print("Modal is open, but post button is disabled or missing.")

            except Exception as e:
                print(f"Error during posting sequence: {e}", file=sys.stderr)
                try:
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved error screenshot to {screenshot_path}")
                except Exception as ex:
                    print(f"Failed to save screenshot: {ex}")
            
            finally:
                context.close()
                
        return success
