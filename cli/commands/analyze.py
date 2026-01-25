"""Analysis commands for thread processing."""

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from cli.config_manager import ConfigManager
from cli.output_formatter import (
    ThreadLoadingProgress,
    create_progress,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)

console = Console()
app = typer.Typer(help="Thread analysis commands")


def _is_inside_claude_code() -> bool:
    """Check if we're running inside an active Claude Code session."""
    return os.environ.get("CLAUDECODE") == "1"


def _output_for_claude_code(threads_json: str, config_dict: dict) -> None:
    """Output thread data for the current Claude Code session to analyze.

    When running inside Claude Code, we simply print the data and instructions.
    Claude (the AI) will see this output and can analyze it directly.
    """
    console.print()
    console.print("[bold cyan]═══ Thread Analysis Request ═══[/bold cyan]")
    console.print()
    console.print("I've fetched the following threads from LangSmith for analysis:")
    console.print()
    console.print("[dim]```json[/dim]")
    print(threads_json)
    console.print("[dim]```[/dim]")
    console.print()
    console.print("[bold]Please analyze these threads for:[/bold]")
    console.print("  1. Performance issues (slow execution, high latency)")
    console.print("  2. Errors and failures")
    console.print("  3. Quality issues (poor responses, hallucinations)")
    console.print("  4. Token efficiency problems")
    console.print()
    console.print(f"[dim]Provider: {config_dict.get('provider', 'jira')}[/dim]")
    console.print(f"[dim]Project: {config_dict.get('project', 'default')}[/dim]")
    console.print()
    console.print("After analysis, I can help create tickets for any issues found.")
    console.print()
    console.print("[bold cyan]═══════════════════════════════[/bold cyan]")
    console.print()


def _spawn_claude_code(threads_json: str, config_dict: dict, verbose: bool = False) -> int:
    """Spawn Claude Code CLI to analyze threads.

    If already inside Claude Code, just output the data.
    Otherwise, spawn a new claude process.

    Args:
        threads_json: JSON string of thread data
        config_dict: Configuration for ticket creation
        verbose: Whether to show verbose output

    Returns:
        Exit code (0 for success)
    """
    # If we're already inside Claude Code, just output the data
    if _is_inside_claude_code():
        _output_for_claude_code(threads_json, config_dict)
        return 0

    # Not inside Claude Code - check if CLI is available
    claude_path = shutil.which("claude")
    if not claude_path:
        print_error("Claude Code CLI not found")
        print_info("Option 1: Run 'geni analyze-latest' from within Claude Code")
        print_info("Option 2: Install Claude Code: npm install -g @anthropic-ai/claude-code")
        print_info("Option 3: Use --ci flag for automated analysis with Anthropic API")
        raise typer.Exit(1)

    # Build the analysis prompt
    prompt = f"""You are analyzing LangSmith conversation threads for quality issues.

## Thread Data

```json
{threads_json}
```

## Your Task

Analyze each thread and identify:
1. **Performance Issues**: Slow execution, high latency, inefficient token usage
2. **Errors**: Failures, exceptions, timeouts
3. **Quality Issues**: Poor responses, incomplete answers, hallucinations
4. **Token Efficiency**: Excessive token usage, poor prompt/completion ratios

## Configuration

- Provider: {config_dict.get('provider', 'jira')}
- Project: {config_dict.get('project', 'default')}
- Report Directory: {config_dict.get('report_dir', './reports')}

## Output Format

For each thread with issues, provide:
1. A summary of the issue
2. Severity (critical/high/medium/low)
3. Specific recommendations for improvement
4. Evidence from the thread data

After analysis, ask if I want to create tickets for any identified issues.

Begin your analysis now."""

    # Run claude with the prompt
    print_info("Launching Claude Code for analysis...")
    console.print("[dim]You can interact with Claude Code directly.[/dim]")
    console.print()

    try:
        # Use --permission-mode to allow file writes for reports
        cmd = [
            claude_path,
            "--permission-mode", "default",
            "-p", prompt,
        ]

        if verbose:
            console.print(f"[dim]Running: {' '.join(cmd[:3])}...[/dim]")

        # Run interactively - inherit stdio so user can interact
        result = subprocess.run(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        return result.returncode

    except KeyboardInterrupt:
        print_warning("\nAnalysis interrupted")
        return 130
    except Exception as e:
        print_error(f"Failed to run Claude Code: {e}")
        return 1


def _get_anthropic_api_key(config_manager: ConfigManager) -> Optional[str]:
    """Get Anthropic API key from environment, config, or secrets.

    Priority order:
    1. ANTHROPIC_API_KEY environment variable
    2. Config file (anthropic.api_key)
    3. AWS Secrets Manager (if authenticated)

    Returns:
        API key if found, None otherwise
    """
    # 1. Check environment variable
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        return key

    # 2. Check local config
    try:
        config = config_manager.load()
        if config.anthropic and config.anthropic.api_key:
            return config.anthropic.api_key
    except Exception:
        pass

    # 3. Check AWS Secrets Manager (if we have auth token)
    try:
        from cli.secrets_manager import SecretsManagerClient

        auth_token = _get_auth_token()
        if auth_token:
            secrets_client = SecretsManagerClient()
            secret = secrets_client.get_secret("anthropic")
            if secret and secret.get("api_key"):
                return secret["api_key"]
    except Exception:
        pass

    return None


def _prompt_for_anthropic_key(config_manager: ConfigManager) -> str:
    """Prompt user for Anthropic API key and optionally store it.

    Returns:
        The API key entered by the user

    Raises:
        typer.Exit: If user cancels or provides invalid key
    """
    console.print()
    console.print("[yellow]Anthropic API key required for LLM-powered reports.[/yellow]")
    console.print("Get your API key from: [link]https://console.anthropic.com/settings/keys[/link]")
    console.print()

    api_key = Prompt.ask("Enter your Anthropic API key", password=True)

    if not api_key:
        print_error("API key is required for --ci mode")
        raise typer.Exit(1)

    if not api_key.startswith("sk-ant-"):
        print_warning("API key should typically start with 'sk-ant-'")
        if not Confirm.ask("Continue anyway?", default=False):
            raise typer.Exit(1)

    # Ask if user wants to save the key
    if Confirm.ask("Save API key to config for future use?", default=True):
        try:
            config = config_manager.load()
            from shared.models.config import AnthropicConfig

            config.anthropic = AnthropicConfig(api_key=api_key)
            config_manager.save(config)
            print_success("API key saved to config")
        except Exception as e:
            print_warning(f"Could not save to config: {e}")

    return api_key


def _setup_ci_mode(config_manager: ConfigManager) -> str:
    """Set up CI mode with Anthropic API key.

    Returns:
        The API key to use

    Raises:
        typer.Exit: If API key cannot be obtained
    """
    api_key = _get_anthropic_api_key(config_manager)

    if not api_key:
        api_key = _prompt_for_anthropic_key(config_manager)

    # Set environment variable for the session
    os.environ["ANTHROPIC_API_KEY"] = api_key

    return api_key


def _require_auth():
    """Require authentication before proceeding."""
    import typer as t

    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        if not auth_client.is_authenticated():
            print_error("Authentication required")
            print_info("Run 'geni login' to authenticate first")
            raise t.Exit(1)
    except (ImportError, ValueError) as e:
        print_error(f"Authentication module not configured: {e}")
        print_info("Ensure AWS Cognito is configured properly")
        raise t.Exit(1)
    except t.Exit:
        raise
    except Exception as e:
        print_error(f"Authentication check failed: {e}")
        raise t.Exit(1)


def _get_auth_token() -> Optional[str]:
    """Get the current Cognito auth token.

    Returns:
        The ID token if authenticated, None otherwise
    """
    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        tokens = auth_client.get_current_tokens()
        if tokens:
            return tokens.id_token
    except Exception:
        pass
    return None


@app.command("latest")
def analyze_latest(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum threads to analyze"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze without creating tickets"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="CI/CD mode: Use Anthropic API directly (requires API key)",
    ),
):
    """Analyze latest annotated threads from LangSmith queue.

    Default mode: Spawns Claude Code CLI for interactive analysis.
    You'll see Claude working in real-time and can interact with it.

    CI mode (--ci flag): Uses Anthropic API directly for automated pipelines.
    Requires ANTHROPIC_API_KEY environment variable or config.
    """
    # Check auth status
    _require_auth()

    # Only show detailed logs in verbose mode
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger("agent").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    try:
        # Load configuration
        print_info("Loading configuration...")
        config_manager = ConfigManager()
        config = config_manager.load()

        # Get auth token for API calls
        auth_token = _get_auth_token()

        # Import required modules
        from agent.api_clients.integration_client import IntegrationServiceClient
        from agent.state_manager import StateManager

        # Show last poll timestamp
        state_manager = StateManager(
            project=config.langsmith.project,
            state_dir=str(config.defaults.report_dir),
        )
        stats = state_manager.get_stats()
        print_info(f"Last poll: {stats['last_poll']}")
        print_info(f"Previously processed: {stats['total_processed']} threads")

        # Initialize integration client
        integration = IntegrationServiceClient(
            endpoint=config.aws.integration_endpoint,
            api_key=config.aws.api_key,
            auth_token=auth_token,
        )

        # Fetch threads with progress display
        def progress_handler(phase: str, current: int, total: int, thread_id: str):
            if phase == "summaries":
                loading_progress.start_summaries()
            elif phase == "details":
                if current == 0:
                    loading_progress.start_details(total)
                else:
                    loading_progress.update_details(current, thread_id)
            elif phase == "complete":
                loading_progress.complete()

        with ThreadLoadingProgress() as loading_progress:
            threads = integration.get_annotated_threads(
                limit=limit,
                with_details=True,
                progress_callback=progress_handler,
            )

        if not threads:
            print_warning("No annotated threads found in queue")
            raise typer.Exit(0)

        print_success(f"Loaded {len(threads)} threads")

        # =====================================================================
        # Branch: CI mode (Anthropic API) vs Default mode (Claude Code CLI)
        # =====================================================================

        if ci:
            # CI MODE: Use Anthropic API directly
            print_info("Setting up LLM-powered reports (CI mode)...")
            _setup_ci_mode(config_manager)
            print_success("CI mode enabled - using Anthropic API")

            # Import agent for CI mode
            from agent.agent import Agent, AgentConfig

            # Get provider-specific config
            jira_project_key = None
            notion_database_id = None
            if config.jira:
                jira_project_key = config.jira.project_key
            if config.notion:
                notion_database_id = config.notion.database_id

            # Build agent config
            agent_config = AgentConfig(
                integration_endpoint=config.aws.integration_endpoint,
                evaluation_endpoint=config.aws.evaluation_endpoint,
                api_key=config.aws.api_key,
                auth_token=auth_token,
                provider=config.provider,
                report_dir=config.defaults.report_dir,
                project=config.langsmith.project,
                jira_project_key=jira_project_key,
                notion_database_id=notion_database_id,
                ci_mode=True,
            )

            # Create agent and run
            agent = Agent(agent_config)
            summary = agent.run(
                limit=limit,
                create_tickets=not dry_run,
                dry_run=dry_run,
                skip_processed=True,
                force_reprocess=False,
            )

            # Display results
            console.print()
            print_header("Analysis Summary")
            console.print(f"  Threads analyzed: {summary['threads_analyzed']}")
            console.print(f"  Threads skipped:  {summary['threads_skipped']}")
            console.print(f"  Issues found:     {summary['issues_found']}")
            console.print(f"  Tickets created:  {summary['tickets_created']}")

            if summary.get("report_paths"):
                console.print("\n[cyan]Generated Reports:[/cyan]")
                for path in summary["report_paths"]:
                    console.print(f"  - {path}")

            if dry_run:
                print_warning("Dry run mode - no tickets were created")

        else:
            # DEFAULT MODE: Spawn Claude Code CLI for interactive analysis
            # Convert threads to JSON for Claude Code
            thread_data = [t.to_dict() for t in threads]
            threads_json = json.dumps(thread_data, indent=2, default=str)

            # Build config dict for the prompt
            config_dict = {
                "provider": config.provider,
                "project": config.langsmith.project,
                "report_dir": str(config.defaults.report_dir),
            }

            # Spawn Claude Code CLI
            exit_code = _spawn_claude_code(threads_json, config_dict, verbose)

            if exit_code != 0:
                raise typer.Exit(exit_code)

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("specific")
def analyze_specific(
    count: int = typer.Option(10, "--count", "-c", help="Number of recent threads to show"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="Enable LLM-powered reports using Anthropic API (requires API key)",
    ),
):
    """Select and analyze a specific thread interactively.

    Displays a table of recent threads and prompts for selection.

    Use --ci flag for AI-powered insights in reports (requires Anthropic API key).
    """
    # Check auth status (optional for now)
    _require_auth()

    # Only show detailed logs in verbose mode
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        # Suppress agent logs in non-verbose mode for cleaner progress display
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger("agent").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    try:
        # Load configuration
        print_info("Loading configuration...")
        config_manager = ConfigManager()
        config = config_manager.load()

        # Handle --ci flag for LLM-powered reports
        ci_mode = False
        if ci:
            print_info("Setting up LLM-powered reports (CI mode)...")
            _setup_ci_mode(config_manager)
            ci_mode = True
            print_success("CI mode enabled - reports will include AI-powered insights")

        # Import required modules
        from agent.agent import Agent, AgentConfig
        from agent.api_clients.integration_client import IntegrationServiceClient
        from agent.state_manager import StateManager

        # Get auth token for API calls
        auth_token = _get_auth_token()

        # Initialize clients
        integration = IntegrationServiceClient(
            endpoint=config.aws.integration_endpoint,
            api_key=config.aws.api_key,
            auth_token=auth_token,
        )

        state_manager = StateManager(
            project=config.langsmith.project,
            state_dir=str(config.defaults.report_dir),
        )

        # Fetch recent threads with loading animation
        def progress_handler(phase: str, current: int, total: int, thread_id: str):
            if phase == "summaries":
                loading_progress.start_summaries()
            elif phase == "details":
                if current == 0:
                    loading_progress.start_details(total)
                else:
                    loading_progress.update_details(current, thread_id)
            elif phase == "complete":
                loading_progress.complete()

        with ThreadLoadingProgress() as loading_progress:
            threads = integration.get_annotated_threads(
                limit=count,
                with_details=True,
                progress_callback=progress_handler,
            )

        if not threads:
            print_warning("No threads found in the annotation queue")
            raise typer.Exit(0)

        # Get processed thread IDs for marking
        processed_ids = set(state_manager.load().processed_thread_ids)

        # Display table
        table = Table(title=f"Recent Threads (showing {len(threads)})")
        table.add_column("#", style="dim", width=4)
        table.add_column("Thread ID", style="cyan", width=12)
        table.add_column("Name", width=40)
        table.add_column("Status", width=10)
        table.add_column("Duration", width=10)
        table.add_column("Processed", width=10)

        for idx, thread in enumerate(threads, 1):
            # Format duration
            duration = thread.duration_seconds
            if duration > 60:
                duration_str = f"{duration / 60:.1f}m"
            else:
                duration_str = f"{duration:.1f}s"

            # Check if processed
            is_processed = thread.thread_id in processed_ids
            processed_mark = "[green]✓[/green]" if is_processed else "[dim]—[/dim]"

            # Status styling
            status = thread.status
            if status == "error":
                status_styled = f"[red]{status}[/red]"
            elif status == "success":
                status_styled = f"[green]{status}[/green]"
            else:
                status_styled = status

            table.add_row(
                str(idx),
                thread.thread_id[:10] + "...",
                thread.name[:38] + "..." if len(thread.name) > 40 else thread.name,
                status_styled,
                duration_str,
                processed_mark,
            )

        console.print()
        console.print(table)
        console.print()

        # Prompt for selection
        selection = IntPrompt.ask(
            "Select thread number to analyze",
            default=1,
        )

        if selection < 1 or selection > len(threads):
            print_error(f"Invalid selection. Please choose 1-{len(threads)}")
            raise typer.Exit(1)

        selected_thread = threads[selection - 1]
        print_info(f"Selected: {selected_thread.name}")

        # Check if already processed
        if selected_thread.thread_id in processed_ids:
            print_warning("This thread has already been processed")
            history = state_manager.get_processing_history(selected_thread.thread_id)
            if history:
                entry = history[0]
                console.print(f"  [dim]Processed at:[/dim] {entry.processed_at}")
                if entry.documentation_path:
                    console.print(f"  [dim]Report:[/dim] {entry.documentation_path}")
                if entry.jira_issue_urls:
                    console.print(f"  [dim]Jira:[/dim] {entry.jira_issue_urls[0]}")
                if entry.notion_issue_urls:
                    console.print(f"  [dim]Notion:[/dim] {entry.notion_issue_urls[0]}")

            if not Confirm.ask("Re-analyze this thread?", default=False):
                raise typer.Exit(0)

        # Get provider-specific config
        jira_project_key = None
        notion_database_id = None
        if config.jira:
            jira_project_key = config.jira.project_key
        if config.notion:
            notion_database_id = config.notion.database_id

        # Build agent config
        agent_config = AgentConfig(
            integration_endpoint=config.aws.integration_endpoint,
            evaluation_endpoint=config.aws.evaluation_endpoint,
            api_key=config.aws.api_key,
            auth_token=auth_token,
            provider=config.provider,
            report_dir=config.defaults.report_dir,
            project=config.langsmith.project,
            jira_project_key=jira_project_key,
            notion_database_id=notion_database_id,
            ci_mode=ci_mode,
        )

        # Create agent and analyze
        agent = Agent(agent_config)

        print_info("Running analysis...")
        with create_progress() as progress:
            task = progress.add_task("Analyzing thread...", total=None)
            result = agent.analyze_thread(selected_thread)
            progress.remove_task(task)

        # Generate report
        from agent.report_generator import ReportGenerator

        reporter = ReportGenerator(output_dir=config.defaults.report_dir, use_llm=ci_mode)
        report_path = reporter.generate_thread_report(
            thread=selected_thread.to_dict(),
            eval_result=result.evaluation,
            run_id=agent.run_id,
        )

        # Create ticket if issues found
        ticket_url = None
        if result.has_issues:
            print_warning(f"Found {result.issues_count} issues")
            if Confirm.ask("Create ticket?", default=True):
                ticket_response = agent.create_ticket(result.issue_card)
                if ticket_response:
                    ticket_url = ticket_response.get("issue_url")
                    ticket_key = ticket_response.get("issue_key") or ticket_response.get("issue_id")
                    print_success(f"Created ticket: {ticket_key}")

                    # Update report with ticket info
                    if ticket_url:
                        provider = ticket_response.get("provider", config.provider)
                        if provider == "jira":
                            reporter.update_report_with_tickets(
                                report_path=report_path,
                                jira_tickets=[{"key": ticket_key, "url": ticket_url}],
                            )
                        else:
                            reporter.update_report_with_tickets(
                                report_path=report_path,
                                notion_tickets=[{"id": ticket_key, "url": ticket_url}],
                            )
        else:
            print_success("No issues found")

        # Record processing
        state_manager.record_processing(
            thread_id=selected_thread.thread_id,
            name=selected_thread.name,
            status="success",
            issues_created=result.issues_count,
            documentation_path=str(report_path),
            jira_issue_urls=[ticket_url] if ticket_url and config.provider == "jira" else None,
            notion_issue_urls=[ticket_url] if ticket_url and config.provider == "notion" else None,
        )

        # Show results
        console.print()
        print_header("Analysis Complete")
        console.print(f"  [cyan]Report:[/cyan] {report_path}")
        if ticket_url:
            console.print(f"  [cyan]Ticket:[/cyan] {ticket_url}")

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_warning("\nCancelled")
        raise typer.Exit(0)
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("fetch")
def fetch(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum threads to fetch from queue"),
    thread_id: Optional[str] = typer.Option(
        None, "--thread-id", "-t", help="Fetch a specific thread by ID"
    ),
    output: str = typer.Option("json", "--output", "-o", help="Output format: json, yaml, or summary"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Fetch unanalyzed threads from LangSmith annotation queue.

    The AWS service automatically filters out previously analyzed threads,
    so you only get new threads that haven't been processed yet.

    Examples:

        geni analyze fetch --output summary
        # Shows: Found 12 threads, 5 skipped (previously analyzed), 7 new

        geni analyze fetch --output json
        # Returns JSON array of unanalyzed threads

        geni analyze fetch --thread-id abc123
        # Fetch a specific thread by ID
    """
    # Check auth status
    _require_auth()

    # Suppress logs for clean JSON/YAML output
    if not verbose:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger("agent").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)

    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load()

        # Import required modules
        from agent.api_clients.integration_client import IntegrationServiceClient

        # Get auth token for API calls
        auth_token = _get_auth_token()

        # Initialize client
        integration = IntegrationServiceClient(
            endpoint=config.aws.integration_endpoint,
            api_key=config.aws.api_key,
            auth_token=auth_token,
        )

        # Fetch threads with metadata
        if thread_id:
            # Fetch specific thread by ID
            result = integration.fetch_threads(limit=1, with_details=True)
            # Filter to the specific thread
            result.threads = [t for t in result.threads if t.thread_id == thread_id]
            if not result.threads:
                print_error(f"Thread not found: {thread_id}")
                raise typer.Exit(1)
        else:
            # Fetch latest unanalyzed threads
            result = integration.fetch_threads(limit=limit, with_details=True)

        # Handle different output formats
        if output == "summary":
            # Human-readable summary for Claude Code agent
            console.print(
                f"Found {result.total_in_queue} threads in queue, "
                f"{result.skipped} skipped (previously analyzed), "
                f"{result.returned} new threads to analyze"
            )
            if result.threads:
                console.print("\nThreads to analyze:")
                for i, t in enumerate(result.threads, 1):
                    console.print(f"  {i}. {t.name} ({t.thread_id[:8]}...)")
            return

        if not result.threads:
            # Output empty result for consistent parsing
            if output == "json":
                output_data = {
                    "threads": [],
                    "total_in_queue": result.total_in_queue,
                    "skipped": result.skipped,
                    "returned": 0,
                }
                print(json.dumps(output_data, indent=2, default=str))
            else:
                print("[]")
            return

        # Convert to serializable format
        thread_data = [t.to_dict() for t in result.threads]

        # Output in requested format
        if output == "json":
            output_data = {
                "threads": thread_data,
                "total_in_queue": result.total_in_queue,
                "skipped": result.skipped,
                "returned": result.returned,
            }
            print(json.dumps(output_data, indent=2, default=str))
        elif output == "yaml":
            try:
                import yaml

                output_data = {
                    "threads": thread_data,
                    "total_in_queue": result.total_in_queue,
                    "skipped": result.skipped,
                    "returned": result.returned,
                }
                print(yaml.dump(output_data, default_flow_style=False, allow_unicode=True))
            except ImportError:
                print_error("PyYAML is required for YAML output. Install with: pip install pyyaml")
                raise typer.Exit(1)
        else:
            print_error(f"Unsupported output format: {output}")
            print_info("Supported formats: json, yaml, summary")
            raise typer.Exit(1)

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Fetch failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("mark-done")
def mark_done(
    thread_ids: str = typer.Option(
        ..., "--thread-ids", "-t", help="Comma-separated list of thread IDs to mark as done"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Mark threads as analyzed/done so they won't appear in future fetches.

    This syncs the processing state to AWS. Once marked, these threads
    will be filtered out by the fetch command.

    Examples:

        geni analyze mark-done --thread-ids "abc123,def456,ghi789"
    """
    # Check auth status
    _require_auth()

    # Suppress logs unless verbose
    if not verbose:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger("agent").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)

    try:
        # Parse thread IDs
        ids = [tid.strip() for tid in thread_ids.split(",") if tid.strip()]
        if not ids:
            print_error("No valid thread IDs provided")
            raise typer.Exit(1)

        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load()

        # Import required modules
        from agent.api_clients.integration_client import IntegrationServiceClient

        # Get auth token for API calls
        auth_token = _get_auth_token()

        # Initialize client
        integration = IntegrationServiceClient(
            endpoint=config.aws.integration_endpoint,
            api_key=config.aws.api_key,
            auth_token=auth_token,
        )

        # Mark threads as done
        result = integration.mark_threads_done(
            thread_ids=ids,
            project=config.langsmith.project,
        )

        if result.get("success"):
            print_success(f"Marked {len(ids)} thread(s) as analyzed")
            console.print(f"[dim]Synced to AWS at: {result.get('synced_at', 'unknown')}[/dim]")
        else:
            print_error(f"Failed to mark threads as done: {result.get('error', 'unknown error')}")
            raise typer.Exit(1)

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Mark-done failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)
