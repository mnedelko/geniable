"""Scaffold command — generate agent project templates."""

import re

import questionary
import typer
from rich.console import Console

from cli.output_formatter import print_error, print_info, print_success
from cli.scaffold import (
    IdentityLayerConfig,
    LangSmithConfig,
    ObservabilityConfig,
    SessionConfig,
    ToolGovernanceConfig,
    ToolsConfig,
)

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

# Identity layer choices (Principle 3: Separation of Identity Concerns)
IDENTITY_LAYERS = [
    questionary.Choice(
        title="Single System Prompt only — skip identity layers",
        value="_single_prompt",
        checked=False,
    ),
    questionary.Choice(
        title="Operational Rules  — core instructions and constraints",
        value="rules",
        checked=True,
    ),
    questionary.Choice(
        title="Personality        — voice, tone, communication style",
        value="personality",
        checked=True,
    ),
    questionary.Choice(
        title="Public Identity    — name, bio, presentation",
        value="identity",
        checked=True,
    ),
    questionary.Choice(
        title="Tool Guidance      — tool usage tips and workflows",
        value="tools",
        checked=True,
    ),
    questionary.Choice(
        title="User Context       — user preferences and history",
        value="user",
        checked=True,
    ),
    questionary.Choice(
        title="Persistent Memory  — long-term notes and observations",
        value="memory",
        checked=True,
    ),
    questionary.Choice(
        title="Bootstrap          — one-time setup instructions",
        value="bootstrap",
        checked=True,
    ),
    questionary.Choice(
        title="Scheduled Duties   — periodic task definitions",
        value="duties",
        checked=True,
    ),
]

PERSONALITY_PRESETS = [
    questionary.Choice(
        title="Professional  — formal, precise, business-appropriate",
        value="professional",
    ),
    questionary.Choice(
        title="Friendly      — warm, conversational, approachable",
        value="friendly",
    ),
    questionary.Choice(
        title="Technical     — detailed, specification-oriented, exact",
        value="technical",
    ),
    questionary.Choice(
        title="Concise       — minimal, direct, no fluff",
        value="concise",
    ),
    questionary.Choice(
        title="Custom        — blank template for manual editing",
        value="custom",
    ),
]

RULES_FOCUS_AREAS = [
    questionary.Choice(
        title="Safety           — prevent harmful outputs",
        value="safety",
        checked=True,
    ),
    questionary.Choice(
        title="Tool Governance  — permission-based tool usage",
        value="tool_governance",
        checked=True,
    ),
    questionary.Choice(
        title="Data Privacy     — PII handling and data protection",
        value="data_privacy",
    ),
    questionary.Choice(
        title="Output Quality   — structured, evidence-based responses",
        value="output_quality",
        checked=True,
    ),
    questionary.Choice(
        title="Error Handling   — graceful degradation and reporting",
        value="error_handling",
    ),
]


TOOL_PROFILE_CHOICES = [
    questionary.Choice(
        title="Minimal   — session status only (most restrictive)",
        value="minimal",
    ),
    questionary.Choice(
        title="Coding    — file, runtime, sessions, memory access",
        value="coding",
    ),
    questionary.Choice(
        title="Full      — all tools permitted (no restrictions)",
        value="full",
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


def _ask_identity_layers() -> IdentityLayerConfig:
    """Ask user about identity layer configuration (Principle 3).

    Returns:
        IdentityLayerConfig with user selections.
    """
    enable = questionary.confirm(
        "Enable identity layers? (Principle 3: Separation of Identity Concerns)",
        default=True,
    ).ask()

    if enable is None:
        raise typer.Abort()

    if not enable:
        return IdentityLayerConfig(enabled=False)

    layers = questionary.checkbox(
        "Select identity layers:",
        choices=IDENTITY_LAYERS,
    ).ask()

    if layers is None:
        raise typer.Abort()

    while not layers:
        console.print("[red]Please select at least one option.[/red]")
        layers = questionary.checkbox(
            "Select identity layers:",
            choices=IDENTITY_LAYERS,
        ).ask()
        if layers is None:
            raise typer.Abort()

    # "Single System Prompt only" — skip identity layers entirely
    if "_single_prompt" in layers:
        # If real layers were also selected, they take precedence
        real_layers = [layer for layer in layers if layer != "_single_prompt"]
        if not real_layers:
            return IdentityLayerConfig(enabled=False)
        layers = real_layers

    personality_preset = "professional"
    if "personality" in layers:
        personality_preset = questionary.select(
            "Personality preset:",
            choices=PERSONALITY_PRESETS,
        ).ask()

        if personality_preset is None:
            raise typer.Abort()

    rules_focus: list[str] = ["safety", "tool_governance", "output_quality"]
    if "rules" in layers:
        rules_focus = questionary.checkbox(
            "Rules focus areas:",
            choices=RULES_FOCUS_AREAS,
        ).ask()

        if rules_focus is None:
            raise typer.Abort()

    return IdentityLayerConfig(
        enabled=True,
        layers=layers,
        personality_preset=personality_preset,
        rules_focus=rules_focus,
    )


def _ask_tool_governance() -> ToolGovernanceConfig:
    """Ask user about tool governance configuration (Principle 9).

    Returns:
        ToolGovernanceConfig with user selections.
    """
    profile = questionary.select(
        "Tool access profile:",
        choices=TOOL_PROFILE_CHOICES,
    ).ask()

    if profile is None:
        raise typer.Abort()

    sub_agent_restrictions = questionary.confirm(
        "Enable sub-agent restrictions? (prevent sub-agents from accessing orchestration tools)",
        default=True,
    ).ask()

    if sub_agent_restrictions is None:
        raise typer.Abort()

    return ToolGovernanceConfig(
        profile=profile,
        sub_agent_restrictions=sub_agent_restrictions,
    )


def _ask_langsmith(project_name: str) -> LangSmithConfig:
    """Ask user about LangSmith tracing configuration (Principle 16).

    Returns:
        LangSmithConfig with user selections.
    """
    enable = questionary.confirm(
        "Enable LangSmith tracing? (Principle 16: Observability)",
        default=True,
    ).ask()

    if enable is None:
        raise typer.Abort()

    if not enable:
        return LangSmithConfig(enabled=False)

    project = questionary.text(
        "LangSmith project name:",
        default=project_name,
    ).ask()

    if project is None:
        raise typer.Abort()

    return LangSmithConfig(enabled=True, project=project)


MAINTENANCE_MODE_CHOICES = [
    questionary.Choice(
        title="Warn     — log warnings but don't prune/cap automatically",
        value="warn",
    ),
    questionary.Choice(
        title="Enforce  — automatically prune stale sessions and cap entries",
        value="enforce",
    ),
]


def _ask_session_persistence() -> SessionConfig:
    """Ask user about session persistence configuration (Principle 11).

    Returns:
        SessionConfig with user selections.
    """
    enable = questionary.confirm(
        "Enable session persistence? (Principle 11: Append-only conversation state)",
        default=False,
    ).ask()

    if enable is None:
        raise typer.Abort()

    if not enable:
        return SessionConfig(enabled=False)

    maintenance_mode = questionary.select(
        "Session maintenance mode:",
        choices=MAINTENANCE_MODE_CHOICES,
    ).ask()

    if maintenance_mode is None:
        raise typer.Abort()

    return SessionConfig(enabled=True, maintenance_mode=maintenance_mode)


def _ask_observability() -> ObservabilityConfig:
    """Ask user about operational observability configuration (Principle 17).

    Returns:
        ObservabilityConfig with user selections.
    """
    enable = questionary.confirm(
        "Enable operational observability? (Principle 17: Structured logging, audit, cost tracking)",
        default=False,
    ).ask()

    if enable is None:
        raise typer.Abort()

    if not enable:
        return ObservabilityConfig(enabled=False)

    return ObservabilityConfig(enabled=True)


def _ask_tools() -> ToolsConfig:
    """Ask user about tool availability (Principle 9: Tool Governance).

    Returns:
        ToolsConfig with user selections.
    """
    enable = questionary.confirm(
        "Will your agent use tools? (generates tools/ folder with boilerplate)",
        default=True,
    ).ask()

    if enable is None:
        raise typer.Abort()

    if not enable:
        return ToolsConfig(enabled=False)

    return ToolsConfig(enabled=True)


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

    # 7. Identity layers (Principle 3)
    console.print("\n[cyan]Identity Layers (Principle 3: Separation of Concerns)[/cyan]")
    identity_config = _ask_identity_layers()

    # 8. Tool governance (Principle 9)
    console.print("\n[cyan]Tool Governance (Principle 9: Layered Permissions)[/cyan]")
    tool_governance_config = _ask_tool_governance()

    # 9. Tools (Principle 9: Tool Governance — executable tools)
    console.print("\n[cyan]Tools (Principle 9: Executable Tool Functions)[/cyan]")
    tools_config = _ask_tools()

    # 10. Output directory
    output_dir = questionary.text(
        "Output directory:",
        default=f"./{project_name}",
    ).ask()

    if output_dir is None:
        raise typer.Abort()

    # 11. LangSmith tracing (Principle 16)
    console.print("\n[cyan]Observability (Principle 16: LangSmith Tracing)[/cyan]")
    langsmith_config = _ask_langsmith(project_name)

    # 12. Session persistence (Principle 11)
    console.print("\n[cyan]Session Persistence (Principle 11: Conversation State)[/cyan]")
    session_config = _ask_session_persistence()

    # 13. Operational observability (Principle 17)
    console.print(
        "\n[cyan]Operational Observability (Principle 17: Logging, Audit, Cost Tracking)[/cyan]"
    )
    observability_config = _ask_observability()

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
        identity=identity_config,
        tool_governance=tool_governance_config,
        langsmith=langsmith_config,
        sessions=session_config,
        tools=tools_config,
        observability=observability_config,
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
