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

# Provider choices for primary and fallback model selection
PROVIDER_CHOICES = [
    questionary.Choice(
        title="AWS Bedrock  — Claude models via AWS",
        value="bedrock",
    ),
    questionary.Choice(
        title="OpenAI       — GPT-4o and o3 models",
        value="openai",
    ),
    questionary.Choice(
        title="Google AI    — Gemini models",
        value="google",
    ),
    questionary.Choice(
        title="Ollama       — Local open-source models",
        value="ollama",
    ),
]

# Models available per provider
MODELS_BY_PROVIDER = {
    "bedrock": [
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
    ],
    "openai": [
        questionary.Choice(title="GPT-4o", value="gpt-4o"),
        questionary.Choice(title="GPT-4o mini", value="gpt-4o-mini"),
        questionary.Choice(title="o3-mini", value="o3-mini"),
    ],
    "google": [
        questionary.Choice(title="Gemini 2.0 Flash", value="gemini-2.0-flash"),
        questionary.Choice(
            title="Gemini 2.5 Pro", value="gemini-2.5-pro-preview-05-06"
        ),
    ],
    "ollama": [
        questionary.Choice(title="Llama 3.2", value="llama3.2"),
        questionary.Choice(title="Mistral", value="mistral"),
        questionary.Choice(title="DeepSeek R1", value="deepseek-r1"),
    ],
}

# Providers that require an API key
API_KEY_PROVIDERS = {
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


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


def _ask_provider_model(prompt_prefix: str = "Primary") -> tuple[str, str, str] | None:
    """Ask user to select a provider, model, and optional API key.

    Returns:
        Tuple of (provider, model_id, api_key) or None if user aborted.
    """
    provider = questionary.select(
        f"{prompt_prefix} provider:",
        choices=PROVIDER_CHOICES,
    ).ask()

    if provider is None:
        return None

    model_id = questionary.select(
        f"{prompt_prefix} model:",
        choices=MODELS_BY_PROVIDER[provider],
    ).ask()

    if model_id is None:
        return None

    api_key = ""
    if provider in API_KEY_PROVIDERS:
        env_var = API_KEY_PROVIDERS[provider]
        api_key = questionary.text(
            f"API key (or leave blank to use ${env_var} env var):",
            default="",
        ).ask()

        if api_key is None:
            return None

    return provider, model_id, api_key


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

    # 4. AWS region (still needed for Bedrock even if not primary)
    region = questionary.select(
        "AWS region:",
        choices=REGION_CHOICES,
        default="us-east-1",
    ).ask()

    if region is None:
        raise typer.Abort()

    # 5. Primary provider + model + API key
    console.print("\n[cyan]Model Configuration (Principle 5: Model Resilience)[/cyan]")
    primary_result = _ask_provider_model("Primary")

    if primary_result is None:
        raise typer.Abort()

    from cli.scaffold import ProviderModel

    primary_model = ProviderModel(
        provider=primary_result[0],
        model_id=primary_result[1],
        api_key=primary_result[2],
    )

    # 6. Fallback models loop
    fallback_models: list[ProviderModel] = []
    while True:
        add_fallback = questionary.confirm(
            "Add a fallback model?",
            default=False,
        ).ask()

        if add_fallback is None:
            raise typer.Abort()

        if not add_fallback:
            break

        fallback_result = _ask_provider_model("Fallback")
        if fallback_result is None:
            raise typer.Abort()

        fallback_models.append(
            ProviderModel(
                provider=fallback_result[0],
                model_id=fallback_result[1],
                api_key=fallback_result[2],
            )
        )

    # 7. Output directory
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
        primary_model=primary_model,
        fallback_models=fallback_models,
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
        console.print("  # Edit .env with your credentials")
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
