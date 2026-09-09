import os
import sys
import tempfile
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.table import Table

import config
from src.ai_generator import AIGenerator
from poster import LinkedInPoster

console = Console()

def display_header():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🚀 LINKEDIN POST PUBLISHER & MANAGER[/bold cyan]\n"
        "[dim]Powered by Gemini & LinkedIn REST API[/dim]",
        border_style="cyan"
    ))

def check_setup():
    """Checks and warns the user if the environment is not configured."""
    if not config.is_configured():
        console.print("[yellow]⚠️ Warning: GEMINI_API_KEY is not set in your .env file.[/yellow]")
        console.print("[dim]AI Post generation features will not work until you add your key.[/dim]\n")
        return False
    return True

def run_login_setup():
    """Guide the user to log in and save the session context."""
    poster = LinkedInPoster(headed=True)
    poster.setup_session()

def edit_manually(initial_text: str) -> str:
    """
    Writes the post text to a temporary file, opens Notepad (Windows),
    and reads the modified text back once the editor is closed.
    """
    console.print("\n[bold yellow]Opening Notepad for editing...[/bold yellow]")
    console.print("[dim]Edit the post, save the file (Ctrl+S), and close the editor to return to this script.[/dim]")
    
    temp_file = config.BASE_DIR / "temp_draft.txt"
    try:
        temp_file.write_text(initial_text, encoding="utf-8")
        
        # Open in Notepad (since the user is on Windows)
        subprocess.run(["notepad.exe", str(temp_file)], check=True)
        
        # Read edited content
        edited_text = temp_file.read_text(encoding="utf-8")
        return edited_text.strip()
    except Exception as e:
        console.print(f"[red]Error opening text editor: {e}[/red]")
        console.print("Please copy the draft and edit it elsewhere.")
        return initial_text
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass

def handle_post_options(post_text: str, ai_gen: AIGenerator) -> str:
    """
    Sub-menu for reviewing, revising, editing, and posting a draft.
    """
    while True:
        console.clear()
        display_header()
        
        console.print("[bold green]📄 CURRENT DRAFT:[/bold green]")
        console.print(Panel(post_text, border_style="green", expand=False))
        
        console.print("\n[bold]Options:[/bold]")
        console.print("1. [bold green]🚀 Post it to LinkedIn now[/bold green]")
        console.print("2. [bold cyan]✍️ Revise post with AI instructions[/bold cyan]")
        console.print("3. [bold yellow]✏️ Edit post manually (via Notepad)[/bold yellow]")
        console.print("4. [bold magenta]💾 Save draft to file[/bold magenta]")
        console.print("5. [bold red]❌ Discard and return to main menu[/bold red]")
        
        choice = Prompt.ask("\nChoose an option", choices=["1", "2", "3", "4", "5"], default="1")
        
        if choice == "1":
            # Post to LinkedIn
            headed_confirm = Confirm.ask("Would you like to watch the browser while posting? (Headed mode)", default=False)
            poster = LinkedInPoster(headed=headed_confirm)
            
            with console.status("[bold green]Posting to LinkedIn... This may take a few seconds...[/bold green]"):
                success = poster.post_to_linkedin(post_text)
                
            if success:
                console.print("\n[bold green]✅ Post shared successfully![/bold green]")
                Prompt.ask("\nPress [ENTER] to return to the main menu")
                return ""
            else:
                console.print("\n[bold red]❌ Failed to post automatically. Please verify your login session via option 1 in the main menu or check the screenshot saved in the screenshots directory.[/bold red]")
                Prompt.ask("\nPress [ENTER] to return to the review menu")
                
        elif choice == "2":
            # Revise with AI
            if not config.is_configured():
                console.print("[red]Error: Gemini API Key not set. Cannot revise.[/red]")
                Prompt.ask("\nPress [ENTER] to go back")
                continue
                
            revision_prompt = Prompt.ask("\nWhat changes would you like to make? (e.g., 'make it shorter', 'add technical details')")
            with console.status("[bold cyan]Revising post with Gemini...[/bold cyan]"):
                try:
                    post_text = ai_gen.revise_post(post_text, revision_prompt)
                except Exception as e:
                    console.print(f"[red]Error revising: {e}[/red]")
                    Prompt.ask("\nPress [ENTER] to return")
                    
        elif choice == "3":
            # Edit manually
            post_text = edit_manually(post_text)
            
        elif choice == "4":
            # Save draft
            filename = Prompt.ask("Enter filename to save as", default="linkedin_post_draft.txt")
            if not filename.endswith(".txt"):
                filename += ".txt"
            draft_path = config.BASE_DIR / filename
            try:
                draft_path.write_text(post_text, encoding="utf-8")
                console.print(f"[bold green]Saved draft to {draft_path.resolve()}[/bold green]")
            except Exception as e:
                console.print(f"[red]Error saving draft: {e}[/red]")
            Prompt.ask("\nPress [ENTER] to return")
            
        elif choice == "5":
            if Confirm.ask("[bold red]Are you sure you want to discard this draft?[/bold red]"):
                return ""

def run_post_generation(ai_gen: AIGenerator):
    """Workflow to generate a post via Gemini."""
    if not check_setup():
        Prompt.ask("Press [ENTER] to return to the main menu")
        return
        
    console.print("\n[bold cyan]New Post Details[/bold cyan]")
    topic = Prompt.ask("Enter the topic or main idea of the post")
    if not topic.strip():
        console.print("[red]Topic cannot be empty.[/red]")
        Prompt.ask("Press [ENTER] to return")
        return

    # Select Tone
    tones = ["Professional", "Technical", "Thought Leadership", "Casual/Conversational", "Storytelling"]
    console.print("\n[bold]Select a Tone style:[/bold]")
    for idx, tone in enumerate(tones, 1):
        console.print(f"{idx}. {tone}")
    
    tone_idx = Prompt.ask("Choose tone (number)", choices=[str(i) for i in range(1, len(tones)+1)], default="1")
    selected_tone = tones[int(tone_idx) - 1]
    
    extra_instructions = Prompt.ask("Any extra constraints or details? (Optional, press Enter to skip)")

    with console.status("[bold green]Generating post with Gemini...[/bold green]"):
        try:
            post_text = ai_gen.generate_post(topic, selected_tone, extra_instructions)
        except Exception as e:
            console.print(f"\n[red]Error generating post: {e}[/red]")
            Prompt.ask("\nPress [ENTER] to return to the main menu")
            return
            
    # Go to review options
    handle_post_options(post_text, ai_gen)

def post_custom_text():
    """Post text pasted or entered manually."""
    console.print("\n[bold cyan]Paste / Enter your post text below. (Ctrl+Z or Ctrl+D on a empty line to submit, or use Notepad via options):[/bold cyan]")
    
    # Let the user choose to write in editor or paste raw
    use_editor = Confirm.ask("Would you like to draft/paste it in Notepad instead of console terminal input?", default=True)
    if use_editor:
        post_text = edit_manually("")
        if not post_text.strip():
            console.print("[yellow]Empty post. Cancelled.[/yellow]")
            Prompt.ask("\nPress [ENTER] to return")
            return
    else:
        console.print("[dim]Enter/paste text (Press Enter, then Ctrl+Z on Windows to save):[/dim]")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        post_text = "\n".join(lines).strip()
        if not post_text:
            console.print("[yellow]Empty post. Cancelled.[/yellow]")
            Prompt.ask("\nPress [ENTER] to return")
            return

    # Reuse the post menu for custom text
    ai_gen = AIGenerator()
    handle_post_options(post_text, ai_gen)

def main():
    ai_gen = AIGenerator()
    
    while True:
        display_header()
        check_setup()
        
        # Display main options table
        table = Table(show_header=False, box=None)
        table.add_row("[bold cyan]1.[/bold cyan] Authenticate & Setup Session (Run this first)")
        table.add_row("[bold cyan]2.[/bold cyan] Generate Post with AI (Gemini)")
        table.add_row("[bold cyan]3.[/bold cyan] Post Custom Text (Paste & Post)")
        table.add_row("[bold cyan]4.[/bold cyan] Exit")
        
        console.print(Panel(table, title="[bold]Main Menu[/bold]", border_style="cyan", expand=False))
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4"], default="2")
        
        if choice == "1":
            run_login_setup()
        elif choice == "2":
            run_post_generation(ai_gen)
        elif choice == "3":
            post_custom_text()
        elif choice == "4":
            console.print("\n[bold cyan]Goodbye! Keep posting and sharing knowledge. 👋[/bold cyan]")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Program interrupted. Exiting...[/yellow]")
        sys.exit(0)
