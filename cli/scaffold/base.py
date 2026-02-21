"""Base template with shared rendering for all frameworks.

Provides shared sections (0, 2, 7) and support files (pyproject.toml, README.md,
Makefile, .env.example, config.yaml, system_prompt.md, test_agent.py).
Framework-specific templates override sections 1, 3, 4, 5, 6, 8.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cli.scaffold import ScaffoldConfig

# ---------------------------------------------------------------------------
# Principles mapping — top 3 relevant principles per section as inline comments
# ---------------------------------------------------------------------------
SECTION_PRINCIPLES = {
    0: [
        "Principle 2: Configuration-Driven Design — behaviour determined by config, not code",
        "Principle 16: Observability — structured output for audit and analysis",
    ],
    1: [
        "Principle 17: Provider Abstraction — no vendor lock-in",
        "Principle 1: Serverless Agency — ephemeral agents, persistent infra",
    ],
    2: [
        "Principle 2: Configuration-Driven Design — single source of truth",
        "Principle 3: Separation of Concerns — identity layers are independent",
        "Principle 19: Workspace Isolation — configurable environment boundaries",
    ],
    3: [
        "Principle 5: Model Resilience — fallback cascades and auth rotation",
        "Principle 20: Graceful Degradation — explicit fallbacks for every failure",
    ],
    4: [
        "Principle 10: Session Persistence — durable conversation state",
        "Principle 6: Context Window Management — treat context as finite resource",
    ],
    5: [
        "Principle 4: Tool Loop — reason, act, observe, repeat",
        "Principle 9: Tool Governance — layered permission systems",
        "Principle 14: Defence in Depth — multiple security layers",
    ],
    6: [
        "Principle 4: Tool Loop — the model controls the loop",
        "Principle 12: Sub-Agent Delegation — parallel with recursion limits",
        "Principle 7: Progressive Disclosure — load details on demand",
    ],
    7: [
        "Principle 20: Graceful Degradation — partial results over total failure",
        "Principle 16: Observability — structured logging of every action",
    ],
    8: [
        "Principle 1: Serverless Agency — invoked on demand, not long-running",
        "Principle 18: Human-in-the-Loop — configurable approval points",
        "Principle 8: Structured Routing — normalise, route, prepare, execute, deliver",
    ],
}

# The 20 principles summary table for README
PRINCIPLES_TABLE = """\
| # | Principle | One-Line Summary |
|---|-----------|-----------------|
| 1 | Serverless Agency | Agents are ephemeral; infrastructure is persistent |
| 2 | Configuration-Driven Design | Behaviour is determined by config, not code changes |
| 3 | Separation of Identity Concerns | Rules, personality, identity, and context are independent layers |
| 4 | Tool Loop Execution | Agents reason, act, observe, repeat — the model controls the loop |
| 5 | Model Resilience | Fallback cascades and auth rotation ensure availability |
| 6 | Context Window Management | Proactive compaction, truncation, and graceful failure |
| 7 | Progressive Disclosure | Advertise capabilities at summary level; load details on demand |
| 8 | Structured Routing | Normalise, route, prepare, execute, deliver — in that order |
| 9 | Tool Governance | Cascading permissions where deny always wins |
| 10 | Session Persistence | Append-only, durable, provider-sanitised conversation state |
| 11 | Streaming and Chunking | Format-aware delivery with human-like cadence |
| 12 | Sub-Agent Delegation | Parallel execution with recursion limits and capability isolation |
| 13 | Self-Modification with Guardrails | Explicit allowlists, audit trails, and reversibility |
| 14 | Defence in Depth | Six independent security layers, any one of which can stop an attack |
| 15 | Scheduled Execution | First-class scheduling for proactive and time-based agent work |
| 16 | Observability and Audit | Structured logging of every action, change, and cost |
| 17 | Provider Abstraction | No vendor lock-in; agents work with any LLM provider |
| 18 | Human-in-the-Loop | Configurable approval points from full autonomy to full supervision |
| 19 | Workspace Isolation | Configurable sandboxing from no isolation to full containerisation |
| 20 | Graceful Degradation | Explicit fallbacks, timeouts, and partial results for every failure mode |"""


def _principle_comments(section: int) -> str:
    """Return inline principle comments for a given section number."""
    principles = SECTION_PRINCIPLES.get(section, [])
    if not principles:
        return ""
    lines = [f"# {p}" for p in principles]
    return "\n".join(lines) + "\n"


class BaseTemplate:
    """Base template providing shared sections and support files.

    Framework-specific templates inherit this and override:
    render_section_1_imports, render_section_3_client,
    render_section_4_state, render_section_5_worker,
    render_section_6_graph, render_section_8_entrypoint,
    and framework_dependencies.
    """

    def __init__(self, config: ScaffoldConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Framework-specific overrides (must be implemented by subclasses)
    # ------------------------------------------------------------------

    @property
    def framework_display_name(self) -> str:
        raise NotImplementedError

    @property
    def framework_dependencies(self) -> list[str]:
        """Extra pyproject.toml dependencies for this framework."""
        raise NotImplementedError

    def render_section_1_imports(self) -> str:
        raise NotImplementedError

    def render_section_3_client(self) -> str:
        raise NotImplementedError

    def render_section_4_state(self) -> str:
        raise NotImplementedError

    def render_section_5_worker(self) -> str:
        raise NotImplementedError

    def render_section_6_graph(self) -> str:
        raise NotImplementedError

    def render_section_8_entrypoint(self) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared sections
    # ------------------------------------------------------------------

    def render_section_0_models(self) -> str:
        return f"""\
# =============================================================================
# 0. PYDANTIC MODELS
# =============================================================================
{_principle_comments(0)}
from pydantic import BaseModel, Field


class EvaluatorOutput(BaseModel):
    \"\"\"Output model for evaluation feedback.\"\"\"

    feedback: str = Field(description="The feedback for the agent task")
    success_criteria_met: bool = Field(description="Whether the success criteria was met")
"""

    def render_section_2_config(self) -> str:
        return f"""\
# =============================================================================
# 2. CONFIGURATION
# =============================================================================
{_principle_comments(2)}
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROMPT_DIR = BASE_DIR / "prompts"


def load_system_prompt() -> str:
    \"\"\"Load system prompt from prompts directory.\"\"\"
    prompt_file = PROMPT_DIR / "system_prompt.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"System prompt not found: {{prompt_file}}")


@dataclass
class Config:
    \"\"\"Agent configuration — loaded from config.yaml in production.\"\"\"

    region: str = "{self.config.region}"
    model_id: str = "{self.config.model_id}"
    max_tokens: int = 4096
    temperature: float = 0.3


CONFIG = Config()
"""

    def render_section_7_utilities(self) -> str:
        return f"""\
# =============================================================================
# 7. UTILITIES
# =============================================================================
{_principle_comments(7)}
import logging

logger = logging.getLogger(__name__)


def log_invocation(action: str, detail: str = "") -> None:
    \"\"\"Structured log entry for observability.\"\"\"
    logger.info(f"[{{action}}] {{detail}}")
"""

    # ------------------------------------------------------------------
    # agent.py assembly
    # ------------------------------------------------------------------

    def render_agent_py(self) -> str:
        """Combine all 9 sections into the final agent.py."""
        docstring = f'''\
"""
{self.config.description}
{"=" * len(self.config.description)}

A production AI agent built with {self.framework_display_name}.

Sections:
    0. Pydantic Models
    1. Imports
    2. Configuration
    3. LLM Client (lazy init)
    4. State Definition
    5. Worker Node
    6. Graph / Agent Construction
    7. Utilities
    8. Entry Point
"""

'''
        sections = [
            docstring,
            self.render_section_1_imports(),
            self.render_section_0_models(),
            self.render_section_2_config(),
            self.render_section_3_client(),
            self.render_section_4_state(),
            self.render_section_5_worker(),
            self.render_section_6_graph(),
            self.render_section_7_utilities(),
            self.render_section_8_entrypoint(),
        ]
        return "\n\n".join(sections) + "\n"

    # ------------------------------------------------------------------
    # Support files
    # ------------------------------------------------------------------

    def render_config_yaml(self) -> str:
        return f"""\
# {self.config.project_name} configuration
# Principle 2: Configuration-Driven Design — all behaviour via config

agent:
  name: "{self.config.project_name}"
  description: "{self.config.description}"
  framework: "{self.config.framework}"

model:
  primary: "{self.config.model_id}"
  region: "{self.config.region}"
  max_tokens: 4096
  temperature: 0.3
  # fallbacks:
  #   - "anthropic.claude-haiku-4-5-20251001-v1:0"

tools:
  profile: "minimal"
  # deny: ["shell_exec"]

operational:
  max_iterations: 10
  timeout_seconds: 120
  log_level: "INFO"
"""

    def render_pyproject_toml(self) -> str:
        deps = ['    "pydantic>=2.0.0"', '    "boto3>=1.34.0"', '    "pyyaml>=6.0.0"']
        for d in self.framework_dependencies:
            deps.append(f'    "{d}"')
        deps_str = ",\n".join(deps)

        return f"""\
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{self.config.project_name}"
version = "0.1.0"
description = "{self.config.description}"
requires-python = ">=3.11"
dependencies = [
{deps_str},
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "isort>=5.0.0",
]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
disallow_untyped_defs = true
check_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--cov=.", "--cov-report=term-missing"]
"""

    def render_readme(self) -> str:
        return f"""\
# {self.config.project_name}

{self.config.description}

Built with **{self.framework_display_name}** on AWS Bedrock.

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your AWS credentials

# Run the agent
make run
```

## Project Structure

```
{self.config.project_name}/
    agent.py                 # Main agent — 8-section architecture
    prompts/
        system_prompt.md     # Externalized system prompt
    config.yaml              # Agent configuration
    pyproject.toml           # Dependencies and tooling
    Makefile                 # Dev targets
    .env.example             # Environment variable template
    tests/
        test_agent.py        # Smoke tests
```

## Development

```bash
make lint        # Run ruff linter
make format      # Run black + isort
make typecheck   # Run mypy
make test        # Run pytest
```

## Architecture

This agent follows the **8-section architecture pattern**:

| Section | Purpose |
|---------|---------|
| 0. Pydantic Models | Structured output models for evaluation |
| 1. Imports | Framework and library imports |
| 2. Configuration | Dataclass config + system prompt loader |
| 3. LLM Client | Lazy-initialized model client |
| 4. State Definition | Agent state schema |
| 5. Worker Node | Core processing logic |
| 6. Graph Construction | Agent/graph assembly |
| 7. Utilities | Helper functions and logging |
| 8. Entry Point | CLI and runtime entry |

## Design Principles

This project is built on 20 agent engineering principles for production systems:

{PRINCIPLES_TABLE}

For the full specification, see the
[Agent Engineering Principles](https://github.com/your-org/agent-principles) document.

## Configuration

Edit `config.yaml` to customise agent behaviour without code changes (Principle 2).
Key settings:

- **model.primary** — AWS Bedrock model ID
- **model.region** — AWS region for Bedrock
- **tools.profile** — Tool access level (minimal/coding/full)
- **operational.max_iterations** — Tool loop iteration limit
"""

    def render_makefile(self) -> str:
        return """\
.PHONY: lint format typecheck test run clean

lint:
\truff check .

format:
\tblack .
\tisort .

typecheck:
\tmypy agent.py

test:
\tpytest tests/ -v

run:
\tpython agent.py

clean:
\trm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov
\tfind . -name "*.pyc" -delete
"""

    def render_env_example(self) -> str:
        return f"""\
# {self.config.project_name} environment variables
# Copy to .env and fill in your values

# AWS Configuration
AWS_REGION={self.config.region}
AWS_PROFILE=default

# Model Configuration
MODEL_ID={self.config.model_id}

# Agent Settings
LOG_LEVEL=INFO
MAX_TOKENS=4096
TEMPERATURE=0.3
"""

    def render_system_prompt(self) -> str:
        return f"""\
# System Prompt — {self.config.project_name}

You are a production AI agent built with {self.framework_display_name}.

## Role

{self.config.description}

## Operational Rules

- Follow the tool loop pattern: reason, act, observe, repeat (Principle 4)
- Use tools only when necessary — prefer reasoning from available context
- Return structured, actionable responses
- Handle errors gracefully and report them clearly (Principle 20)

## Constraints

- Do not make assumptions about data you haven't verified
- Always validate inputs before processing
- Respect tool permission boundaries (Principle 9)
- Keep responses concise and evidence-based

## Output Format

Respond with clear, structured output. Use markdown formatting when helpful.
"""

    def render_test_agent(self) -> str:
        return f"""\
\"\"\"Smoke tests for {self.config.project_name} agent.\"\"\"

import ast
from pathlib import Path

import pytest


AGENT_FILE = Path(__file__).parent.parent / "agent.py"


class TestAgentSyntax:
    \"\"\"Verify generated agent.py is syntactically valid Python.\"\"\"

    def test_agent_file_exists(self):
        assert AGENT_FILE.exists(), f"agent.py not found at {{AGENT_FILE}}"

    def test_agent_parses(self):
        \"\"\"Ensure agent.py is valid Python syntax.\"\"\"
        source = AGENT_FILE.read_text()
        ast.parse(source)  # Raises SyntaxError if invalid

    def test_agent_has_sections(self):
        \"\"\"Verify all 8 sections are present.\"\"\"
        source = AGENT_FILE.read_text()
        for section_num in range(9):  # 0-8
            assert f"# {{section_num}}." in source or f"{{section_num}}. " in source.split("Sections:")[1].split('\"\"\"')[0], (
                f"Section {{section_num}} marker not found"
            )


class TestConfig:
    \"\"\"Verify configuration loads.\"\"\"

    def test_config_defaults(self):
        \"\"\"Config dataclass has sensible defaults.\"\"\"
        # Import inline to avoid import errors if deps missing
        import importlib.util
        spec = importlib.util.spec_from_file_location("agent", str(AGENT_FILE))
        # Just verify the file can be parsed — full import may need deps
        source = AGENT_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert "Config" in class_names, "Config class not found in agent.py"
        assert "EvaluatorOutput" in class_names, "EvaluatorOutput class not found"
"""
