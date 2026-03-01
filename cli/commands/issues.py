"""Jira issue management commands."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from cli.config_manager import ConfigManager
from cli.output_formatter import (
    print_error,
    print_info,
    print_success,
    print_warning,
)

console = Console()
app = typer.Typer(help="Jira issue management commands")


def _require_auth() -> None:
    """Require authentication before proceeding."""
    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        if not auth_client.is_authenticated():
            print_error("Authentication required")
            print_info("Run 'geni login' to authenticate first")
            raise typer.Exit(1)
    except (ImportError, ValueError) as e:
        print_error(f"Authentication module not configured: {e}")
        raise typer.Exit(1) from e
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Authentication check failed: {e}")
        raise typer.Exit(1) from e


def _ensure_agent_installed() -> None:
    """Ensure the Issue Resolver agent is installed in the project."""
    from cli.agents import install_agents

    project_root = Path.cwd()
    target_dir = project_root / ".claude" / "agents"
    target_file = target_dir / "Issue Resolver.md"

    if not target_file.exists():
        print_info("Installing Issue Resolver agent...")
        results = install_agents(target_dir=target_dir, force=False, project_root=project_root)
        if results.get("Issue Resolver.md"):
            print_success("Issue Resolver agent installed")
        else:
            print_warning("Could not install Issue Resolver agent (will continue anyway)")


def _build_resolve_prompt(issue: object) -> str:
    """Build the Claude Code prompt for resolving an issue.

    Args:
        issue: JiraIssue object with issue details

    Returns:
        Formatted prompt string
    """
    from cli.jira_client import JiraIssue

    assert isinstance(issue, JiraIssue)

    description_section = ""
    if issue.description:
        description_section = f"""
## Issue Description

{issue.description}
"""

    labels_section = ""
    if issue.labels:
        labels_section = f"\n**Labels**: {', '.join(issue.labels)}"

    return f"""You are helping resolve a Jira issue. Work with the user to understand, plan, and implement a fix.

## Issue Details

- **Key**: [{issue.key}]({issue.url})
- **Summary**: {issue.summary}
- **Priority**: {issue.priority}
- **Status**: {issue.status}
- **Type**: {issue.issue_type}
- **Assignee**: {issue.assignee or 'Unassigned'}{labels_section}
{description_section}
## Resolution Workflow

Follow these steps:

### 1. Understand
Present the issue details above and ask the user how they'd like to approach the resolution. Clarify any ambiguities in the issue description.

### 2. Research (Optional)
If the user wants, search the web for best practices, patterns, or solutions relevant to this issue. Use WebSearch and WebFetch tools.

### 3. Explore
Search the codebase for files relevant to this issue. Use Grep, Glob, and Read tools to understand the current implementation and identify what needs to change.

### 4. Plan
Create a numbered implementation plan with specific file changes. Be concrete about:
- Which files to modify/create
- What changes to make in each file
- Any tests to add or update

### 5. Confirm
Present the plan to the user and **wait for explicit approval** before making any changes. Do not proceed until the user confirms.

### 6. Execute
Implement the approved changes. Make clean, focused changes that address the issue.

### 7. Verify
After implementation:
- Run relevant tests if they exist
- Run linters/type checkers if configured
- Summarize all changes made
- Ask the user if they'd like any adjustments

Begin by presenting the issue details and asking the user how they'd like to approach it."""


def _spawn_claude_code_for_issue(issue: object, verbose: bool = False) -> int:
    """Spawn Claude Code to resolve a Jira issue.

    Args:
        issue: JiraIssue object
        verbose: Whether to show verbose output

    Returns:
        Exit code (0 for success)
    """
    from cli.jira_client import JiraIssue

    assert isinstance(issue, JiraIssue)

    # If already inside Claude Code, just output the prompt
    if os.environ.get("CLAUDECODE") == "1":
        prompt = _build_resolve_prompt(issue)
        console.print()
        console.print("[bold cyan]--- Issue Resolution Request ---[/bold cyan]")
        console.print()
        console.print(prompt)
        console.print()
        console.print("[bold cyan]-------------------------------[/bold cyan]")
        console.print()
        return 0

    # Check if Claude Code CLI is available
    claude_path = shutil.which("claude")
    if not claude_path:
        print_error("Claude Code CLI not found")
        print_info("Install Claude Code: npm install -g @anthropic-ai/claude-code")
        raise typer.Exit(1)

    prompt = _build_resolve_prompt(issue)

    print_info(f"Launching Claude Code to resolve {issue.key}...")
    console.print("[dim]You can interact with Claude Code directly.[/dim]")
    console.print()

    try:
        cmd = [
            claude_path,
            "--permission-mode",
            "default",
            "-p",
            prompt,
        ]

        if verbose:
            console.print(f"[dim]Running: {' '.join(cmd[:3])}...[/dim]")

        result = subprocess.run(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        return result.returncode

    except KeyboardInterrupt:
        print_warning("\nResolution interrupted")
        return 130
    except Exception as e:
        print_error(f"Failed to run Claude Code: {e}")
        return 1


def _format_priority_style(priority: str) -> str:
    """Return Rich markup for priority styling."""
    p = priority.lower()
    if p in ("highest", "critical"):
        return f"[bold red]{priority}[/bold red]"
    if p == "high":
        return f"[red]{priority}[/red]"
    if p == "medium":
        return f"[yellow]{priority}[/yellow]"
    if p in ("low", "lowest"):
        return f"[green]{priority}[/green]"
    return priority


@app.command("list")
def issues_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum issues to fetch"),
) -> None:
    """List open Jira issues and select one to resolve with Claude Code.

    Displays incomplete issues from your configured Jira project,
    lets you pick one interactively, and launches Claude Code to
    collaboratively work on the resolution.
    """
    import questionary

    _require_auth()

    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load()

        # Validate provider is Jira
        if config.provider != "jira":
            print_error(f"Issues command requires Jira provider (current: {config.provider})")
            print_info("Configure Jira with 'geni init' or update ~/.geniable.yaml")
            raise typer.Exit(1)

        if not config.jira:
            print_error("Jira configuration not found")
            print_info("Run 'geni init' to configure Jira credentials")
            raise typer.Exit(1)

        # Create Jira client
        from cli.jira_client import JiraClient

        client = JiraClient(
            base_url=config.jira.base_url,
            email=config.jira.email,
            api_token=config.jira.api_token,
        )

        # Fetch issues
        print_info(f"Fetching open issues from {config.jira.project_key}...")

        issues = client.search_issues(
            project_key=config.jira.project_key,
            max_results=limit,
        )

        if not issues:
            print_warning(f"No open issues found in {config.jira.project_key}")
            raise typer.Exit(0)

        # Count by priority
        priority_counts: dict[str, int] = {}
        for issue in issues:
            p = issue.priority
            priority_counts[p] = priority_counts.get(p, 0) + 1

        priority_summary = ", ".join(f"{count} {name}" for name, count in priority_counts.items())
        print_success(
            f"Found {len(issues)} open issues in {config.jira.project_key} " f"({priority_summary})"
        )

        # Build choices for questionary
        # Determine column widths for alignment
        max_key_len = max(len(issue.key) for issue in issues)
        max_status_len = max(len(issue.status) for issue in issues)
        max_priority_len = max(len(issue.priority) for issue in issues)

        choices = []
        for issue in issues:
            # Truncate summary if too long
            summary = issue.summary
            if len(summary) > 60:
                summary = summary[:57] + "..."

            label = (
                f"{issue.key:<{max_key_len}}  |  "
                f"{issue.status:<{max_status_len}}  |  "
                f"{issue.priority:<{max_priority_len}}  |  "
                f"{summary}"
            )
            choices.append(questionary.Choice(title=label, value=issue.key))

        # Add cancel option
        choices.append(questionary.Choice(title="[Cancel]", value=None))

        # Present selection
        console.print()
        selected_key = questionary.select(
            "Select an issue to resolve:",
            choices=choices,
        ).ask()

        if selected_key is None:
            print_info("Cancelled")
            raise typer.Exit(0)

        # Find the selected issue
        selected_issue = next(i for i in issues if i.key == selected_key)

        # Ensure agent is installed
        _ensure_agent_installed()

        # Launch Claude Code
        exit_code = _spawn_claude_code_for_issue(selected_issue, verbose)
        if exit_code != 0:
            raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        print_warning("\nCancelled")
        raise typer.Exit(0) from None
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list issues: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from e


@app.command("resolve")
def issues_resolve(
    key: str = typer.Argument(..., help="Jira issue key (e.g., AIEV-37)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Resolve a specific Jira issue with Claude Code.

    Fetches the issue details and launches Claude Code for interactive resolution.

    Example:
        geni issues resolve AIEV-37
    """
    _require_auth()

    try:
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load()

        # Validate provider is Jira
        if config.provider != "jira":
            print_error(f"Issues command requires Jira provider (current: {config.provider})")
            raise typer.Exit(1)

        if not config.jira:
            print_error("Jira configuration not found")
            raise typer.Exit(1)

        # Create Jira client
        from cli.jira_client import JiraClient

        client = JiraClient(
            base_url=config.jira.base_url,
            email=config.jira.email,
            api_token=config.jira.api_token,
        )

        # Fetch the issue
        print_info(f"Fetching issue {key}...")

        try:
            issue = client.get_issue(key)
        except Exception as e:
            print_error(f"Could not find issue {key}: {e}")
            raise typer.Exit(1) from e

        print_success(f"Found: {issue.summary}")
        console.print(f"  [dim]Status:[/dim] {issue.status}")
        console.print(f"  [dim]Priority:[/dim] {issue.priority}")
        if issue.assignee:
            console.print(f"  [dim]Assignee:[/dim] {issue.assignee}")

        # Ensure agent is installed
        _ensure_agent_installed()

        # Launch Claude Code
        exit_code = _spawn_claude_code_for_issue(issue, verbose)
        if exit_code != 0:
            raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        print_warning("\nCancelled")
        raise typer.Exit(0) from None
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to resolve issue: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from e
