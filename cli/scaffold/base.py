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
        fallback_lines = ""
        if self.config.fallback_models:
            items = []
            for fm in self.config.fallback_models:
                items.append(
                    f'{{"provider": "{fm.provider}", "model_id": "{fm.model_id}"}}'
                )
            fallback_lines = f"\n    fallbacks: list = field(default_factory=lambda: [{', '.join(items)}])"

        cooldown_line = ""
        if self.config.fallback_models:
            cooldown_line = (
                '\n    cooldown_config: dict = field(default_factory=lambda: {'
                '"transient_tiers": [60, 300, 1500, 3600], '
                '"billing_tiers": [18000, 36000, 72000, 86400]})'
            )

        return f"""\
# =============================================================================
# 2. CONFIGURATION
# =============================================================================
{_principle_comments(2)}
from dataclasses import dataclass, field
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
    provider: str = "{self.config.primary_model.provider}"
    max_tokens: int = 4096
    temperature: float = 0.3{fallback_lines}{cooldown_line}


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
    # resilience.py — full fallback cascade + auth rotation module
    # ------------------------------------------------------------------

    def render_resilience_py(self) -> str:
        """Render the complete resilience.py for the generated project.

        Implements Principle 5: Model Resilience — two-nested-loop fallback
        cascades with credential rotation and health tracking.
        """
        return '''\
"""Model Resilience — fallback cascades and auth rotation.

Principle 5: Model Resilience — ensures availability through:
- Inner loop: credential rotation per provider (auth rotation)
- Outer loop: model/provider fallback cascade

Sections:
    - Data Models (FailoverReason, FailoverError, ProfileHealthRecord, ModelCandidate)
    - Error Classifier (classify_error)
    - Cooldown Engine (CooldownEngine)
    - Credential Rotator (CredentialRotator — inner loop)
    - Model Fallback Runner (ModelFallbackRunner — outer loop)
    - Health Store (HealthStore — file-based persistence)
"""

from __future__ import annotations

import enum
import fcntl
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


class FailoverReason(enum.Enum):
    """Reason for triggering a failover."""

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    BILLING = "billing"
    TIMEOUT = "timeout"
    FORMAT = "format"
    UNKNOWN = "unknown"


class FailoverError(Exception):
    """Raised when a failover-eligible error is detected."""

    def __init__(self, message: str, reason: FailoverReason, provider: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.provider = provider


@dataclass
class ProfileHealthRecord:
    """Health tracking for a single credential profile."""

    profile_id: str
    consecutive_errors: int = 0
    last_error_time: float = 0.0
    cooldown_until: float = 0.0
    billing_disabled_until: float = 0.0
    last_used: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "consecutive_errors": self.consecutive_errors,
            "last_error_time": self.last_error_time,
            "cooldown_until": self.cooldown_until,
            "billing_disabled_until": self.billing_disabled_until,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileHealthRecord:
        return cls(
            profile_id=data["profile_id"],
            consecutive_errors=data.get("consecutive_errors", 0),
            last_error_time=data.get("last_error_time", 0.0),
            cooldown_until=data.get("cooldown_until", 0.0),
            billing_disabled_until=data.get("billing_disabled_until", 0.0),
            last_used=data.get("last_used", 0.0),
        )


@dataclass
class ModelCandidate:
    """A model candidate with its associated credential profiles."""

    provider: str
    model_id: str
    profiles: list[ProfileHealthRecord] = field(default_factory=list)


# =============================================================================
# ERROR CLASSIFIER
# =============================================================================


def classify_error(error: Exception) -> FailoverReason | None:
    """Classify an error into a FailoverReason, or None if not failover-eligible.

    Maps HTTP status codes and error message patterns to failover reasons.
    Returns None for errors that should propagate without triggering failover.
    """
    error_str = str(error).lower()

    # Check for HTTP status code patterns
    status_code = _extract_status_code(error)
    if status_code is not None:
        status_map = {
            401: FailoverReason.AUTH,
            403: FailoverReason.AUTH,
            429: FailoverReason.RATE_LIMIT,
            402: FailoverReason.BILLING,
            408: FailoverReason.TIMEOUT,
            504: FailoverReason.TIMEOUT,
        }
        if status_code in status_map:
            return status_map[status_code]

    # Check error message patterns
    auth_patterns = ["invalid api key", "invalid_api_key", "authentication", "unauthorized", "forbidden"]
    rate_patterns = ["rate limit", "rate_limit", "too many requests", "throttl"]
    billing_patterns = ["billing", "payment", "quota exceeded", "insufficient_quota"]
    timeout_patterns = ["timeout", "timed out", "deadline exceeded"]
    format_patterns = ["invalid request", "malformed", "bad request"]

    for pattern in auth_patterns:
        if pattern in error_str:
            return FailoverReason.AUTH

    for pattern in rate_patterns:
        if pattern in error_str:
            return FailoverReason.RATE_LIMIT

    for pattern in billing_patterns:
        if pattern in error_str:
            return FailoverReason.BILLING

    for pattern in timeout_patterns:
        if pattern in error_str:
            return FailoverReason.TIMEOUT

    for pattern in format_patterns:
        if pattern in error_str:
            return FailoverReason.FORMAT

    # Not a failover-eligible error
    return None


def _extract_status_code(error: Exception) -> int | None:
    """Try to extract an HTTP status code from an exception."""
    # Common patterns: error.status_code, error.status, error.code
    for attr in ("status_code", "status", "code", "http_status"):
        val = getattr(error, attr, None)
        if isinstance(val, int) and 400 <= val < 600:
            return val
    return None


# =============================================================================
# COOLDOWN ENGINE
# =============================================================================


class CooldownEngine:
    """Manages cooldown periods for failed credential profiles.

    Uses tiered cooldown escalation:
    - Transient errors (rate limit, timeout): 1min -> 5min -> 25min -> 1hr
    - Billing errors: 5hr -> 10hr -> 20hr -> 24hr
    """

    DEFAULT_TRANSIENT_TIERS = [60, 300, 1500, 3600]
    DEFAULT_BILLING_TIERS = [18000, 36000, 72000, 86400]

    def __init__(
        self,
        transient_tiers: list[int] | None = None,
        billing_tiers: list[int] | None = None,
    ) -> None:
        self.transient_tiers = transient_tiers or self.DEFAULT_TRANSIENT_TIERS
        self.billing_tiers = billing_tiers or self.DEFAULT_BILLING_TIERS

    def apply_cooldown(self, record: ProfileHealthRecord, reason: FailoverReason) -> None:
        """Apply cooldown to a profile based on error reason and failure count."""
        now = time.time()
        record.consecutive_errors += 1
        record.last_error_time = now

        tier_index = min(record.consecutive_errors - 1, 3)

        if reason == FailoverReason.BILLING:
            cooldown_seconds = self.billing_tiers[tier_index]
            record.billing_disabled_until = now + cooldown_seconds
            record.cooldown_until = now + cooldown_seconds
        else:
            cooldown_seconds = self.transient_tiers[tier_index]
            record.cooldown_until = now + cooldown_seconds

        logger.warning(
            "Cooldown applied: profile=%s reason=%s tier=%d cooldown=%ds",
            record.profile_id,
            reason.value,
            tier_index,
            cooldown_seconds,
        )

    def is_available(self, record: ProfileHealthRecord) -> bool:
        """Check if a profile is available (not in cooldown)."""
        now = time.time()
        if record.billing_disabled_until > now:
            return False
        if record.cooldown_until > now:
            return False
        return True


# =============================================================================
# CREDENTIAL ROTATOR (inner loop)
# =============================================================================


class CredentialRotator:
    """Rotates through credential profiles for a single provider.

    Orders profiles by last_used (oldest first) and respects cooldowns.
    Supports pinned credentials that bypass rotation.
    """

    def __init__(self, cooldown_engine: CooldownEngine) -> None:
        self.cooldown_engine = cooldown_engine

    def next_profile(
        self,
        profiles: list[ProfileHealthRecord],
        pinned_id: str | None = None,
    ) -> ProfileHealthRecord:
        """Get the next available profile.

        Args:
            profiles: All credential profiles for this provider.
            pinned_id: If set, prefer this profile (bypass rotation).

        Returns:
            The next available ProfileHealthRecord.

        Raises:
            FailoverError: If no profiles are available.
        """
        # If pinned and available, use it
        if pinned_id:
            for profile in profiles:
                if profile.profile_id == pinned_id and self.cooldown_engine.is_available(profile):
                    return profile

        # Sort by last_used ascending (oldest first)
        available = [
            p for p in sorted(profiles, key=lambda p: p.last_used)
            if self.cooldown_engine.is_available(p)
        ]

        if not available:
            raise FailoverError(
                "All credential profiles are in cooldown",
                reason=FailoverReason.AUTH,
                provider=profiles[0].profile_id.split("/")[0] if profiles else "unknown",
            )

        return available[0]


# =============================================================================
# MODEL FALLBACK RUNNER (outer loop)
# =============================================================================


class ModelFallbackRunner:
    """Orchestrates the two-nested-loop failover:
    - Outer loop: iterates model candidates (primary -> fallback1 -> fallback2 ...)
    - Inner loop: rotates credentials within each candidate\'s provider

    Args:
        primary: The primary model candidate.
        fallbacks: Ordered list of fallback model candidates.
        cooldown_engine: CooldownEngine instance for managing cooldowns.
    """

    def __init__(
        self,
        primary: ModelCandidate,
        fallbacks: list[ModelCandidate] | None = None,
        cooldown_engine: CooldownEngine | None = None,
    ) -> None:
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.cooldown_engine = cooldown_engine or CooldownEngine()
        self.rotator = CredentialRotator(self.cooldown_engine)

    def run(self, invoke_fn: Callable[[str, str, ProfileHealthRecord], Any]) -> Any:
        """Execute with fallback cascade.

        Args:
            invoke_fn: Callable(provider, model_id, profile) -> result.
                Should raise exceptions on failure; the runner classifies
                them and decides whether to failover.

        Returns:
            The result from the first successful invocation.

        Raises:
            FailoverError: If all candidates and profiles are exhausted.
            Exception: If a non-failover error occurs.
        """
        candidates = [self.primary] + self.fallbacks
        last_error: Exception | None = None

        for candidate in candidates:
            # Inner loop: try credential rotation for this candidate
            try:
                profile = self.rotator.next_profile(candidate.profiles)
            except FailoverError:
                logger.warning(
                    "All profiles exhausted for %s/%s, trying next candidate",
                    candidate.provider,
                    candidate.model_id,
                )
                continue

            try:
                profile.last_used = time.time()
                result = invoke_fn(candidate.provider, candidate.model_id, profile)
                # Success — reset health
                profile.consecutive_errors = 0
                profile.cooldown_until = 0.0
                profile.billing_disabled_until = 0.0
                return result
            except Exception as e:
                reason = classify_error(e)
                if reason is None:
                    # Not a failover error — propagate immediately
                    raise

                last_error = e
                self.cooldown_engine.apply_cooldown(profile, reason)
                logger.warning(
                    "Failover triggered: provider=%s model=%s reason=%s error=%s",
                    candidate.provider,
                    candidate.model_id,
                    reason.value,
                    str(e),
                )

                # Try next profile for the same candidate
                while True:
                    try:
                        profile = self.rotator.next_profile(
                            candidate.profiles, pinned_id=None
                        )
                    except FailoverError:
                        break  # All profiles exhausted, move to next candidate

                    try:
                        profile.last_used = time.time()
                        result = invoke_fn(candidate.provider, candidate.model_id, profile)
                        profile.consecutive_errors = 0
                        profile.cooldown_until = 0.0
                        profile.billing_disabled_until = 0.0
                        return result
                    except Exception as inner_e:
                        inner_reason = classify_error(inner_e)
                        if inner_reason is None:
                            raise
                        last_error = inner_e
                        self.cooldown_engine.apply_cooldown(profile, inner_reason)

        raise FailoverError(
            f"All model candidates exhausted. Last error: {last_error}",
            reason=FailoverReason.UNKNOWN,
            provider="all",
        )


# =============================================================================
# HEALTH STORE (file-based persistence)
# =============================================================================


class HealthStore:
    """Persists ProfileHealthRecord list to JSON on disk.

    Uses fcntl.flock() for concurrency-safe reads/writes on Unix.
    Note: On Windows, replace fcntl with msvcrt or skip locking.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        if store_path is None:
            store_path = Path(__file__).parent / ".agent" / "health.json"
        self.store_path = store_path

    def load(self) -> list[ProfileHealthRecord]:
        """Load health records from disk."""
        if not self.store_path.exists():
            return []

        try:
            with open(self.store_path) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            return [ProfileHealthRecord.from_dict(r) for r in data]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Corrupted health store, resetting: %s", e)
            return []

    def save(self, records: list[ProfileHealthRecord]) -> None:
        """Save health records to disk with file locking."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.store_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump([r.to_dict() for r in records], f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def update_record(self, record: ProfileHealthRecord) -> None:
        """Update a single record in the store (merge by profile_id)."""
        records = self.load()
        updated = False
        for i, existing in enumerate(records):
            if existing.profile_id == record.profile_id:
                records[i] = record
                updated = True
                break
        if not updated:
            records.append(record)
        self.save(records)

    def reset_record(self, profile_id: str) -> None:
        """Reset all failure state for a profile (on success)."""
        records = self.load()
        for record in records:
            if record.profile_id == profile_id:
                record.consecutive_errors = 0
                record.cooldown_until = 0.0
                record.billing_disabled_until = 0.0
                break
        self.save(records)


# =============================================================================
# CONFIG LOADER
# =============================================================================


def load_resilience_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load resilience configuration from config.yaml.

    Returns the \'resilience\' section of the config, or defaults.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    if not config_path.exists():
        return {}

    import yaml

    with open(config_path) as f:
        full_config = yaml.safe_load(f) or {}

    return full_config.get("resilience", {})
'''

    # ------------------------------------------------------------------
    # Support files
    # ------------------------------------------------------------------

    def render_config_yaml(self) -> str:
        providers = self.config.all_providers
        has_fallbacks = bool(self.config.fallback_models)

        # Build fallback lines
        fallback_yaml = ""
        if has_fallbacks:
            fallback_yaml = "    fallbacks:\n"
            for fm in self.config.fallback_models:
                fallback_yaml += f'      - provider: "{fm.provider}"\n'
                fallback_yaml += f'        model_id: "{fm.model_id}"\n'

        # Build auth profiles
        auth_profiles = ""
        provider_auth = {
            "bedrock": '      bedrock:\n        type: "aws"\n        # Uses AWS_PROFILE / AWS credentials chain\n',
            "openai": '      openai:\n        type: "api_key"\n        env_var: "OPENAI_API_KEY"\n',
            "google": '      google:\n        type: "api_key"\n        env_var: "GOOGLE_API_KEY"\n',
            "ollama": '      ollama:\n        type: "none"\n        base_url: "http://localhost:11434"\n',
        }
        for p in sorted(providers):
            if p in provider_auth:
                auth_profiles += provider_auth[p]

        # Build resilience section
        resilience_section = f"""\
resilience:
  model:
    primary:
      provider: "{self.config.primary_model.provider}"
      model_id: "{self.config.primary_model.model_id}"
      region: "{self.config.region}"
{fallback_yaml}
  auth:
    profiles:
{auth_profiles}
    cooldowns:
      transient_tiers: [60, 300, 1500, 3600]
      billing_tiers: [18000, 36000, 72000, 86400]
"""

        return f"""\
# {self.config.project_name} configuration
# Principle 2: Configuration-Driven Design — all behaviour via config

agent:
  name: "{self.config.project_name}"
  description: "{self.config.description}"
  framework: "{self.config.framework}"

{resilience_section}
tools:
  profile: "minimal"
  # deny: ["shell_exec"]

operational:
  max_iterations: 10
  timeout_seconds: 120
  log_level: "INFO"
"""

    def render_pyproject_toml(self) -> str:
        deps = ['    "pydantic>=2.0.0"', '    "pyyaml>=6.0.0"']

        # Add provider-specific deps based on selected providers
        providers = self.config.all_providers
        if "bedrock" in providers:
            deps.append('    "boto3>=1.34.0"')
        if "openai" in providers:
            deps.append('    "openai>=1.0.0"')
        if "google" in providers:
            deps.append('    "google-genai>=1.0.0"')
        if "ollama" in providers:
            deps.append('    "ollama>=0.4.0"')

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

Built with **{self.framework_display_name}** with multi-provider model resilience.

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Run the agent
make run
```

## Project Structure

```
{self.config.project_name}/
    agent.py                 # Main agent — 8-section architecture
    resilience.py            # Fallback cascades + auth rotation (Principle 5)
    prompts/
        system_prompt.md     # Externalized system prompt
    config.yaml              # Agent configuration with resilience section
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
| 3. LLM Client | Resilient model client with fallback cascade |
| 4. State Definition | Agent state schema |
| 5. Worker Node | Core processing logic |
| 6. Graph Construction | Agent/graph assembly |
| 7. Utilities | Helper functions and logging |
| 8. Entry Point | CLI and runtime entry |

## Model Resilience (Principle 5)

This project includes a complete resilience module (`resilience.py`) that provides:

- **Fallback cascades** — if the primary model fails, automatically try fallback models
- **Auth rotation** — rotate through credential profiles per provider
- **Cooldown engine** — tiered cooldown for transient and billing errors
- **Health tracking** — persistent health records in `.agent/health.json`

Configure fallback models in `config.yaml` under the `resilience` section.

## Design Principles

This project is built on 20 agent engineering principles for production systems:

{PRINCIPLES_TABLE}

For the full specification, see the
[Agent Engineering Principles](https://github.com/your-org/agent-principles) document.

## Configuration

Edit `config.yaml` to customise agent behaviour without code changes (Principle 2).
Key settings:

- **resilience.model.primary** — Primary model provider and ID
- **resilience.model.fallbacks** — Fallback model cascade
- **resilience.auth.profiles** — Per-provider authentication configuration
- **resilience.auth.cooldowns** — Cooldown tier configuration
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
\tmypy agent.py resilience.py

test:
\tpytest tests/ -v

run:
\tpython agent.py

clean:
\trm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .agent
\tfind . -name "*.pyc" -delete
"""

    def render_env_example(self) -> str:
        providers = self.config.all_providers
        lines = [
            f"# {self.config.project_name} environment variables",
            "# Copy to .env and fill in your values",
            "",
        ]

        if "bedrock" in providers:
            lines.extend([
                "# AWS Bedrock",
                f"AWS_REGION={self.config.region}",
                "AWS_PROFILE=default",
                "",
            ])

        if "openai" in providers:
            lines.extend([
                "# OpenAI",
                "OPENAI_API_KEY=sk-...",
                "",
            ])

        if "google" in providers:
            lines.extend([
                "# Google AI",
                "GOOGLE_API_KEY=AIza...",
                "",
            ])

        if "ollama" in providers:
            lines.extend([
                "# Ollama",
                "OLLAMA_BASE_URL=http://localhost:11434",
                "",
            ])

        lines.extend([
            "# Agent Settings",
            "LOG_LEVEL=INFO",
            "MAX_TOKENS=4096",
            "TEMPERATURE=0.3",
            "",
        ])

        return "\n".join(lines)

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
RESILIENCE_FILE = Path(__file__).parent.parent / "resilience.py"


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


class TestResilienceSyntax:
    \"\"\"Verify generated resilience.py is syntactically valid Python.\"\"\"

    def test_resilience_file_exists(self):
        assert RESILIENCE_FILE.exists(), f"resilience.py not found at {{RESILIENCE_FILE}}"

    def test_resilience_parses(self):
        \"\"\"Ensure resilience.py is valid Python syntax.\"\"\"
        source = RESILIENCE_FILE.read_text()
        ast.parse(source)

    def test_resilience_has_key_classes(self):
        \"\"\"Verify resilience.py contains all required classes.\"\"\"
        source = RESILIENCE_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "FailoverError",
            "CooldownEngine",
            "CredentialRotator",
            "ModelFallbackRunner",
            "HealthStore",
        ]:
            assert expected in class_names, f"{{expected}} class not found in resilience.py"


class TestConfig:
    \"\"\"Verify configuration loads.\"\"\"

    def test_config_defaults(self):
        \"\"\"Config dataclass has sensible defaults.\"\"\"
        source = AGENT_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert "Config" in class_names, "Config class not found in agent.py"
        assert "EvaluatorOutput" in class_names, "EvaluatorOutput class not found"
"""
