"""Scaffold generator for agent project templates.

Generates complete project structures for LangGraph, Strands, and Pi agent frameworks,
following the 8-section architecture pattern and 20 agent engineering principles.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cli.scaffold.base import BaseTemplate


@dataclass
class ScaffoldConfig:
    """Configuration for scaffold generation."""

    project_name: str
    description: str
    framework: str  # "langgraph", "strands", "pi"
    region: str
    model_id: str
    output_dir: str

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
            "config.yaml": template.render_config_yaml(),
            "pyproject.toml": template.render_pyproject_toml(),
            "README.md": template.render_readme(),
            "Makefile": template.render_makefile(),
            ".env.example": template.render_env_example(),
            "prompts/system_prompt.md": template.render_system_prompt(),
            "tests/__init__.py": "",
            "tests/test_agent.py": template.render_test_agent(),
        }

        for rel_path, content in files.items():
            file_path = output_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        return output_path
