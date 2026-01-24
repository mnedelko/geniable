"""Analysis commands for thread processing."""

import logging
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import IntPrompt, Confirm
from rich.table import Table

from cli.config_manager import ConfigManager
from cli.output_formatter import (
    print_success,
    print_error,
    print_warning,
    print_info,
    print_header,
    create_progress,
    ThreadLoadingProgress,
)

console = Console()
app = typer.Typer(help="Thread analysis commands")


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
):
    """Analyze latest annotated threads from LangSmith queue.

    Fetches new threads since the last poll and runs evaluation pipeline.
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

        # Import agent
        from agent.agent import Agent, AgentConfig
        from agent.state_manager import StateManager

        # Show last poll timestamp
        state_manager = StateManager(
            project=config.langsmith.project,
            state_dir=str(config.defaults.report_dir),
        )
        stats = state_manager.get_stats()
        print_info(f"Last poll: {stats['last_poll']}")
        print_info(f"Previously processed: {stats['total_processed']} threads")

        # Get provider-specific config
        jira_project_key = None
        notion_database_id = None
        if config.jira:
            jira_project_key = config.jira.project_key
        if config.notion:
            notion_database_id = config.notion.database_id

        # Get auth token for API calls
        auth_token = _get_auth_token()

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
        )

        # Create agent and run with progress display
        agent = Agent(agent_config)

        # Create progress callback for thread loading
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
            summary = agent.run(
                limit=limit,
                create_tickets=not dry_run,
                dry_run=dry_run,
                skip_processed=True,
                force_reprocess=False,
                progress_callback=progress_handler,
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

    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("specific")
def analyze_specific(
    count: int = typer.Option(10, "--count", "-c", help="Number of recent threads to show"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Select and analyze a specific thread interactively.

    Displays a table of recent threads and prompts for selection.
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

        reporter = ReportGenerator(config.defaults.report_dir)
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
