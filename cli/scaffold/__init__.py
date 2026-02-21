"""Scaffold generator for agent project templates.

Generates complete project structures for LangGraph, Strands, and Pi agent frameworks,
following the 8-section architecture pattern and 20 agent engineering principles.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cli.scaffold.base import BaseTemplate


@dataclass
class IdentityLayerConfig:
    """Configuration for Principle 3: Separation of Identity Concerns."""

    enabled: bool = False
    layers: list[str] = field(default_factory=lambda: [
        "rules", "personality", "identity", "tools",
        "user", "memory", "bootstrap", "duties",
    ])
    personality_preset: str = "professional"
    rules_focus: list[str] = field(default_factory=lambda: [
        "safety", "tool_governance", "output_quality",
    ])


@dataclass
class ToolGovernanceConfig:
    """Configuration for Principle 9: Tool Governance."""

    profile: str = "minimal"  # minimal | coding | full
    deny: list[str] = field(default_factory=list)
    sub_agent_restrictions: bool = True


@dataclass
class LangSmithConfig:
    """Configuration for LangSmith tracing (Principle 16: Observability)."""

    enabled: bool = False
    project: str = ""  # defaults to project_name at generation time


@dataclass
class SessionConfig:
    """Configuration for Principle 11: Session Persistence."""

    enabled: bool = False
    storage_dir: str = ".agent/sessions"
    prune_after_days: int = 30
    max_entries: int = 500
    rotate_bytes: int = 10_485_760  # 10 MB
    history_limit: int = 50
    compaction_threshold: int = 50
    maintenance_mode: str = "warn"  # "warn" | "enforce"


@dataclass
class SkillsConfig:
    """Configuration for Principle 7: Progressive Capability Disclosure."""

    enabled: bool = False
    skills_dir: str = "skills"
    max_description_chars: int = 150
    read_tool_name: str = "read_file"


@dataclass
class ProviderModel:
    """A provider + model pair for primary or fallback."""

    provider: str  # "bedrock", "openai", "google", "ollama"
    model_id: str  # e.g. "anthropic.claude-sonnet-4-20250514-v1:0"
    api_key: str = ""  # Empty for Bedrock/Ollama


@dataclass
class ScaffoldConfig:
    """Configuration for scaffold generation."""

    project_name: str
    description: str
    framework: str  # "langgraph", "strands", "pi"
    region: str
    primary_model: ProviderModel
    output_dir: str
    fallback_models: list[ProviderModel] = field(default_factory=list)
    identity: IdentityLayerConfig = field(default_factory=IdentityLayerConfig)
    tool_governance: ToolGovernanceConfig = field(default_factory=ToolGovernanceConfig)
    langsmith: LangSmithConfig = field(default_factory=LangSmithConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)

    def validate(self) -> None:
        """Validate configuration values."""
        if not re.match(r"^[a-z][a-z0-9_-]*$", self.project_name):
            raise ValueError(
                f"Invalid project name '{self.project_name}': "
                "must start with lowercase letter, contain only [a-z0-9_-]"
            )
        if self.framework not in ("langgraph", "strands", "pi"):
            raise ValueError(f"Unknown framework: {self.framework}")

    @property
    def model_id(self) -> str:
        """Backward compat — returns primary model ID."""
        return self.primary_model.model_id

    @property
    def all_providers(self) -> set[str]:
        """All unique providers across primary + fallbacks."""
        providers = {self.primary_model.provider}
        for fm in self.fallback_models:
            providers.add(fm.provider)
        return providers

    @property
    def module_name(self) -> str:
        """Python module name (underscores instead of hyphens)."""
        return self.project_name.replace("-", "_")


class ScaffoldGenerator:
    """Orchestrates project scaffold generation."""

    FRAMEWORK_TEMPLATES = {
        "langgraph": "cli.scaffold.langgraph",
        "strands": "cli.scaffold.strands",
        "pi": "cli.scaffold.pi",
    }

    def __init__(self, config: ScaffoldConfig) -> None:
        self.config = config
        self.config.validate()

    def _get_template(self) -> "BaseTemplate":
        """Get the template class for the configured framework."""
        if self.config.framework == "langgraph":
            from cli.scaffold.langgraph import LangGraphTemplate

            return LangGraphTemplate(self.config)
        elif self.config.framework == "strands":
            from cli.scaffold.strands import StrandsTemplate

            return StrandsTemplate(self.config)
        elif self.config.framework == "pi":
            from cli.scaffold.pi import PiTemplate

            return PiTemplate(self.config)
        else:
            raise ValueError(f"Unknown framework: {self.config.framework}")

    def generate(self) -> Path:
        """Generate the full project scaffold.

        Returns:
            Path to the created project directory.
        """
        output_path = Path(self.config.output_dir).resolve()

        if output_path.exists() and any(output_path.iterdir()):
            raise FileExistsError(f"Directory is not empty: {output_path}")

        template = self._get_template()

        # Create directory structure
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "prompts").mkdir(exist_ok=True)
        (output_path / "tests").mkdir(exist_ok=True)

        # Generate all files
        files = {
            "agent.py": template.render_agent_py(),
            "resilience.py": template.render_resilience_py(),
            "tool_policy.py": template.render_tool_policy_py(),
            "config.yaml": template.render_config_yaml(),
            "pyproject.toml": template.render_pyproject_toml(),
            "README.md": template.render_readme(),
            "Makefile": template.render_makefile(),
            ".env.example": template.render_env_example(),
            "prompts/system_prompt.md": template.render_system_prompt(),
            "tests/__init__.py": "",
            "tests/test_agent.py": template.render_test_agent(),
        }

        if self.config.sessions.enabled:
            files["sessions.py"] = template.render_sessions_py()

        if self.config.skills.enabled:
            (output_path / "skills" / "example-skill").mkdir(
                parents=True, exist_ok=True
            )
            files["capabilities.py"] = template.render_capabilities_py()
            files[
                "skills/example-skill/SKILL.md"
            ] = template.render_example_skill_md()

        if self.config.identity.enabled:
            (output_path / "identity").mkdir(exist_ok=True)
            files["brief_packet.py"] = template.render_brief_packet_py()

            layer_renderers = {
                "rules": template.render_identity_rules,
                "personality": template.render_identity_personality,
                "identity": template.render_identity_identity,
                "tools": template.render_identity_tools,
                "user": template.render_identity_user,
                "memory": template.render_identity_memory,
                "bootstrap": template.render_identity_bootstrap,
                "duties": template.render_identity_duties,
            }
            for layer in self.config.identity.layers:
                filename = layer.upper() + ".md"
                renderer = layer_renderers[layer]
                files[f"identity/{filename}"] = renderer()

        for rel_path, content in files.items():
            file_path = output_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        return output_path
