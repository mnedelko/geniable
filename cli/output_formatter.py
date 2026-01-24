"""Output formatting for CLI commands."""

from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text


console = Console()


class ThreadLoadingProgress:
    """Progress display for thread loading with two phases."""

    def __init__(self):
        self._live: Optional[Live] = None
        self._phase = "summaries"
        self._total_threads = 0
        self._current_thread = 0
        self._current_thread_id = ""

    def __enter__(self):
        self._live = Live(console=console, refresh_per_second=10)
        self._live.__enter__()
        self._update_display()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def _update_display(self):
        """Update the live display based on current phase."""
        if self._phase == "summaries":
            spinner = Spinner("dots", text=" Fetching thread summaries...")
            self._live.update(spinner)
        elif self._phase == "details":
            # Create a progress display with bar
            progress_text = Text()
            progress_text.append("📥 ", style="blue")
            progress_text.append(f"Loading thread details: ", style="white")
            progress_text.append(f"{self._current_thread}/{self._total_threads}", style="cyan bold")

            # Add progress bar
            bar_width = 30
            filled = int((self._current_thread / self._total_threads) * bar_width) if self._total_threads > 0 else 0
            empty = bar_width - filled
            bar = "━" * filled + "╺" + "─" * max(0, empty - 1)

            progress_text.append("\n")
            progress_text.append("    [", style="dim")
            progress_text.append(bar[:filled], style="cyan")
            progress_text.append(bar[filled:], style="dim")
            progress_text.append("]", style="dim")

            # Add current thread ID if available
            if self._current_thread_id:
                progress_text.append(f"\n    Thread: ", style="dim")
                progress_text.append(self._current_thread_id[:20] + "...", style="dim italic")

            self._live.update(progress_text)
        elif self._phase == "complete":
            complete_text = Text()
            complete_text.append("✓ ", style="green")
            complete_text.append(f"Loaded {self._total_threads} threads", style="green")
            self._live.update(complete_text)

    def start_summaries(self):
        """Start the summaries loading phase."""
        self._phase = "summaries"
        self._update_display()

    def start_details(self, total: int):
        """Start the details loading phase."""
        self._phase = "details"
        self._total_threads = total
        self._current_thread = 0
        self._update_display()

    def update_details(self, current: int, thread_id: str = ""):
        """Update the details loading progress."""
        self._current_thread = current
        self._current_thread_id = thread_id
        self._update_display()

    def complete(self):
        """Mark loading as complete."""
        self._phase = "complete"
        self._update_display()


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_header(title: str) -> None:
    """Print a section header."""
    console.print(Panel(title, style="bold blue"))


def print_config(config: Dict[str, Any]) -> None:
    """Print configuration summary."""
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    def add_dict(d: Dict[str, Any], prefix: str = "") -> None:
        for key, value in d.items():
            if isinstance(value, dict):
                add_dict(value, f"{prefix}{key}.")
            else:
                # Mask sensitive values
                display_value = str(value)
                if any(s in key.lower() for s in ["key", "token", "secret", "password"]):
                    if display_value and len(display_value) > 4:
                        display_value = display_value[:4] + "..." + "*" * 4
                table.add_row(f"{prefix}{key}", display_value)

    add_dict(config)
    console.print(table)


def print_tools(tools: List[str]) -> None:
    """Print discovered evaluation tools."""
    table = Table(title="Available Evaluation Tools")
    table.add_column("#", style="dim")
    table.add_column("Tool Name", style="cyan")

    for i, tool in enumerate(tools, 1):
        table.add_row(str(i), tool)

    console.print(table)


def print_threads(threads: List[Dict[str, Any]]) -> None:
    """Print thread summary."""
    table = Table(title="Annotated Threads")
    table.add_column("Thread ID", style="dim", max_width=12)
    table.add_column("Name", max_width=40)
    table.add_column("Status", style="cyan")
    table.add_column("Duration", justify="right")
    table.add_column("Tokens", justify="right")

    for thread in threads[:20]:  # Limit display
        table.add_row(
            thread.get("thread_id", "")[:12],
            thread.get("name", "")[:40],
            thread.get("status", "unknown"),
            f"{thread.get('duration_seconds', 0):.1f}s",
            f"{thread.get('total_tokens', 0):,}",
        )

    if len(threads) > 20:
        table.add_row("...", f"({len(threads) - 20} more)", "", "", "")

    console.print(table)


def print_run_summary(summary: Dict[str, Any]) -> None:
    """Print analysis run summary."""
    console.print()
    print_header("Analysis Complete")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Run ID", summary.get("run_id", "N/A"))
    table.add_row("Threads Analyzed", str(summary.get("threads_analyzed", 0)))
    table.add_row("Issues Found", str(summary.get("issues_found", 0)))
    table.add_row("Tickets Created", str(summary.get("tickets_created", 0)))
    table.add_row("Report", summary.get("report_path", "N/A"))

    if summary.get("dry_run"):
        table.add_row("Mode", "[yellow]DRY RUN[/yellow]")

    console.print(table)
    console.print()


def create_progress() -> Progress:
    """Create a progress indicator."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )
