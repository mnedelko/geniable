"""Scaffold command — generate agent project templates."""

import re

import questionary
import typer
from rich.console import Console

from cli.output_formatter import print_error, print_info, print_success

console = Console()
app = typer.Typer(help="Generate agent project scaffolds")

# Available frameworks with descriptions
FRAMEWORK_CHOICES = [
    questionary.Choice(
        title="LangGraph  — StateGraph + LangChain, closest to reference architecture",
        value="langgraph",
    ),
    questionary.Choice(
        title="Strands    — strands-agents SDK, model-first with @tool decorators",
        value="strands",
    ),
    questionary.Choice(
        title="Pi         — Pi agent framework, declarative config with gateway pattern",
        value="pi",
    ),
]

REGION_CHOICES = [
    "us-east-1",
    "us-west-2",
    "ap-southeast-2",
    "eu-west-1",
]

MODEL_CHOICES = [
    questionary.Choice(
        title="Claude Sonnet 4  (anthropic.claude-sonnet-4-20250514-v1:0)",
        value="anthropic.claude-sonnet-4-20250514-v1:0",
    ),
    questionary.Choice(
        title="Claude Haiku 4.5 (anthropic.claude-haiku-4-5-20251001-v1:0)",
        value="anthropic.claude-haiku-4-5-20251001-v1:0",
    ),
    questionary.Choice(
        title="Claude Opus 4    (anthropic.claude-opus-4-20250514-v1:0)",
        value="anthropic.claude-opus-4-20250514-v1:0",
    ),
]


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


def _validate_project_name(name: str) -> bool | str:
    """Validate project name format."""
    if not name:
        return "Project name is required"
    if not re.match(r"^[a-z][a-z0-9_-]*$", name):
        return "Must start with lowercase letter, contain only [a-z0-9_-]"
    return True


@app.command("create")
def create() -> None:
    """Create a new agent project from a template.

    Interactive wizard that collects framework choice, project name,
    and configuration, then generates a complete project structure.
    """
    _require_auth()

    console.print("\n[bold cyan]Agent Project Generator[/bold cyan]")
    console.print("Create a new agent project from a production template.\n")

    # 1. Framework selection
    framework = questionary.select(
        "Select agent framework:",
        choices=FRAMEWORK_CHOICES,
    ).ask()

    if framework is None:
        raise typer.Abort()

    # 2. Project name
    project_name = questionary.text(
        "Project name:",
        default="my-agent",
        validate=_validate_project_name,
    ).ask()

    if project_name is None:
        raise typer.Abort()

    # 3. Description
    description = questionary.text(
        "Agent description:",
        default="A production AI agent",
    ).ask()

    if description is None:
        raise typer.Abort()

    # 4. AWS region
    region = questionary.select(
        "AWS region:",
        choices=REGION_CHOICES,
        default="us-east-1",
    ).ask()

    if region is None:
        raise typer.Abort()

    # 5. Model
    model_id = questionary.select(
        "Default model:",
        choices=MODEL_CHOICES,
    ).ask()

    if model_id is None:
        raise typer.Abort()

    # 6. Output directory
    output_dir = questionary.text(
        "Output directory:",
        default=f"./{project_name}",
    ).ask()

    if output_dir is None:
        raise typer.Abort()

    # Generate
    from cli.scaffold import ScaffoldConfig, ScaffoldGenerator

    config = ScaffoldConfig(
        project_name=project_name,
        description=description,
        framework=framework,
        region=region,
        model_id=model_id,
        output_dir=output_dir,
    )

    try:
        print_info(f"Generating {framework} project: {project_name}")
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        print_success(f"\nProject created: {output_path}")

        # Show file tree
        console.print("\n[cyan]Generated files:[/cyan]")
        for child in sorted(output_path.rglob("*")):
            if child.is_file():
                rel = child.relative_to(output_path)
                console.print(f"  {rel}")

        # Next steps
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print(f"  cd {output_dir}")
        console.print("  python -m venv venv && source venv/bin/activate")
        console.print('  pip install -e ".[dev]"')
        console.print("  cp .env.example .env")
        console.print("  # Edit .env with your AWS credentials")
        console.print("  make run")

    except FileExistsError as e:
        print_error(str(e))
        raise typer.Exit(1) from None
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        print_error(f"Scaffold generation failed: {e}")
        raise typer.Exit(1) from None
