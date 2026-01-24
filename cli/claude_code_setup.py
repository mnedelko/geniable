"""Claude Code agent setup for Geniable.

This module handles checking and guiding users through Claude Code
agent configuration, enabling the /agent workflow in Claude Code.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
logger = logging.getLogger(__name__)


class ClaudeCodeSetup:
    """Handles Claude Code agent setup verification and guidance."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the setup handler.

        Args:
            project_root: Root directory of the project. Defaults to cwd.
        """
        self.project_root = project_root or Path.cwd()

    def check_claude_md_exists(self) -> Tuple[bool, Optional[Path]]:
        """Check if CLAUDE.md exists in the project.

        Checks both root and .claude/ directory.

        Returns:
            Tuple of (exists, path) where path is the location if found.
        """
        # Check root first
        root_path = self.project_root / "CLAUDE.md"
        if root_path.exists():
            return True, root_path

        # Check .claude directory
        claude_dir_path = self.project_root / ".claude" / "CLAUDE.md"
        if claude_dir_path.exists():
            return True, claude_dir_path

        return False, None

    def check_claude_directory_exists(self) -> bool:
        """Check if .claude/ directory exists.

        Returns:
            True if .claude/ directory exists.
        """
        return (self.project_root / ".claude").is_dir()

    def run_setup_check(self) -> bool:
        """Run the Claude Code setup check and guide user through setup.

        This is designed to be run as Step 1 of geni init, allowing users
        to set up Claude Code integration before proceeding.

        Returns:
            True if setup is complete (or skipped), False if user cancels.
        """
        console.print("\n[bold cyan]Claude Code Agent Setup[/bold cyan]")
        console.print("[dim]Checking Claude Code integration requirements...[/dim]\n")

        # Check current state
        claude_md_exists, claude_md_path = self.check_claude_md_exists()
        claude_dir_exists = self.check_claude_directory_exists()

        if claude_md_exists:
            console.print(f"[green]✓[/green] CLAUDE.md found: {claude_md_path}")
            console.print("[green]✓[/green] Claude Code agent integration is configured\n")
            return True

        # CLAUDE.md not found - guide user through setup
        console.print("[yellow]![/yellow] CLAUDE.md not found\n")

        # Explain why this matters
        explanation = Text()
        explanation.append("Claude Code uses ", style="dim")
        explanation.append("CLAUDE.md", style="cyan bold")
        explanation.append(" to understand your project.\n", style="dim")
        explanation.append("This enables the ", style="dim")
        explanation.append("/agent", style="cyan bold")
        explanation.append(" workflow to work effectively with Geniable.", style="dim")

        console.print(
            Panel(
                explanation,
                title="Why is this needed?",
                border_style="blue",
                padding=(1, 2),
            )
        )

        # Ask if user wants to set up now
        setup_now = questionary.confirm(
            "Would you like to set up Claude Code integration now?",
            default=True,
        ).ask()

        if setup_now is None:
            raise KeyboardInterrupt("Setup cancelled")

        if not setup_now:
            console.print("\n[dim]Skipping Claude Code setup.[/dim]")
            console.print(
                "[dim]You can set this up later by running '/init' in Claude Code.[/dim]\n"
            )
            return True

        # Guide user through the /init process
        return self._guide_init_process()

    def _guide_init_process(self) -> bool:
        """Guide user through running /init in Claude Code.

        Returns:
            True if setup completed successfully, False otherwise.
        """
        console.print("\n[bold]To set up Claude Code integration:[/bold]\n")

        # Create step-by-step instructions
        steps = [
            ("1", "Open a new terminal window or tab"),
            ("2", "Navigate to this project directory"),
            ("3", "Start Claude Code by running: [cyan]claude[/cyan]"),
            ("4", "In Claude Code, run: [cyan]/init[/cyan]"),
            ("5", "Claude will analyze your codebase and create CLAUDE.md"),
            ("6", "Once complete, return here and press Enter"),
        ]

        for num, instruction in steps:
            console.print(f"  [cyan]{num}.[/cyan] {instruction}")

        console.print()

        # Show the commands they need
        console.print(
            Panel(
                "[bold]Commands to run:[/bold]\n\n"
                f"  cd {self.project_root}\n"
                "  claude\n"
                "  /init",
                title="Quick Reference",
                border_style="green",
                padding=(1, 2),
            )
        )

        # Wait for user to complete
        console.print()
        try:
            questionary.press_any_key_to_continue(
                message="Press Enter when you've completed the /init setup..."
            ).ask()
        except AttributeError:
            # Fallback if press_any_key_to_continue not available
            input("Press Enter when you've completed the /init setup...")

        # Verify setup
        return self._verify_setup()

    def _verify_setup(self) -> bool:
        """Verify that CLAUDE.md was created.

        Returns:
            True if verification passed or user chooses to continue anyway.
        """
        claude_md_exists, claude_md_path = self.check_claude_md_exists()

        if claude_md_exists:
            console.print(f"\n[green]✓[/green] CLAUDE.md created successfully: {claude_md_path}")
            console.print("[green]✓[/green] Claude Code agent integration is now configured!\n")
            return True

        # Not found - ask if they want to retry or continue
        console.print("\n[yellow]![/yellow] CLAUDE.md still not found")

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Try again - I'll run /init now",
                "Skip for now - I'll set it up later",
                "Cancel setup",
            ],
        ).ask()

        if choice is None or choice == "Cancel setup":
            raise KeyboardInterrupt("Setup cancelled")

        if choice == "Try again - I'll run /init now":
            return self._guide_init_process()

        # Skip for now
        console.print("\n[dim]Continuing without Claude Code setup.[/dim]")
        console.print("[dim]Remember to run '/init' in Claude Code later.[/dim]\n")
        return True


def run_claude_code_setup(project_root: Optional[Path] = None) -> bool:
    """Convenience function to run Claude Code setup check.

    Args:
        project_root: Root directory of the project.

    Returns:
        True if setup complete or skipped, False if cancelled.
    """
    setup = ClaudeCodeSetup(project_root)
    return setup.run_setup_check()
