"""Main CLI application using Typer."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from cli.config_manager import DEFAULT_CONFIG_PATH, ConfigManager
from cli.output_formatter import (
    console,
    create_progress,
    print_config,
    print_error,
    print_header,
    print_info,
    print_run_summary,
    print_success,
    print_threads,
    print_tools,
    print_warning,
)


# Auth middleware - authentication is required for all commands
def require_auth():
    """Require authentication before proceeding.

    Checks if user is authenticated and exits with error if not.
    """
    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        if not auth_client.is_authenticated():
            print_error("Authentication required")
            print_info("Run 'geni login' to authenticate first")
            raise typer.Exit(1)
    except (ImportError, ValueError) as e:
        print_error(f"Authentication module not configured: {e}")
        print_info("Ensure AWS Cognito is configured properly")
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Authentication check failed: {e}")
        raise typer.Exit(1)


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


# Create app
app = typer.Typer(
    name="geni",
    help="Geni - QA Pipeline for LLM Applications",
    add_completion=False,
)

# Add analyze subcommands
from cli.commands.analyze import app as analyze_app

app.add_typer(analyze_app, name="analyze", help="Thread analysis commands")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip service validation"
    ),
):
    """Initialize configuration with interactive wizard.

    This command will:
    1. Set up Claude Code agent integration (CLAUDE.md via /init)
    2. Collect LangSmith credentials and project settings
    3. Configure issue tracker integration (Jira/Notion)
    4. Validate service connections (optional)
    5. Sync credentials to AWS Secrets Manager (required)

    Note: Authentication with AWS Cognito is required before running init.
    Run 'geni login' first if not already authenticated.
    """
    # Require authentication first
    require_auth()

    from cli.wizard import ConfigWizard

    # Check for existing config
    if DEFAULT_CONFIG_PATH.exists() and not force:
        print_warning(f"Configuration already exists: {DEFAULT_CONFIG_PATH}")
        if not typer.confirm("Overwrite existing configuration?"):
            print_info("Use 'geni configure --show' to view current config")
            raise typer.Abort()

    try:
        # Run wizard (includes mandatory Secrets Manager sync)
        wizard = ConfigWizard()
        config = wizard.run(skip_validation=skip_validation)

        # Save configuration
        path = ConfigManager.save_config(config)
        print_success(f"\nConfiguration saved to: {path}")

        # Validate saved config by reloading it
        print_info("Verifying saved configuration...")
        try:
            config_manager = ConfigManager()
            loaded_config = config_manager.load()
            print_success("Configuration validated successfully")
        except Exception as e:
            print_error(f"Configuration validation failed: {e}")
            print_warning("The saved config may have issues. Check the file manually.")

        # Create reports directory
        report_dir = Path(config.get("defaults", {}).get("report_dir", "./reports"))
        if not report_dir.is_absolute():
            report_dir = Path.cwd() / report_dir
        report_dir.mkdir(parents=True, exist_ok=True)
        print_info(f"Reports directory created: {report_dir}")

        # Initialize empty processing state
        state_file = report_dir / "processing_state.json"
        if not state_file.exists():
            import json

            initial_state = {
                "project": config.get("langsmith", {}).get("project", "default"),
                "processed_threads": {},
                "last_poll": None,
            }
            state_file.write_text(json.dumps(initial_state, indent=2))
            print_info(f"Processing state initialized: {state_file}")

        # Show next steps
        console.print("\n[bold cyan]Setup Complete![/bold cyan]")
        console.print("\n[bold]Next Steps:[/bold]")
        console.print("  1. [dim]Run analysis:[/dim]  geni analyze-latest")
        console.print("\n[dim]Claude Code agent integration is configured.[/dim]")
        console.print("[dim]Use /agent in Claude Code to leverage the Geniable pipeline.[/dim]")

    except KeyboardInterrupt:
        print_warning("\nWizard cancelled")
        raise typer.Abort()
    except RuntimeError as e:
        # RuntimeError from secrets sync failure
        print_error(f"Setup failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        raise typer.Exit(1)


@app.command()
def inject(
    target: Path = typer.Argument(
        Path("./agent"),
        help="Target directory for agent code",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    no_shared: bool = typer.Option(False, "--no-shared", help="Skip shared module"),
):
    """Inject agent code for Claude Code visibility.

    Copies the agent module to a local directory so Claude Code
    can read and understand the evaluation pipeline.
    """
    # Require authentication
    require_auth()

    from cli.injector import inject_agent_code

    try:
        # Resolve target path
        target_path = target.resolve()

        # Create parent directory if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        print_info(f"Injecting agent code to: {target_path}")

        results = inject_agent_code(
            target_dir=target_path,
            overwrite=force,
            include_shared=not no_shared,
        )

        # Report results
        if results["errors"]:
            for error in results["errors"]:
                print_error(error)
            raise typer.Exit(1)

        print_success(f"Injected {results['files_copied']} Python files")

        if results["agent_dir"]:
            console.print(f"  [dim]Agent:[/dim]  {results['agent_dir']}")
        if results["shared_dir"]:
            console.print(f"  [dim]Shared:[/dim] {results['shared_dir']}")

        # Show next steps
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("  Claude Code can now read the agent code for context.")
        console.print("  Run 'geni analyze-latest' to start analysis.")

    except FileExistsError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except FileNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Injection failed: {e}")
        raise typer.Exit(1)


@app.command()
def configure(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
    reset: bool = typer.Option(False, "--reset", help="Reset to template configuration"),
    sync_secrets: bool = typer.Option(
        False, "--sync-secrets", help="Sync credentials to AWS Secrets Manager"
    ),
    list_secrets: bool = typer.Option(
        False, "--list-secrets", help="List secrets in AWS Secrets Manager"
    ),
):
    """Configure the analyzer with credentials and settings."""
    # Require authentication
    require_auth()

    config_manager = ConfigManager()

    if reset:
        if DEFAULT_CONFIG_PATH.exists():
            if not typer.confirm("This will overwrite existing config. Continue?"):
                raise typer.Abort()

        path = ConfigManager.create_template()
        print_success(f"Configuration template created: {path}")
        print_info("Edit the file to add your credentials.")
        return

    if not DEFAULT_CONFIG_PATH.exists():
        print_warning("No configuration file found.")
        if typer.confirm("Create configuration template?"):
            path = ConfigManager.create_template()
            print_success(f"Configuration template created: {path}")
            print_info("Edit the file to add your credentials, then run 'configure --validate'")
        return

    if show:
        try:
            config = config_manager.load()
            print_config(config.model_dump())
        except Exception as e:
            print_error(f"Failed to load config: {e}")
            raise typer.Exit(1)
        return

    if list_secrets:
        print_info("Listing secrets in AWS Secrets Manager...")
        try:
            from cli.secrets_manager import SecretsManagerClient

            config = config_manager.load()
            client = SecretsManagerClient(region=config.aws.region)

            if not client.validate_connection():
                print_error("Cannot connect to AWS Secrets Manager")
                print_info("Check your AWS credentials (aws configure)")
                raise typer.Exit(1)

            secrets = client.list_secrets()

            if not secrets:
                print_warning("No secrets found with prefix 'geni/'")
            else:
                console.print(f"\n[cyan]Found {len(secrets)} secret(s):[/cyan]")
                for secret in secrets:
                    console.print(f"  - {secret['name']}")
                    if secret.get("last_changed"):
                        console.print(f"    [dim]Last modified: {secret['last_changed']}[/dim]")

        except ImportError:
            print_error("boto3 is required for AWS Secrets Manager")
            print_info("Install with: pip install boto3")
            raise typer.Exit(1)
        except Exception as e:
            print_error(f"Failed to list secrets: {e}")
            raise typer.Exit(1)
        return

    if sync_secrets:
        print_info("Syncing credentials to AWS Secrets Manager...")
        try:
            from cli.secrets_manager import SecretsManagerClient, format_sync_results

            config = config_manager.load()
            client = SecretsManagerClient(region=config.aws.region)

            if not client.validate_connection():
                print_error("Cannot connect to AWS Secrets Manager")
                print_info("Check your AWS credentials (aws configure)")
                raise typer.Exit(1)

            # Convert AppConfig to dict for sync
            config_dict = {
                "langsmith": {"api_key": config.langsmith.api_key},
                "aws": {"api_key": config.aws.api_key},
                "provider": config.provider,
            }

            if config.jira:
                config_dict["jira"] = {
                    "base_url": config.jira.base_url,
                    "email": config.jira.email,
                    "api_token": config.jira.api_token,
                    "project_key": config.jira.project_key,
                }

            if config.notion:
                config_dict["notion"] = {
                    "api_key": config.notion.api_key,
                    "database_id": config.notion.database_id,
                }

            results = client.sync_all(config_dict)
            console.print(format_sync_results(results))

            all_success = all(r.success for r in results)
            if all_success:
                print_success("\nCredentials synced to AWS Secrets Manager!")
            else:
                print_warning("\nSome credentials failed to sync")
                raise typer.Exit(1)

        except ImportError:
            print_error("boto3 is required for AWS Secrets Manager")
            print_info("Install with: pip install boto3")
            raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            print_error(f"Failed to sync secrets: {e}")
            raise typer.Exit(1)
        return

    if validate:
        print_info("Validating configuration...")
        try:
            config = config_manager.load()

            # Validate provider config
            provider_config = config.get_provider_config()
            print_success(f"Configuration valid for provider: {config.provider}")

            # Show summary
            print_config(
                {
                    "provider": config.provider,
                    "langsmith_project": config.langsmith.project,
                    "langsmith_queue": config.langsmith.queue,
                    "aws_region": config.aws.region,
                }
            )

            # Live service validation
            console.print("\n[cyan]Testing service connections...[/cyan]")
            from cli.service_validator import ServiceValidator

            validator = ServiceValidator()

            # Convert AppConfig to dict for validator
            config_dict = {
                "langsmith": {"api_key": config.langsmith.api_key},
                "aws": {
                    "integration_endpoint": config.aws.integration_endpoint,
                    "evaluation_endpoint": config.aws.evaluation_endpoint,
                    "api_key": config.aws.api_key,
                },
                "provider": config.provider,
            }

            if config.jira:
                config_dict["jira"] = {
                    "base_url": config.jira.base_url,
                    "email": config.jira.email,
                    "api_token": config.jira.api_token,
                    "project_key": config.jira.project_key,
                }

            if config.notion:
                config_dict["notion"] = {
                    "api_key": config.notion.api_key,
                    "database_id": config.notion.database_id,
                }

            results = validator.validate_all(config_dict)

            all_passed = True
            for result in results:
                status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
                console.print(f"  {status} {result.service}: {result.message}")
                if not result.success:
                    all_passed = False

            if all_passed:
                print_success("\nAll services validated successfully!")
            else:
                print_warning("\nSome service connections failed")
                raise typer.Exit(1)

        except typer.Exit:
            raise
        except Exception as e:
            print_error(f"Configuration invalid: {e}")
            raise typer.Exit(1)
        return

    # Default: show help
    print_info(f"Configuration file: {DEFAULT_CONFIG_PATH}")
    if DEFAULT_CONFIG_PATH.exists():
        print_success("Configuration file exists")
        print_info("Use --show to display, --validate to check")
    else:
        print_warning("No configuration file found")
        print_info("Use --reset to create template")


@app.command()
def run(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum threads to analyze"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze without creating tickets"),
    report_only: bool = typer.Option(False, "--report-only", help="Generate report only"),
    queue: Optional[str] = typer.Option(None, "--queue", "-q", help="Override annotation queue"),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Override provider (jira/notion)"
    ),
    force_reprocess: bool = typer.Option(
        False, "--force", "-f", help="Reprocess already-processed threads"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run the analysis pipeline on annotated threads."""
    # Check auth status (optional for now)
    require_auth()

    # Set up logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Load configuration
        print_info("Loading configuration...")
        config_manager = ConfigManager()
        config = config_manager.load()

        # Import agent here to avoid import errors if dependencies missing
        from agent.agent import Agent, AgentConfig

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
            provider=provider or config.provider,
            report_dir=config.defaults.report_dir,
            project=config.langsmith.project,
            jira_project_key=jira_project_key,
            notion_database_id=notion_database_id,
        )

        # Create agent
        agent = Agent(agent_config)

        # Discover tools
        with create_progress() as progress:
            task = progress.add_task("Discovering evaluation tools...", total=None)
            tools = agent.discover_tools()
            progress.remove_task(task)

        print_success(f"Discovered {len(tools)} evaluation tools")
        if verbose:
            print_tools(tools)

        # Fetch threads
        with create_progress() as progress:
            task = progress.add_task("Fetching annotated threads...", total=None)
            threads = agent.fetch_threads(limit=limit)
            progress.remove_task(task)

        if not threads:
            print_warning("No annotated threads found in queue")
            raise typer.Exit(0)

        print_success(f"Found {len(threads)} annotated threads")
        if verbose:
            print_threads([t.to_dict() for t in threads])

        # Run analysis
        print_info("Running analysis...")
        summary = agent.run(
            limit=limit,
            create_tickets=not report_only,
            dry_run=dry_run,
            skip_processed=not force_reprocess,
            force_reprocess=force_reprocess,
        )

        # Print summary
        print_run_summary(summary)

        # Show report paths
        if summary.get("report_paths"):
            console.print("\n[cyan]Generated Reports:[/cyan]")
            for path in summary["report_paths"]:
                console.print(f"  - {path}")

        if summary.get("state_file"):
            console.print(f"\n[dim]State file: {summary['state_file']}[/dim]")

    except FileNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)

    except Exception as e:
        print_error(f"Analysis failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed status"),
):
    """Show current processing status and statistics."""
    # Check auth status (optional for now)
    require_auth()

    try:
        config_manager = ConfigManager()
        config = config_manager.load()

        print_header("Geni Status")

        # Configuration status
        print_info(f"Provider: {config.provider}")
        print_info(f"Project: {config.langsmith.project}")
        print_info(f"Queue: {config.langsmith.queue}")

        # Test connections
        from agent.api_clients.evaluation_client import EvaluationServiceClient
        from agent.api_clients.integration_client import IntegrationServiceClient

        # Get auth token for API calls
        auth_token = _get_auth_token()

        with create_progress() as progress:
            task = progress.add_task("Testing connections...", total=None)

            # Test integration service
            integration = IntegrationServiceClient(
                endpoint=config.aws.integration_endpoint,
                api_key=config.aws.api_key,
                auth_token=auth_token,
            )
            if integration.validate_connection():
                print_success("Integration Service: Connected")
            else:
                print_error("Integration Service: Connection failed")

            # Test evaluation service
            evaluation = EvaluationServiceClient(
                endpoint=config.aws.evaluation_endpoint,
                api_key=config.aws.api_key,
                auth_token=auth_token,
            )
            try:
                tools = evaluation.discover_tools()
                print_success(f"Evaluation Service: Connected ({len(tools)} tools)")
            except Exception as e:
                print_error(f"Evaluation Service: {e}")

            progress.remove_task(task)

    except FileNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)

    except Exception as e:
        print_error(f"Status check failed: {e}")
        raise typer.Exit(1)


@app.command()
def discover():
    """Discover available evaluation tools from the Evaluation Service."""
    # Check auth status (optional for now)
    require_auth()

    try:
        config_manager = ConfigManager()
        config = config_manager.load()

        from agent.mcp_client import MCPClient

        print_info("Discovering evaluation tools...")

        mcp = MCPClient(
            evaluation_endpoint=config.aws.evaluation_endpoint,
            api_key=config.aws.api_key,
        )

        tools = mcp.discover()

        print_header("Available Evaluation Tools")

        for tool in tools:
            console.print(f"\n[cyan bold]{tool.name}[/cyan bold] v{tool.version}")
            console.print(f"  {tool.description}")

            required = tool.input_schema.get("required", [])
            if required:
                console.print(f"  [dim]Required: {', '.join(required)}[/dim]")

        print_success(f"\nTotal: {len(tools)} tools available")

    except Exception as e:
        print_error(f"Discovery failed: {e}")
        raise typer.Exit(1)


@app.command()
def stats():
    """Show processing statistics and history."""
    # Check auth status (optional for now)
    require_auth()

    try:
        config_manager = ConfigManager()
        config = config_manager.load()

        from agent.state_manager import StateManager

        state_manager = StateManager(
            project=config.langsmith.project,
            state_dir=str(config.defaults.report_dir),
        )

        stats = state_manager.get_stats()

        print_header("Processing Statistics")

        console.print(f"\n[cyan]Project:[/cyan] {stats['project']}")
        console.print(f"[cyan]Last Poll:[/cyan] {stats['last_poll']}")
        console.print(f"\n[cyan]Total Processed:[/cyan] {stats['total_processed']}")
        console.print(f"[cyan]Successful:[/cyan] {stats['successful']}")
        console.print(f"[cyan]Errors:[/cyan] {stats['errors']}")
        console.print(f"[cyan]Total Issues Created:[/cyan] {stats['total_issues_created']}")

        # Show recent history
        history = state_manager.get_processing_history()
        if history:
            console.print("\n[cyan]Recent Processing History:[/cyan]")
            for entry in history[-10:]:  # Show last 10
                status_icon = "✅" if entry.status == "success" else "❌"
                console.print(f"  {status_icon} {entry.thread_id[:8]}... - {entry.name[:40]}")
                if entry.documentation_path:
                    console.print(f"     [dim]Report: {entry.documentation_path}[/dim]")

        console.print(f"\n[dim]State file: {state_manager.state_file}[/dim]")

    except FileNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to get stats: {e}")
        raise typer.Exit(1)


@app.command()
def clear_state(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clear processing state (allows reprocessing all threads)."""
    # Check auth status (optional for now)
    require_auth()

    try:
        config_manager = ConfigManager()
        config = config_manager.load()

        if not confirm:
            if not typer.confirm("This will reset all processing history. Continue?"):
                raise typer.Abort()

        from agent.state_manager import StateManager

        state_manager = StateManager(
            project=config.langsmith.project,
            state_dir=str(config.defaults.report_dir),
        )

        state_manager.clear_state()
        print_success("Processing state cleared")

    except FileNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to clear state: {e}")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("Geni v2.0.0")
    console.print("QA Pipeline for LLM Applications")


# =====================================================================
# Authentication Commands
# =====================================================================


@app.command()
def login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email address"),
    no_keyring: bool = typer.Option(
        False, "--no-keyring", help="Use file storage instead of system keyring"
    ),
):
    """Login to Geni cloud service.

    Authenticates with AWS Cognito and stores tokens securely in the
    system keyring (macOS Keychain, Windows Credential Store) or
    encrypted file if --no-keyring is specified.
    """
    from getpass import getpass

    try:
        from cli.auth import AuthenticationError, PasswordChangeRequired, get_auth_client
    except ImportError as e:
        print_error(f"Authentication module not available: {e}")
        print_info("Ensure all dependencies are installed: pip install -e '.[dev]'")
        raise typer.Exit(1)

    # Get email if not provided
    if not email:
        email = typer.prompt("Email")

    # Get password securely
    password = getpass("Password: ")

    if not password:
        print_error("Password is required")
        raise typer.Exit(1)

    try:
        # Get auth client
        auth_client = get_auth_client(use_keyring=not no_keyring)

        # Attempt login
        print_info("Authenticating...")
        tokens = auth_client.login(email, password)

        print_success(f"Successfully logged in as {email}")

        # Show token expiry
        if tokens.expires_at:
            expiry_str = tokens.expires_at.strftime("%Y-%m-%d %H:%M:%S %Z")
            print_info(f"Session expires: {expiry_str}")

        # Show next steps
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("  1. Run 'geni init' to configure your settings")
        console.print("  2. Your credentials will be stored securely in AWS")

    except PasswordChangeRequired as e:
        # Handle first-time login with temporary password
        print_warning("Password change required for new account.")
        console.print("\n[cyan]Please set a new permanent password.[/cyan]")
        console.print("[dim]Requirements: min 12 chars, uppercase, lowercase, numbers[/dim]\n")

        # Prompt for new password with confirmation
        while True:
            new_password = getpass("New password: ")
            if not new_password:
                print_error("Password is required")
                continue

            if len(new_password) < 12:
                print_error("Password must be at least 12 characters")
                continue

            confirm_password = getpass("Confirm new password: ")
            if new_password != confirm_password:
                print_error("Passwords do not match")
                continue

            break

        try:
            print_info("Setting new password...")
            tokens = auth_client.complete_password_change(
                session=e.session,
                user_id=e.user_id,
                new_password=new_password,
                email=email,
            )

            print_success(f"Password changed successfully!")
            print_success(f"Logged in as {email}")

            # Show next steps
            console.print("\n[bold cyan]Next Steps:[/bold cyan]")
            console.print("  1. Run 'geni init' to configure your settings")
            console.print("  2. Your credentials will be stored securely in AWS")

        except AuthenticationError as pw_error:
            print_error(f"Password change failed: {pw_error}")
            raise typer.Exit(1)

    except AuthenticationError as e:
        print_error(f"Authentication failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Login failed: {e}")
        raise typer.Exit(1)


@app.command()
def logout():
    """Logout and clear stored authentication tokens.

    Removes tokens from the system keyring or encrypted file storage.
    """
    try:
        from cli.auth import get_auth_client
    except ImportError as e:
        print_error(f"Authentication module not available: {e}")
        raise typer.Exit(1)

    try:
        auth_client = get_auth_client()

        if not auth_client.is_authenticated():
            print_warning("Not currently logged in")
            return

        auth_client.logout()
        print_success("Successfully logged out")

    except Exception as e:
        print_error(f"Logout failed: {e}")
        raise typer.Exit(1)


@app.command()
def whoami():
    """Show current authentication status and user information.

    Displays the currently logged-in user, token expiry, and
    authentication status.
    """
    try:
        from cli.auth import get_auth_client
    except ImportError as e:
        print_error(f"Authentication module not available: {e}")
        raise typer.Exit(1)

    try:
        auth_client = get_auth_client()

        if not auth_client.is_authenticated():
            print_warning("Not logged in")
            print_info("Run 'geni login' to authenticate")
            raise typer.Exit(1)

        tokens = auth_client.get_current_tokens()

        if not tokens:
            print_warning("No valid session found")
            print_info("Run 'geni login' to authenticate")
            raise typer.Exit(1)

        print_header("Authentication Status")

        # Decode JWT to get user info (without verification - just for display)
        import base64
        import json

        try:
            # JWT format: header.payload.signature
            payload_b64 = tokens.id_token.split(".")[1]
            # Add padding if needed
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            email = payload.get("email", "Unknown")
            user_id = payload.get("sub", "Unknown")

            console.print(f"\n[cyan]Email:[/cyan] {email}")
            console.print(f"[cyan]User ID:[/cyan] {user_id}")

        except Exception:
            console.print("\n[cyan]Status:[/cyan] Authenticated")

        # Show token expiry
        if tokens.expires_at:
            now = datetime.now(timezone.utc)
            if tokens.expires_at > now:
                remaining = tokens.expires_at - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                console.print(f"[cyan]Session expires in:[/cyan] {hours}h {minutes}m")
                expiry_str = tokens.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                console.print(f"[dim]({expiry_str})[/dim]")
            else:
                print_warning("Session expired - run 'geni login' to reauthenticate")

        print_success("\nAuthenticated and ready")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get authentication status: {e}")
        raise typer.Exit(1)


# Top-level aliases for analyze commands (convenience)
@app.command("analyze-latest")
def analyze_latest_alias(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum threads to analyze"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze without creating tickets"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Analyze latest annotated threads (alias for 'analyze latest')."""
    from cli.commands.analyze import analyze_latest

    analyze_latest(limit=limit, dry_run=dry_run, verbose=verbose)


@app.command("analyze-specific")
def analyze_specific_alias(
    count: int = typer.Option(10, "--count", "-c", help="Number of recent threads to show"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Select and analyze a specific thread (alias for 'analyze specific')."""
    from cli.commands.analyze import analyze_specific

    analyze_specific(count=count, verbose=verbose)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
