"""Ticket management commands."""

import json
import logging

import typer
from rich.console import Console

from cli.config_manager import ConfigManager
from cli.output_formatter import (
    print_error,
    print_info,
    print_success,
)

console = Console()
app = typer.Typer(help="Ticket management commands")


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
        print_info("Ensure AWS Cognito is configured properly")
        raise typer.Exit(1) from None
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Authentication check failed: {e}")
        raise typer.Exit(1) from None


def _get_auth_token() -> str | None:
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


@app.command("create")
def create_ticket(
    issue_json: str = typer.Argument(..., help="IssueCard JSON string"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only, don't create ticket"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Override provider (jira/notion)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Create a Jira/Notion ticket from IssueCard JSON.

    This command accepts an IssueCard JSON string, validates it against
    the IssueCard schema, and creates a ticket in the configured provider
    (Jira or Notion).

    Examples:

        geni ticket create '{"title": "Issue Title", ...}'

        geni ticket create --dry-run '{"title": "Issue Title", ...}'

        echo '{"title": "Issue Title", ...}' | xargs geni ticket create
    """
    # Check auth status
    _require_auth()

    # Set up logging
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
        config_manager = ConfigManager()
        config = config_manager.load()

        # Use provider from args or config
        ticket_provider = provider or config.provider
        if ticket_provider not in ("jira", "notion"):
            print_error(f"Invalid provider: {ticket_provider}")
            print_info("Supported providers: jira, notion")
            raise typer.Exit(1)

        # Parse and validate JSON
        try:
            issue_data = json.loads(issue_json)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from None

        # Validate against IssueCard schema
        from shared.models.issue_card import IssueCard

        try:
            issue_card = IssueCard(**issue_data)
            if verbose:
                print_success("IssueCard validation passed")
                console.print(f"  [dim]Title:[/dim] {issue_card.title}")
                console.print(f"  [dim]Priority:[/dim] {issue_card.priority}")
                console.print(f"  [dim]Category:[/dim] {issue_card.category}")
        except Exception as e:
            print_error(f"IssueCard validation failed: {e}")
            print_info("Ensure all required fields are present: title, priority, category, "
                      "status, details, description, recommendation, sources")
            raise typer.Exit(1) from None

        # If dry run, stop here
        if dry_run:
            print_success("Validation successful (dry run - no ticket created)")
            console.print()
            console.print("[cyan]IssueCard Contents:[/cyan]")
            console.print(f"  [bold]Title:[/bold] {issue_card.title}")
            console.print(f"  [bold]Priority:[/bold] {issue_card.priority}")
            console.print(f"  [bold]Category:[/bold] {issue_card.category}")
            console.print(f"  [bold]Status:[/bold] {issue_card.status}")
            console.print(f"  [bold]Description:[/bold] {issue_card.description[:100]}...")
            if issue_card.sources:
                console.print(f"  [bold]Thread:[/bold] {issue_card.sources.thread_name}")
            return

        # Import integration client
        from agent.api_clients.integration_client import IntegrationServiceClient

        # Get auth token
        auth_token = _get_auth_token()

        # Initialize client
        integration = IntegrationServiceClient(
            endpoint=config.aws.integration_endpoint,
            api_key=config.aws.api_key,
            auth_token=auth_token,
        )

        # Create ticket
        print_info(f"Creating {ticket_provider.upper()} ticket...")

        # Convert IssueCard to dict for API
        issue_dict = issue_card.model_dump(mode="json", exclude_none=True)

        response = integration.create_ticket(
            provider=ticket_provider,
            issue_data=issue_dict,
        )

        # Extract response details
        ticket_key = response.get("issue_key") or response.get("issue_id") or response.get("key")
        ticket_url = response.get("issue_url") or response.get("url")

        print_success(f"Ticket created: {ticket_key}")
        if ticket_url:
            console.print(f"  [cyan]URL:[/cyan] {ticket_url}")

        # Output machine-readable info for scripting
        if verbose:
            console.print()
            console.print("[dim]Response:[/dim]")
            console.print(json.dumps(response, indent=2))

    except typer.Exit:
        raise
    except FileNotFoundError as e:
        print_error(str(e))
        print_info("Run 'geni init' to set up configuration")
        raise typer.Exit(1) from None
    except Exception as e:
        print_error(f"Failed to create ticket: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from None
