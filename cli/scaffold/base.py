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

        has_identity = self.config.identity.enabled
        has_skills = self.config.skills.enabled

        if has_identity and has_skills:
            # Variant 1: Identity + Skills
            load_prompt_fn = '''\

def load_system_prompt(mode: str = "full") -> str:
    """Load system prompt via brief-packet assembly (Principle 3) + skills (Principle 7).

    Args:
        mode: "full" for main agent, "minimal" for sub-agents, "none" for bare calls.
    """
    from brief_packet import assemble_brief_packet
    from capabilities import build_snapshot, build_skills_system_prompt_section

    base_prompt = assemble_brief_packet(mode=mode)
    snapshot = build_snapshot(str(BASE_DIR))
    skills_section = build_skills_system_prompt_section(snapshot.prompt)
    if skills_section:
        return base_prompt + "\\n\\n" + skills_section
    return base_prompt'''
        elif has_identity:
            # Variant 2: Identity only
            load_prompt_fn = '''\

def load_system_prompt(mode: str = "full") -> str:
    """Load system prompt via brief-packet assembly (Principle 3).

    Args:
        mode: "full" for main agent, "minimal" for sub-agents, "none" for bare calls.
    """
    from brief_packet import assemble_brief_packet
    return assemble_brief_packet(mode=mode)'''
        elif has_skills:
            # Variant 3: Skills only
            load_prompt_fn = '''\

def load_system_prompt() -> str:
    """Load system prompt from prompts directory + skills (Principle 7)."""
    from capabilities import build_snapshot, build_skills_system_prompt_section

    prompt_file = PROMPT_DIR / "system_prompt.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"System prompt not found: {prompt_file}")
    base_prompt = prompt_file.read_text()
    snapshot = build_snapshot(str(BASE_DIR))
    skills_section = build_skills_system_prompt_section(snapshot.prompt)
    if skills_section:
        return base_prompt + "\\n\\n" + skills_section
    return base_prompt'''
        else:
            # Variant 4: Neither
            load_prompt_fn = '''\

def load_system_prompt() -> str:
    """Load system prompt from prompts directory."""
    prompt_file = PROMPT_DIR / "system_prompt.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"System prompt not found: {prompt_file}")'''

        return f"""\
# =============================================================================
# 2. CONFIGURATION
# =============================================================================
{_principle_comments(2)}
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROMPT_DIR = BASE_DIR / "prompts"

{load_prompt_fn}


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
        if self.config.observability.enabled:
            return f"""\
# =============================================================================
# 7. UTILITIES
# =============================================================================
{_principle_comments(7)}
from observability import setup_observability, get_logger

_obs = setup_observability()
logger = get_logger("agent")


def log_invocation(action: str, detail: str = "") -> None:
    \"\"\"Structured log entry for observability.\"\"\"
    logger.info(action, {{"detail": detail}})
"""
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
    # tool_policy.py — Tool Governance (Principle 9)
    # ------------------------------------------------------------------

    def render_tool_policy_py(self) -> str:
        """Render the complete tool_policy.py for the generated project.

        Implements Principle 9: Tool Governance — layered permission systems
        with deny-wins-over-allow logic, tool group selectors, and sub-agent
        restrictions.
        """
        return '''\
"""Tool Governance — layered permission systems.

Principle 9: Tool Governance — provides:
- Tool profiles (minimal, coding, full) controlling access levels
- Deny-wins-over-allow logic as the cardinal safety property
- Tool group selectors expanding shorthand to concrete tool names
- Sub-agent restrictions preventing access to orchestration tools

Sections:
    - Tool Groups (TOOL_GROUPS)
    - Profiles (PROFILES)
    - Sub-Agent Restrictions (DEFAULT_SUBAGENT_DENY)
    - Group Expansion (expand_groups)
    - Policy Matching (matches_policy)
    - Config Loading (load_tool_policy)
    - Tool Filtering (filter_tools)
    - Validation (validate_tool_config)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL GROUPS — shorthand selectors that expand to concrete tool names
# =============================================================================

TOOL_GROUPS: dict[str, list[str]] = {
    "group:fs": [
        "read_file",
        "write_file",
        "list_directory",
        "create_directory",
        "delete_file",
        "move_file",
        "search_files",
    ],
    "group:runtime": [
        "shell_exec",
        "python_exec",
        "subprocess_run",
        "eval_code",
    ],
    "group:web": [
        "http_request",
        "web_search",
        "web_fetch",
        "url_fetch",
    ],
    "group:memory": [
        "memory_read",
        "memory_write",
        "memory_search",
        "memory_delete",
    ],
    "group:sessions": [
        "session_status",
        "session_list",
        "session_create",
        "session_delete",
    ],
    "group:messaging": [
        "send_message",
        "read_messages",
        "channel_list",
        "thread_reply",
    ],
}

ALL_GROUP_NAMES = set(TOOL_GROUPS.keys())


# =============================================================================
# PROFILES — named access levels mapping to allowed tool groups
# =============================================================================

PROFILES: dict[str, list[str]] = {
    "minimal": ["group:sessions"],
    "coding": ["group:fs", "group:runtime", "group:sessions", "group:memory"],
    "full": list(TOOL_GROUPS.keys()),
}

VALID_PROFILES = set(PROFILES.keys())


# =============================================================================
# SUB-AGENT RESTRICTIONS — hardcoded deny for sub-agents
# =============================================================================

DEFAULT_SUBAGENT_DENY: list[str] = [
    "session_create",
    "session_delete",
    "send_message",
    "channel_list",
    "thread_reply",
    "memory_delete",
    "shell_exec",
]


# =============================================================================
# GROUP EXPANSION
# =============================================================================


def expand_groups(items: list[str]) -> list[str]:
    """Expand group selectors (e.g. 'group:fs') into concrete tool names.

    Items that are not group selectors are passed through unchanged.

    Args:
        items: List of tool names and/or group selectors.

    Returns:
        Flat list of concrete tool names.
    """
    result: list[str] = []
    for item in items:
        if item.startswith("group:") and item in TOOL_GROUPS:
            result.extend(TOOL_GROUPS[item])
        else:
            result.append(item)
    return result


# =============================================================================
# POLICY MATCHING — deny-wins-over-allow (cardinal safety property)
# =============================================================================


def matches_policy(tool_name: str, allow_list: list[str], deny_list: list[str]) -> bool:
    """Check if a tool is permitted by the policy.

    The cardinal safety property: deny is checked FIRST.
    If a tool appears in both allow and deny, it is DENIED.

    Args:
        tool_name: Name of the tool to check.
        allow_list: Expanded list of allowed tool names.
        deny_list: Expanded list of denied tool names.

    Returns:
        True if the tool is permitted, False otherwise.
    """
    # Deny wins over allow — always check deny first
    if tool_name in deny_list:
        return False

    # If allow list is empty, nothing is allowed
    if not allow_list:
        return False

    return tool_name in allow_list


# =============================================================================
# CONFIG LOADING
# =============================================================================


def load_tool_policy(config_path: Path | None = None) -> dict[str, Any]:
    """Load the tool governance section from config.yaml.

    Args:
        config_path: Path to config.yaml. Defaults to ./config.yaml.

    Returns:
        Dict with keys: profile, allow, deny, sub_agent_restrictions.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    if not config_path.exists():
        logger.warning("Config file not found: %s — using minimal profile", config_path)
        return {
            "profile": "minimal",
            "allow": expand_groups(PROFILES["minimal"]),
            "deny": [],
            "sub_agent_restrictions": True,
        }

    import yaml

    with open(config_path) as f:
        full_config = yaml.safe_load(f) or {}

    tools_section = full_config.get("tools", {})
    profile_name = tools_section.get("profile", "minimal")
    deny_raw = tools_section.get("deny", [])
    sub_agent_restrictions = tools_section.get("sub_agent_restrictions", True)

    # Expand profile groups into concrete allow list
    profile_groups = PROFILES.get(profile_name, PROFILES["minimal"])
    allow = expand_groups(profile_groups)

    # Expand any group selectors in the deny list
    deny = expand_groups(deny_raw)

    return {
        "profile": profile_name,
        "allow": allow,
        "deny": deny,
        "sub_agent_restrictions": sub_agent_restrictions,
    }


# =============================================================================
# TOOL FILTERING — public API
# =============================================================================


def filter_tools(
    tools: list[str],
    config_path: Path | None = None,
    is_subagent: bool = False,
) -> list[str]:
    """Filter a tool list through the governance policy.

    This is the main public API. Pass your list of tool names and get back
    only the ones permitted by the current profile, deny list, and
    sub-agent restrictions.

    Args:
        tools: List of tool names to filter.
        config_path: Path to config.yaml. Defaults to ./config.yaml.
        is_subagent: If True, apply additional sub-agent restrictions.

    Returns:
        Filtered list of permitted tool names.
    """
    policy = load_tool_policy(config_path)
    allow = policy["allow"]
    deny = list(policy["deny"])  # copy to avoid mutating cached policy

    # Apply sub-agent restrictions if applicable
    if is_subagent and policy.get("sub_agent_restrictions", True):
        deny.extend(DEFAULT_SUBAGENT_DENY)

    permitted = [t for t in tools if matches_policy(t, allow, deny)]

    logger.info(
        "Tool governance: profile=%s permitted=%d/%d denied=%d",
        policy["profile"],
        len(permitted),
        len(tools),
        len(tools) - len(permitted),
    )

    return permitted


# =============================================================================
# VALIDATION
# =============================================================================


def validate_tool_config(config_path: Path | None = None) -> list[str]:
    """Validate the tool governance configuration.

    Checks:
    - Profile name is valid (minimal, coding, full)
    - Deny list entries are valid tool names or group selectors

    Args:
        config_path: Path to config.yaml. Defaults to ./config.yaml.

    Returns:
        List of validation error strings (empty if valid).
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    if not config_path.exists():
        return [f"Config file not found: {config_path}"]

    import yaml

    with open(config_path) as f:
        full_config = yaml.safe_load(f) or {}

    tools_section = full_config.get("tools", {})
    errors: list[str] = []

    # Validate profile name
    profile_name = tools_section.get("profile", "minimal")
    if profile_name not in VALID_PROFILES:
        errors.append(
            f"Invalid profile '{profile_name}': must be one of {sorted(VALID_PROFILES)}"
        )

    # Validate deny list entries
    deny_raw = tools_section.get("deny", [])
    if not isinstance(deny_raw, list):
        errors.append(f"'deny' must be a list, got {type(deny_raw).__name__}")
    else:
        all_known_tools = set()
        for group_tools in TOOL_GROUPS.values():
            all_known_tools.update(group_tools)

        for item in deny_raw:
            if item.startswith("group:") and item not in ALL_GROUP_NAMES:
                errors.append(
                    f"Unknown group selector '{item}': must be one of {sorted(ALL_GROUP_NAMES)}"
                )
            # Individual tool names are not validated — allow custom tools

    if errors:
        for err in errors:
            logger.warning("Tool config validation: %s", err)

    return errors
'''

    # ------------------------------------------------------------------
    # observability.py — Operational Observability (Principle 17)
    # ------------------------------------------------------------------

    def render_observability_py(self) -> str:
        """Render the complete observability.py for the generated project.

        Implements Principle 17: Observability, Audit, and Accountability —
        consolidates 7 blueprint modules into a single file:
        1. Types, 2. Structured Logger, 3. Session Transcript,
        4. Usage/Cost, 5. Prompt Log, 6. Config Audit,
        7. Diagnostic Events, 8. Setup/Integration.
        """
        return '''\
"""Operational Observability — structured logging, audit, and accountability.

Principle 17: Observability, Audit, and Accountability — provides:
- Structured JSON logging with dual-destination (CloudWatch/local)
- Session transcript recording (append-only JSONL)
- Per-invocation cost tracking with model-aware pricing
- Prompt snapshot logging for forensic replay
- Configuration audit with hash-based change detection
- Pluggable diagnostic event system

Sections:
    - Types (MessageRole, TokenUsage, CostBreakdown, ModelCostConfig,
             ToolCallRecord, MessageRecord, ConfigAuditRecord, DiagnosticEvent)
    - Structured Logger (LogLevel, JsonFormatter, setup_logging, get_logger)
    - Session Transcript (SessionTranscript)
    - Usage/Cost (DEFAULT_COSTS, resolve_cost_config, calculate_cost,
                  aggregate_usage, aggregate_cost)
    - Prompt Log (PromptLog)
    - Config Audit (hash_content, collect_changed_paths,
                    detect_suspicious_changes, ConfigAuditLog)
    - Diagnostic Events (subscribe, emit, emit_model_usage,
                         emit_message_processed, emit_tool_executed,
                         jsonl_file_listener, cloudwatch_listener)
    - Setup/Integration (ObservabilityContext, setup_observability)
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# =============================================================================
# 1. TYPES
# =============================================================================


class MessageRole(str, enum.Enum):
    """Role of a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class TokenUsage:
    """Token usage statistics for a single invocation."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CostBreakdown:
    """Cost breakdown for a single invocation."""

    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    model_id: str = ""
    provider: str = ""


@dataclass
class ModelCostConfig:
    """Per-model pricing configuration (per 1K tokens)."""

    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    model_id: str = ""


@dataclass
class ToolCallRecord:
    """Record of a tool invocation."""

    tool_name: str
    params: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    duration_ms: float = 0.0
    is_error: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class MessageRecord:
    """Record of a single message for transcript logging."""

    role: str
    content: str | None = None
    model: str | None = None
    provider: str | None = None
    usage: TokenUsage | None = None
    tool_calls: list[ToolCallRecord] | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ConfigAuditRecord:
    """Record of a configuration state or change."""

    path: str
    hash_before: str = ""
    hash_after: str = ""
    changed: bool = False
    suspicious: bool = False
    reason: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class DiagnosticEvent:
    """A diagnostic event for the event system."""

    event_type: str
    subsystem: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    severity: str = "info"


# =============================================================================
# 2. STRUCTURED LOGGER
# =============================================================================


class LogLevel(str, enum.Enum):
    """Supported log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data") and record.extra_data:
            log_entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }
        return json.dumps(log_entry, default=str)


def _is_aws_environment() -> bool:
    """Auto-detect if running in AWS (Lambda, ECS, EC2)."""
    return any(
        os.environ.get(v)
        for v in (
            "AWS_LAMBDA_FUNCTION_NAME",
            "ECS_CONTAINER_METADATA_URI",
            "AWS_EXECUTION_ENV",
        )
    )


def _local_file_handler(
    log_dir: str, subsystem: str
) -> logging.FileHandler:
    """Create a local file handler for structured logs."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    handler = logging.FileHandler(
        log_path / f"{subsystem}_{date_str}.jsonl",
        encoding="utf-8",
    )
    return handler


def setup_logging(
    subsystem: str = "agent",
    log_dir: str = ".agent/logs",
    log_level: str = "INFO",
    cloudwatch_log_group: str = "",
    cloudwatch_region: str = "",
) -> logging.Logger:
    """Set up structured logging with dual-destination support.

    Routes to CloudWatch when running in AWS with a configured log group,
    otherwise falls back to local JSONL files.

    Args:
        subsystem: Logger name / CloudWatch stream name.
        log_dir: Local directory for log files.
        log_level: Minimum log level.
        cloudwatch_log_group: CloudWatch log group name (empty = skip).
        cloudwatch_region: AWS region for CloudWatch.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(subsystem)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    handler: logging.Handler
    if _is_aws_environment() and cloudwatch_log_group:
        try:
            import watchtower  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {
                "log_group_name": cloudwatch_log_group,
                "stream_name": subsystem,
            }
            if cloudwatch_region:
                import boto3  # type: ignore[import-untyped]

                kwargs["boto3_client"] = boto3.client(
                    "logs", region_name=cloudwatch_region
                )
            handler = watchtower.CloudWatchLogHandler(**kwargs)
        except ImportError:
            handler = _local_file_handler(log_dir, subsystem)
    else:
        handler = _local_file_handler(log_dir, subsystem)

    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


def get_logger(subsystem: str = "agent") -> logging.Logger:
    """Get an existing logger by subsystem name.

    If the logger has no handlers, sets up a basic local logger.
    """
    logger = logging.getLogger(subsystem)
    if not logger.handlers:
        return setup_logging(subsystem)
    return logger


# =============================================================================
# 3. SESSION TRANSCRIPT
# =============================================================================


class SessionTranscript:
    """Append-only JSONL session transcript recorder.

    Creates a forensic-grade log of all messages in a session,
    stored as one JSON object per line.
    """

    def __init__(
        self,
        transcript_dir: str = ".agent/transcripts",
        session_id: str = "",
    ) -> None:
        self.transcript_dir = Path(transcript_dir)
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )
        self.transcript_path = self.transcript_dir / f"{self.session_id}.jsonl"
        self._write_header()

    def _write_header(self) -> None:
        """Write session header if file is new."""
        if self.transcript_path.exists() and self.transcript_path.stat().st_size > 0:
            return
        header = {
            "type": "session",
            "version": "1.0",
            "id": self.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.transcript_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(header, separators=(",", ":")) + "\\n")

    def append(self, record: MessageRecord) -> None:
        """Append a message record to the transcript."""
        entry: dict[str, Any] = {
            "type": "message",
            "role": record.role,
            "timestamp": record.timestamp,
        }
        if record.content is not None:
            entry["content"] = record.content
        if record.model:
            entry["model"] = record.model
        if record.provider:
            entry["provider"] = record.provider
        if record.usage:
            entry["usage"] = {
                "input": record.usage.input_tokens,
                "output": record.usage.output_tokens,
                "total": record.usage.total_tokens,
            }
        if record.tool_calls:
            entry["tool_calls"] = [
                {
                    "name": tc.tool_name,
                    "duration_ms": tc.duration_ms,
                    "is_error": tc.is_error,
                }
                for tc in record.tool_calls
            ]
        with open(self.transcript_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\\n")

    def load_messages(self) -> list[dict[str, Any]]:
        """Load all message entries from the transcript."""
        if not self.transcript_path.exists():
            return []
        messages: list[dict[str, Any]] = []
        with open(self.transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "message":
                        messages.append(entry)
                except json.JSONDecodeError:
                    continue
        return messages

    @property
    def message_count(self) -> int:
        """Number of messages in the transcript."""
        return len(self.load_messages())


# =============================================================================
# 4. USAGE / COST
# =============================================================================


DEFAULT_COSTS: dict[str, ModelCostConfig] = {
    "anthropic.claude-sonnet-4-20250514-v1:0": ModelCostConfig(
        input_cost_per_1k=0.003, output_cost_per_1k=0.015,
        model_id="anthropic.claude-sonnet-4-20250514-v1:0",
    ),
    "anthropic.claude-haiku-4-5-20251001-v1:0": ModelCostConfig(
        input_cost_per_1k=0.0008, output_cost_per_1k=0.004,
        model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
    ),
    "anthropic.claude-opus-4-20250514-v1:0": ModelCostConfig(
        input_cost_per_1k=0.015, output_cost_per_1k=0.075,
        model_id="anthropic.claude-opus-4-20250514-v1:0",
    ),
    "gpt-4o": ModelCostConfig(
        input_cost_per_1k=0.005, output_cost_per_1k=0.015,
        model_id="gpt-4o",
    ),
    "gpt-4o-mini": ModelCostConfig(
        input_cost_per_1k=0.00015, output_cost_per_1k=0.0006,
        model_id="gpt-4o-mini",
    ),
    "gemini-2.0-flash": ModelCostConfig(
        input_cost_per_1k=0.0001, output_cost_per_1k=0.0004,
        model_id="gemini-2.0-flash",
    ),
    "gemini-2.5-pro-preview-05-06": ModelCostConfig(
        input_cost_per_1k=0.00125, output_cost_per_1k=0.01,
        model_id="gemini-2.5-pro-preview-05-06",
    ),
}


def resolve_cost_config(
    model_id: str,
    custom_costs: dict[str, ModelCostConfig] | None = None,
) -> ModelCostConfig:
    """Resolve cost configuration for a model.

    Checks custom costs first, then falls back to DEFAULT_COSTS.
    Returns a zero-cost config if the model is unknown.
    """
    if custom_costs and model_id in custom_costs:
        return custom_costs[model_id]
    return DEFAULT_COSTS.get(
        model_id, ModelCostConfig(model_id=model_id)
    )


def calculate_cost(
    usage: TokenUsage, model_id: str,
    custom_costs: dict[str, ModelCostConfig] | None = None,
) -> CostBreakdown:
    """Calculate cost for a single invocation.

    Args:
        usage: Token usage from the invocation.
        model_id: The model identifier.
        custom_costs: Optional custom pricing overrides.

    Returns:
        CostBreakdown with input/output/total costs.
    """
    cost_cfg = resolve_cost_config(model_id, custom_costs)
    input_cost = (usage.input_tokens / 1000.0) * cost_cfg.input_cost_per_1k
    output_cost = (usage.output_tokens / 1000.0) * cost_cfg.output_cost_per_1k
    return CostBreakdown(
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=input_cost + output_cost,
        model_id=model_id,
    )


def aggregate_usage(usages: list[TokenUsage]) -> TokenUsage:
    """Aggregate multiple TokenUsage records into one."""
    return TokenUsage(
        input_tokens=sum(u.input_tokens for u in usages),
        output_tokens=sum(u.output_tokens for u in usages),
        total_tokens=sum(u.total_tokens for u in usages),
    )


def aggregate_cost(breakdowns: list[CostBreakdown]) -> CostBreakdown:
    """Aggregate multiple CostBreakdown records into one."""
    return CostBreakdown(
        input_cost=sum(b.input_cost for b in breakdowns),
        output_cost=sum(b.output_cost for b in breakdowns),
        total_cost=sum(b.total_cost for b in breakdowns),
    )


# =============================================================================
# 5. PROMPT LOG
# =============================================================================


class PromptLog:
    """Per-invocation prompt snapshot logger.

    Captures the exact system prompt used for each invocation,
    enabling forensic replay and prompt drift detection.
    """

    def __init__(self, log_dir: str = ".agent/logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "prompts.jsonl"

    def log_prompt(
        self,
        prompt_text: str,
        model_id: str = "",
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a prompt snapshot."""
        entry = {
            "type": "prompt",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_hash": hashlib.sha256(
                prompt_text.encode()
            ).hexdigest()[:16],
            "prompt_length": len(prompt_text),
            "prompt_text": prompt_text,
            "model_id": model_id,
            "session_id": session_id,
        }
        if metadata:
            entry["metadata"] = metadata
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\\n")

    def load_prompts(self) -> list[dict[str, Any]]:
        """Load all prompt entries."""
        if not self.log_path.exists():
            return []
        prompts: list[dict[str, Any]] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    prompts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return prompts


# =============================================================================
# 6. CONFIG AUDIT
# =============================================================================


def hash_content(content: str) -> str:
    """Create a SHA-256 hash of content (first 16 hex chars)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def collect_changed_paths(
    before: dict[str, str], after: dict[str, str]
) -> list[ConfigAuditRecord]:
    """Compare before/after config hashes and identify changes.

    Args:
        before: Dict of path -> content hash before.
        after: Dict of path -> content hash after.

    Returns:
        List of ConfigAuditRecord for changed paths.
    """
    records: list[ConfigAuditRecord] = []
    all_paths = set(before.keys()) | set(after.keys())
    for path in sorted(all_paths):
        h_before = before.get(path, "")
        h_after = after.get(path, "")
        if h_before != h_after:
            records.append(
                ConfigAuditRecord(
                    path=path,
                    hash_before=h_before,
                    hash_after=h_after,
                    changed=True,
                )
            )
    return records


def detect_suspicious_changes(
    records: list[ConfigAuditRecord],
    sensitive_patterns: list[str] | None = None,
) -> list[ConfigAuditRecord]:
    """Flag suspicious config changes based on sensitive patterns.

    Args:
        records: List of change records to check.
        sensitive_patterns: File path patterns considered sensitive
            (defaults to common config files).

    Returns:
        Records with suspicious=True for flagged changes.
    """
    if sensitive_patterns is None:
        sensitive_patterns = [
            "config.yaml", ".env", "credentials",
            "secret", "key", "token", "auth",
        ]
    for record in records:
        for pattern in sensitive_patterns:
            if pattern.lower() in record.path.lower():
                record.suspicious = True
                record.reason = f"Sensitive pattern matched: {pattern}"
                break
    return records


class ConfigAuditLog:
    """Configuration audit logger.

    Tracks config file states and detects changes between snapshots.
    """

    def __init__(self, log_dir: str = ".agent/logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "config_audit.jsonl"

    def snapshot(
        self, config_paths: list[str],
    ) -> dict[str, str]:
        """Take a hash snapshot of the given config files.

        Args:
            config_paths: List of file paths to hash.

        Returns:
            Dict of path -> content hash.
        """
        hashes: dict[str, str] = {}
        for path in config_paths:
            p = Path(path)
            if p.exists():
                hashes[path] = hash_content(p.read_text())
            else:
                hashes[path] = ""
        return hashes

    def log_audit(
        self, records: list[ConfigAuditRecord],
    ) -> None:
        """Write audit records to the log."""
        for record in records:
            entry = {
                "type": "config_audit",
                "path": record.path,
                "hash_before": record.hash_before,
                "hash_after": record.hash_after,
                "changed": record.changed,
                "suspicious": record.suspicious,
                "reason": record.reason,
                "timestamp": record.timestamp,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\\n")

    def check_and_log(
        self,
        before: dict[str, str],
        after: dict[str, str],
    ) -> list[ConfigAuditRecord]:
        """Compare snapshots, detect suspicious changes, and log."""
        changed = collect_changed_paths(before, after)
        flagged = detect_suspicious_changes(changed)
        if flagged:
            self.log_audit(flagged)
        return flagged


# =============================================================================
# 7. DIAGNOSTIC EVENTS
# =============================================================================

# Global subscriber registry
_subscribers: dict[str, list[Callable[[DiagnosticEvent], None]]] = {}


def subscribe(
    event_type: str,
    listener: Callable[[DiagnosticEvent], None],
) -> None:
    """Subscribe a listener to a diagnostic event type.

    Args:
        event_type: Event type to listen for (or "*" for all events).
        listener: Callable that receives a DiagnosticEvent.
    """
    if event_type not in _subscribers:
        _subscribers[event_type] = []
    _subscribers[event_type].append(listener)


def emit(event: DiagnosticEvent) -> None:
    """Emit a diagnostic event to all subscribers.

    Notifies type-specific subscribers and wildcard ("*") subscribers.
    """
    for listener in _subscribers.get(event.event_type, []):
        try:
            listener(event)
        except Exception:
            pass  # Never let listener errors break the pipeline

    for listener in _subscribers.get("*", []):
        try:
            listener(event)
        except Exception:
            pass


def emit_model_usage(
    model_id: str,
    provider: str,
    usage: TokenUsage,
    duration_ms: float = 0.0,
) -> None:
    """Emit a model usage diagnostic event."""
    emit(
        DiagnosticEvent(
            event_type="model_usage",
            subsystem="llm",
            data={
                "model_id": model_id,
                "provider": provider,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "duration_ms": duration_ms,
            },
        )
    )


def emit_message_processed(
    role: str, content_length: int, model: str = "",
) -> None:
    """Emit a message processed diagnostic event."""
    emit(
        DiagnosticEvent(
            event_type="message_processed",
            subsystem="agent",
            data={
                "role": role,
                "content_length": content_length,
                "model": model,
            },
        )
    )


def emit_tool_executed(
    tool_name: str,
    duration_ms: float,
    is_error: bool = False,
) -> None:
    """Emit a tool execution diagnostic event."""
    emit(
        DiagnosticEvent(
            event_type="tool_executed",
            subsystem="tools",
            data={
                "tool_name": tool_name,
                "duration_ms": duration_ms,
                "is_error": is_error,
            },
        )
    )


def jsonl_file_listener(
    log_dir: str = ".agent/logs",
) -> Callable[[DiagnosticEvent], None]:
    """Create a JSONL file listener for diagnostic events.

    Returns:
        A listener function that writes events to a JSONL file.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    event_file = log_path / "events.jsonl"

    def _listener(event: DiagnosticEvent) -> None:
        entry = {
            "event_type": event.event_type,
            "subsystem": event.subsystem,
            "data": event.data,
            "timestamp": event.timestamp,
            "severity": event.severity,
        }
        with open(event_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\\n")

    return _listener


def cloudwatch_listener(
    log_group: str,
    stream_name: str = "diagnostics",
    region: str = "",
) -> Callable[[DiagnosticEvent], None]:
    """Create a CloudWatch listener for diagnostic events.

    Returns:
        A listener function that sends events to CloudWatch.
    """

    def _listener(event: DiagnosticEvent) -> None:
        try:
            import boto3  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {"region_name": region} if region else {}
            client = boto3.client("logs", **kwargs)
            client.put_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                logEvents=[
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": json.dumps(
                            {
                                "event_type": event.event_type,
                                "subsystem": event.subsystem,
                                "data": event.data,
                                "severity": event.severity,
                            }
                        ),
                    }
                ],
            )
        except Exception:
            pass  # Graceful degradation — never break the pipeline

    return _listener


# =============================================================================
# 8. SETUP / INTEGRATION
# =============================================================================


@dataclass
class ObservabilityContext:
    """Holds initialised observability components."""

    logger: logging.Logger
    transcript: SessionTranscript | None = None
    prompt_log: PromptLog | None = None
    config_audit: ConfigAuditLog | None = None
    log_dir: str = ".agent/logs"
    transcript_dir: str = ".agent/transcripts"


def setup_observability(
    subsystem: str = "agent",
    log_dir: str = ".agent/logs",
    transcript_dir: str = ".agent/transcripts",
    log_level: str = "INFO",
    cloudwatch_log_group: str = "",
    cloudwatch_region: str = "",
    enable_transcripts: bool = True,
    enable_cost_tracking: bool = True,
    enable_config_audit: bool = True,
    enable_prompt_log: bool = True,
    enable_diagnostics: bool = True,
) -> ObservabilityContext:
    """One-call setup for all observability components.

    Reads configuration and initialises the logger, transcript,
    prompt log, config audit, and diagnostic event system.

    Args:
        subsystem: Logger name / CloudWatch stream name.
        log_dir: Local directory for log files.
        transcript_dir: Directory for session transcripts.
        log_level: Minimum log level.
        cloudwatch_log_group: CloudWatch log group (empty = local only).
        cloudwatch_region: AWS region for CloudWatch.
        enable_transcripts: Enable session transcript recording.
        enable_cost_tracking: Enable cost tracking (reserved).
        enable_config_audit: Enable config audit logging.
        enable_prompt_log: Enable prompt snapshot logging.
        enable_diagnostics: Enable diagnostic event system.

    Returns:
        ObservabilityContext with all initialised components.
    """
    obs_logger = setup_logging(
        subsystem=subsystem,
        log_dir=log_dir,
        log_level=log_level,
        cloudwatch_log_group=cloudwatch_log_group,
        cloudwatch_region=cloudwatch_region,
    )

    transcript = None
    if enable_transcripts:
        transcript = SessionTranscript(transcript_dir=transcript_dir)

    prompt_log = None
    if enable_prompt_log:
        prompt_log = PromptLog(log_dir=log_dir)

    config_audit = None
    if enable_config_audit:
        config_audit = ConfigAuditLog(log_dir=log_dir)

    if enable_diagnostics:
        file_listener = jsonl_file_listener(log_dir=log_dir)
        subscribe("*", file_listener)

        if _is_aws_environment() and cloudwatch_log_group:
            cw_listener = cloudwatch_listener(
                log_group=cloudwatch_log_group,
                region=cloudwatch_region,
            )
            subscribe("*", cw_listener)

    return ObservabilityContext(
        logger=obs_logger,
        transcript=transcript,
        prompt_log=prompt_log,
        config_audit=config_audit,
        log_dir=log_dir,
        transcript_dir=transcript_dir,
    )
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
  profile: "{self.config.tool_governance.profile}"
  deny: {self._render_deny_list()}
  sub_agent_restrictions: {str(self.config.tool_governance.sub_agent_restrictions).lower()}
  # Per-provider overrides (most-specific-wins):
  # byProvider:
  #   anthropic/claude-sonnet-4:
  #     alsoAllow: ["group:web"]
  #   openai:
  #     deny: ["shell_exec"]

operational:
  max_iterations: 10
  timeout_seconds: 120
  log_level: "INFO"
{self._render_langsmith_config_yaml()}{self._render_session_config_yaml()}{self._render_identity_config_yaml()}{self._render_skills_config_yaml()}{self._render_tools_config_yaml()}{self._render_observability_config_yaml()}"""

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

        if self.config.langsmith.enabled:
            deps.append('    "langsmith>=0.1.0"')

        if self.config.observability.enabled:
            deps.append('    "watchtower>=3.0.0"')

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
    tool_policy.py           # Tool governance — layered permissions (Principle 9)
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

## Tool Governance (Principle 9)

This project includes a tool policy module (`tool_policy.py`) that provides:

- **Tool profiles** — minimal, coding, or full access levels
- **Deny-wins-over-allow** — denied tools are always blocked, regardless of profile
- **Tool group selectors** — `group:fs`, `group:runtime`, etc. expand to concrete tools
- **Sub-agent restrictions** — hardcoded deny list prevents sub-agents from accessing orchestration tools

Configure tool access in `config.yaml` under the `tools` section.
{self._render_readme_langsmith()}{self._render_readme_session_persistence()}{self._render_readme_skills()}{self._render_readme_tools()}{self._render_readme_observability()}
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
- **tools.deny** — Explicit deny list (always wins over allow)
- **tools.sub_agent_restrictions** — Enable sub-agent tool restrictions
- **operational.max_iterations** — Tool loop iteration limit{self._render_readme_langsmith_config_line()}{self._render_readme_session_config_line()}{self._render_readme_skills_config_line()}{self._render_readme_tools_config_line()}{self._render_readme_observability_config_line()}
"""

    def render_makefile(self) -> str:
        sessions_target = " sessions.py" if self.config.sessions.enabled else ""
        capabilities_target = " capabilities.py" if self.config.skills.enabled else ""
        tools_target = " tools/" if self.config.tools.enabled else ""
        observability_target = " observability.py" if self.config.observability.enabled else ""
        return f"""\
.PHONY: lint format typecheck test run clean

lint:
\truff check .

format:
\tblack .
\tisort .

typecheck:
\tmypy agent.py resilience.py tool_policy.py{sessions_target}{capabilities_target}{tools_target}{observability_target}

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

        if self.config.langsmith.enabled:
            lines.extend([
                "# LangSmith Tracing (Principle 16)",
                "# LANGCHAIN_TRACING_V2 is set automatically by the --dev flag",
                "LANGCHAIN_API_KEY=lsv2_...",
                f"LANGCHAIN_PROJECT={self.config.langsmith.project}",
                "# LANGCHAIN_ENDPOINT=https://api.smith.langchain.com",
                "",
            ])

        if self.config.observability.enabled:
            lines.extend([
                "# Operational Observability (Principle 17)",
                "# CloudWatch destination (auto-detected in AWS, ignored locally)",
                "CLOUDWATCH_LOG_GROUP=",
                "CLOUDWATCH_REGION=",
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


TOOL_POLICY_FILE = Path(__file__).parent.parent / "tool_policy.py"


class TestToolPolicySyntax:
    \"\"\"Verify generated tool_policy.py is syntactically valid Python.\"\"\"

    def test_tool_policy_file_exists(self):
        assert TOOL_POLICY_FILE.exists(), f"tool_policy.py not found at {{TOOL_POLICY_FILE}}"

    def test_tool_policy_parses(self):
        \"\"\"Ensure tool_policy.py is valid Python syntax.\"\"\"
        source = TOOL_POLICY_FILE.read_text()
        ast.parse(source)

    def test_tool_policy_has_key_functions(self):
        \"\"\"Verify tool_policy.py contains all required functions.\"\"\"
        source = TOOL_POLICY_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in ["expand_groups", "matches_policy", "filter_tools", "validate_tool_config"]:
            assert expected in func_names, f"{{expected}} function not found in tool_policy.py"


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
{self._render_test_tracing()}{self._render_test_sessions()}{self._render_test_skills()}{self._render_test_tools()}{self._render_test_observability()}{self._render_test_identity()}"""

    # ------------------------------------------------------------------
    # sessions.py — Session Persistence (Principle 11)
    # ------------------------------------------------------------------

    def render_sessions_py(self) -> str:
        """Render the complete sessions.py for the generated project.

        Implements Principle 11: Session Persistence — consolidates
        8 blueprint modules into a single file:
        1. Data Types, 2. Session Key, 3. Transcript, 4. Lock,
        5. Session Store, 6. Sanitise, 7. Repair, 8. Compact, 9. Config.
        """
        return '''\
"""Session Persistence — append-only, durable, provider-sanitised conversation state.

Principle 11: Session Persistence — provides:
- Append-only JSONL transcript storage
- Session key routing context encoding
- File-based session write locking
- Provider-specific history sanitisation (Google, Anthropic, OpenAI)
- JSONL file repair (drop bad lines, atomic rewrite)
- Session compaction (LLM-powered summarisation)
- Session store lifecycle management (prune, cap, rotate)
- Configuration loading from config.yaml

Sections:
    - Data Types (MessageRole, ToolCall, ToolResult, TokenUsage, Message, SessionEntry, SessionHeader)
    - Session Key (normalize_agent_id, build_session_key, parse_session_key, is_subagent_key)
    - Transcript (ensure_session_header, append_message, load_transcript)
    - Lock (session_write_lock)
    - Session Store (SessionStore)
    - Sanitise (ensure_alternating_turns, repair_orphaned_tool_calls, sanitise_for_provider)
    - Repair (RepairResult, repair_session_file)
    - Compact (CompactionResult, compact_session)
    - Config (load_session_config)
"""

from __future__ import annotations

import atexit
import glob
import json
import logging
import os
import re
import shutil
import signal
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generator

logger = logging.getLogger(__name__)


# =============================================================================
# 1. DATA TYPES
# =============================================================================


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class ToolCall:
    """A tool invocation request from the assistant."""

    id: str
    name: str
    params: dict[str, Any]


@dataclass
class ToolResult:
    """The result of a tool invocation."""

    tool_call_id: str
    name: str
    result: str
    is_error: bool = False


@dataclass
class TokenUsage:
    """Token usage statistics for a message."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Message:
    """A single message in a conversation."""

    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_result: ToolResult | None = None
    model: str | None = None
    provider: str | None = None
    usage: TokenUsage | None = None
    stop_reason: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )


@dataclass
class SessionEntry:
    """Metadata for a single session in the session store."""

    session_id: str
    session_file: str
    updated_at: float  # epoch ms
    channel: str | None = None
    chat_type: str | None = None
    group_id: str | None = None
    spawned_by: str | None = None
    compaction_count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None
    provider: str | None = None
    delivery_context: dict[str, Any] | None = None

    @staticmethod
    def new(session_key: str, sessions_dir: str) -> SessionEntry:
        """Create a new session entry with a generated ID."""
        sid = uuid.uuid4().hex[:12]
        return SessionEntry(
            session_id=sid,
            session_file=f"{sessions_dir}/{sid}.jsonl",
            updated_at=datetime.utcnow().timestamp() * 1000,
        )


@dataclass
class SessionHeader:
    """Header line for a JSONL transcript file."""

    type: str = "session"
    version: str = "1.0"
    id: str = ""
    timestamp: str = ""
    cwd: str | None = None


# =============================================================================
# 2. SESSION KEY
# =============================================================================

_VALID_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def normalize_agent_id(agent_id: str) -> str:
    """Lowercase, collapse invalid chars to dashes."""
    normalized = agent_id.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    return normalized.strip("-")[:64]


def build_session_key(
    agent_id: str,
    scope: str = "main",
    channel: str | None = None,
    user_id: str | None = None,
    thread_id: str | None = None,
) -> str:
    """Build a session key encoding routing context.

    Format: agent:{agentId}:{scope}:{channel}:{userId}:{threadId}
    """
    parts = ["agent", normalize_agent_id(agent_id), scope]
    if channel:
        parts.append(channel)
    if user_id:
        parts.append(user_id)
    if thread_id:
        parts.append(thread_id)
    return ":".join(parts)


def parse_session_key(key: str) -> dict[str, str | None]:
    """Extract components from a session key."""
    parts = key.split(":")
    return {
        "prefix": parts[0] if len(parts) > 0 else None,
        "agent_id": parts[1] if len(parts) > 1 else None,
        "scope": parts[2] if len(parts) > 2 else None,
        "channel": parts[3] if len(parts) > 3 else None,
        "user_id": parts[4] if len(parts) > 4 else None,
        "thread_id": parts[5] if len(parts) > 5 else None,
    }


def is_subagent_key(key: str) -> bool:
    """Detect sub-agent sessions by checking scope."""
    parsed = parse_session_key(key)
    return parsed.get("scope") not in ("main", None)


# =============================================================================
# 3. TRANSCRIPT
# =============================================================================


def _serialize_message(msg: Message) -> dict[str, Any]:
    """Convert a Message to a JSON-serializable dict."""
    d: dict[str, Any] = {"role": msg.role.value}
    if msg.content is not None:
        d["content"] = msg.content
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "name": tc.name, "params": tc.params}
            for tc in msg.tool_calls
        ]
    if msg.tool_result:
        d["tool_result"] = {
            "tool_call_id": msg.tool_result.tool_call_id,
            "name": msg.tool_result.name,
            "result": msg.tool_result.result,
            "is_error": msg.tool_result.is_error,
        }
    if msg.model:
        d["model"] = msg.model
    if msg.provider:
        d["provider"] = msg.provider
    if msg.usage:
        d["usage"] = {
            "input": msg.usage.input_tokens,
            "output": msg.usage.output_tokens,
            "total": msg.usage.total_tokens,
        }
    if msg.stop_reason:
        d["stop_reason"] = msg.stop_reason
    d["timestamp"] = msg.timestamp
    return d


def ensure_session_header(
    path: str, session_id: str, cwd: str | None = None
) -> None:
    """Create the JSONL file with a session header if it doesn\'t exist."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    header: dict[str, Any] = {
        "type": "session",
        "version": "1.0",
        "id": session_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if cwd:
        header["cwd"] = cwd
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(header, separators=(",", ":")) + "\\n")


def append_message(path: str, message: Message) -> None:
    """Append a single message to the JSONL transcript.

    This is the ONLY write operation on a transcript file.
    Never rewrite or modify existing lines.
    """
    line = {
        "type": "message",
        "message": _serialize_message(message),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, separators=(",", ":")) + "\\n")


def load_transcript(path: str) -> tuple[SessionHeader | None, list[Message]]:
    """Load a complete transcript from a JSONL file.

    Returns the session header (if present) and all messages.
    Malformed lines are skipped with a warning.
    """
    header: SessionHeader | None = None
    messages: list[Message] = []

    if not os.path.exists(path):
        return header, messages

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "session" and header is None:
                header = SessionHeader(
                    type=data.get("type", "session"),
                    version=data.get("version", "1.0"),
                    id=data.get("id", ""),
                    timestamp=data.get("timestamp", ""),
                    cwd=data.get("cwd"),
                )
            elif data.get("type") == "message":
                msg_data = data.get("message", {})
                msg = Message(
                    role=MessageRole(msg_data.get("role", "user")),
                    content=msg_data.get("content"),
                    timestamp=msg_data.get("timestamp", ""),
                    model=msg_data.get("model"),
                    provider=msg_data.get("provider"),
                    stop_reason=msg_data.get("stop_reason"),
                )
                messages.append(msg)

    return header, messages


# =============================================================================
# 4. LOCK
# =============================================================================

_HELD_LOCKS: dict[str, int] = {}  # path -> reentrant count

LOCK_TIMEOUT_S = 10.0
STALE_THRESHOLD_S = 1800  # 30 minutes


def _lock_path(session_file: str) -> str:
    return session_file + ".lock"


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _is_lock_stale(lock_path_str: str, stale_threshold_s: float) -> bool:
    """Check if a lock file is stale (dead process or too old)."""
    try:
        with open(lock_path_str, "r") as f:
            data = json.loads(f.read())
        pid = data.get("pid", -1)
        created_at = data.get("created_at", "")
        if not _is_process_alive(pid):
            return True
        lock_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age = (datetime.now(lock_time.tzinfo) - lock_time).total_seconds()
        return age > stale_threshold_s
    except (json.JSONDecodeError, OSError, ValueError):
        return True


def _remove_stale_lock(lock_path_str: str) -> None:
    try:
        os.unlink(lock_path_str)
    except OSError:
        pass


@contextmanager
def session_write_lock(
    session_file: str,
    timeout_s: float = LOCK_TIMEOUT_S,
    stale_threshold_s: float = STALE_THRESHOLD_S,
) -> Generator[None, None, None]:
    """Context manager for acquiring a session write lock.

    Usage:
        with session_write_lock("/path/to/session.jsonl"):
            append_message(...)
    """
    lp = _lock_path(session_file)

    # Reentrant: if we already hold this lock, just increment
    if lp in _HELD_LOCKS:
        _HELD_LOCKS[lp] += 1
        try:
            yield
        finally:
            _HELD_LOCKS[lp] -= 1
            if _HELD_LOCKS[lp] <= 0:
                del _HELD_LOCKS[lp]
        return

    # Acquire with exponential backoff
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            lock_data = json.dumps({
                "pid": os.getpid(),
                "created_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
            })
            os.write(fd, lock_data.encode())
            os.close(fd)
            break
        except FileExistsError:
            if _is_lock_stale(lp, stale_threshold_s):
                _remove_stale_lock(lp)
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Could not acquire session lock for {session_file} "
                    f"within {timeout_s}s"
                )
            attempt += 1
            time.sleep(min(1.0, 0.05 * attempt))

    _HELD_LOCKS[lp] = 1
    try:
        yield
    finally:
        _HELD_LOCKS.pop(lp, None)
        try:
            os.unlink(lp)
        except OSError:
            pass


def _cleanup_all_locks(*_args: Any) -> None:
    """Release all held locks on process exit."""
    for lp in list(_HELD_LOCKS.keys()):
        try:
            os.unlink(lp)
        except OSError:
            pass
    _HELD_LOCKS.clear()


atexit.register(_cleanup_all_locks)
for _sig in (signal.SIGINT, signal.SIGTERM):
    try:
        signal.signal(_sig, lambda s, f: (_cleanup_all_locks(), exit(1)))
    except (OSError, ValueError):
        pass


# =============================================================================
# 5. SESSION STORE
# =============================================================================


class SessionStore:
    """Session store management.

    Maps session keys to SessionEntry metadata in a JSON index file.
    The actual conversation data lives in per-session JSONL files.
    """

    def __init__(self, store_path: str) -> None:
        self.store_path = store_path
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.store_path):
            with open(self.store_path, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        else:
            self._entries = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        tmp = self.store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)
        os.replace(tmp, self.store_path)

    def get(self, session_key: str) -> SessionEntry | None:
        """Get a session entry by key."""
        data = self._entries.get(session_key)
        if data is None:
            return None
        return SessionEntry(
            session_id=data["session_id"],
            session_file=data["session_file"],
            updated_at=data.get("updated_at", 0),
            channel=data.get("channel"),
            chat_type=data.get("chat_type"),
            group_id=data.get("group_id"),
            spawned_by=data.get("spawned_by"),
            compaction_count=data.get("compaction_count", 0),
            total_tokens=data.get("total_tokens", 0),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            model=data.get("model"),
            provider=data.get("provider"),
            delivery_context=data.get("delivery_context"),
        )

    def upsert(self, session_key: str, entry: SessionEntry) -> None:
        """Insert or update a session entry."""
        from dataclasses import asdict

        self._entries[session_key] = asdict(entry)
        self._save()

    def delete(self, session_key: str) -> bool:
        """Delete a session entry. Returns True if found."""
        if session_key in self._entries:
            del self._entries[session_key]
            self._save()
            return True
        return False

    def keys(self) -> list[str]:
        """Return all session keys."""
        return list(self._entries.keys())

    def count(self) -> int:
        """Return the number of session entries."""
        return len(self._entries)

    # -- Lifecycle Management --

    def prune_stale(
        self,
        max_age: timedelta = timedelta(days=30),
        protect_keys: set[str] | None = None,
    ) -> int:
        """Remove entries older than max_age. Returns count removed."""
        cutoff = (datetime.utcnow() - max_age).timestamp() * 1000
        protect = protect_keys or set()
        to_remove = [
            k
            for k, v in self._entries.items()
            if k not in protect
            and v.get("updated_at", 0) > 0
            and v["updated_at"] < cutoff
        ]
        for k in to_remove:
            del self._entries[k]
        if to_remove:
            self._save()
        return len(to_remove)

    def cap_entries(
        self,
        max_entries: int = 500,
        protect_keys: set[str] | None = None,
    ) -> int:
        """Keep only the N most recent entries. Returns count removed."""
        if len(self._entries) <= max_entries:
            return 0
        protect = protect_keys or set()
        sorted_keys = sorted(
            self._entries.keys(),
            key=lambda k: self._entries[k].get("updated_at", 0),
            reverse=True,
        )
        keep = set(sorted_keys[:max_entries]) | protect
        to_remove = [k for k in self._entries if k not in keep]
        for k in to_remove:
            del self._entries[k]
        if to_remove:
            self._save()
        return len(to_remove)

    def rotate_if_needed(
        self,
        max_bytes: int = 10 * 1024 * 1024,
        max_backups: int = 3,
    ) -> bool:
        """Rotate sessions.json if it exceeds max_bytes."""
        if not os.path.exists(self.store_path):
            return False
        if os.path.getsize(self.store_path) < max_bytes:
            return False
        backup = f"{self.store_path}.bak.{int(time.time())}"
        shutil.copy2(self.store_path, backup)
        backups = sorted(glob.glob(f"{self.store_path}.bak.*"))
        for old in backups[:-max_backups]:
            os.unlink(old)
        return True


# =============================================================================
# 6. SANITISE
# =============================================================================


def ensure_alternating_turns(messages: list[Message]) -> list[Message]:
    """Enforce strict user/assistant turn alternation.

    When consecutive messages share the same role, insert a
    minimal placeholder from the other role.
    """
    if not messages:
        return messages

    result: list[Message] = [messages[0]]
    for msg in messages[1:]:
        prev = result[-1]
        if msg.role == prev.role and msg.role in (
            MessageRole.USER,
            MessageRole.ASSISTANT,
        ):
            placeholder_role = (
                MessageRole.ASSISTANT
                if msg.role == MessageRole.USER
                else MessageRole.USER
            )
            result.append(
                Message(role=placeholder_role, content="(continued)")
            )
        result.append(msg)
    return result


def repair_orphaned_tool_calls(messages: list[Message]) -> list[Message]:
    """Ensure every tool_call has a matching tool result.

    - Drop tool_calls with no input/arguments
    - Create synthetic error results for orphaned tool calls
    - Drop duplicate tool results
    - Drop free-floating tool results with no matching call
    """
    call_ids: set[str] = set()
    for msg in messages:
        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.id and tc.name:
                    call_ids.add(tc.id)

    result_ids: set[str] = set()
    for msg in messages:
        if msg.tool_result:
            result_ids.add(msg.tool_result.tool_call_id)

    repaired: list[Message] = []
    seen_results: set[str] = set()

    for msg in messages:
        if msg.tool_calls:
            valid_calls = [
                tc
                for tc in msg.tool_calls
                if tc.id and tc.name and tc.params is not None
            ]
            if not valid_calls and not msg.content:
                continue
            msg.tool_calls = valid_calls or None

        if msg.tool_result:
            tcid = msg.tool_result.tool_call_id
            if tcid not in call_ids:
                continue
            if tcid in seen_results:
                continue
            seen_results.add(tcid)

        repaired.append(msg)

    missing = call_ids - result_ids
    for msg in repaired:
        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.id in missing:
                    repaired.append(
                        Message(
                            role=MessageRole.TOOL,
                            tool_result=ToolResult(
                                tool_call_id=tc.id,
                                name=tc.name,
                                result="Error: tool execution was interrupted",
                                is_error=True,
                            ),
                        )
                    )

    return repaired


def sanitise_for_provider(
    messages: list[Message],
    provider: str,
) -> list[Message]:
    """Apply provider-specific sanitisation to a message list."""
    messages = repair_orphaned_tool_calls(messages)

    if provider in ("google", "gemini"):
        return _sanitise_google(messages)
    elif provider in ("anthropic",):
        return _sanitise_anthropic(messages)
    elif provider in ("openai",):
        return _sanitise_openai(messages)
    else:
        return ensure_alternating_turns(messages)


def _sanitise_google(messages: list[Message]) -> list[Message]:
    """Google/Gemini: strict alternation, no thinking blocks."""
    messages = ensure_alternating_turns(messages)
    for msg in messages:
        if msg.content and "<think>" in msg.content:
            msg.content = re.sub(
                r"<think>.*?</think>", "", msg.content, flags=re.DOTALL
            ).strip()
    return messages


def _sanitise_anthropic(messages: list[Message]) -> list[Message]:
    """Anthropic: alternation enforced."""
    return ensure_alternating_turns(messages)


def _sanitise_openai(messages: list[Message]) -> list[Message]:
    """OpenAI: enforce basic ordering."""
    return ensure_alternating_turns(messages)


# =============================================================================
# 7. REPAIR
# =============================================================================


@dataclass
class RepairResult:
    """Result of a session file repair operation."""

    repaired: bool
    dropped_lines: int
    backup_path: str | None
    reason: str | None


def repair_session_file(path: str) -> RepairResult:
    """Repair a potentially corrupted JSONL session file.

    - Reads line by line, drops unparseable JSON
    - Creates a backup before rewriting
    - Atomically replaces the original
    """
    if not os.path.exists(path):
        return RepairResult(False, 0, None, "file not found")

    valid_lines: list[str] = []
    dropped = 0

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.rstrip("\\n")
            if not raw_line.strip():
                continue
            try:
                json.loads(raw_line)
                valid_lines.append(raw_line)
            except json.JSONDecodeError:
                dropped += 1

    if dropped == 0:
        return RepairResult(False, 0, None, None)

    backup = f"{path}.bak-{os.getpid()}-{int(time.time())}"
    shutil.copy2(path, backup)

    tmp = path + f".tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        for line in valid_lines:
            f.write(line + "\\n")
    os.replace(tmp, path)

    return RepairResult(
        repaired=True,
        dropped_lines=dropped,
        backup_path=backup,
        reason=f"dropped {dropped} malformed lines",
    )


# =============================================================================
# 8. COMPACT
# =============================================================================


@dataclass
class CompactionResult:
    """Result of a session compaction operation."""

    summary: str
    messages_before: int
    messages_after: int
    tokens_before: int
    tokens_after: int


def compact_session(
    session_file: str,
    summarise_fn: Callable[[list[Message]], str],
    keep_recent: int = 10,
    estimate_tokens_fn: Callable[[list[Message]], int] | None = None,
) -> CompactionResult:
    """Compact a session by summarising older messages.

    Args:
        session_file: Path to the JSONL transcript.
        summarise_fn: Callable that takes messages and returns a summary.
        keep_recent: Number of recent messages to preserve.
        estimate_tokens_fn: Optional token estimator.

    Returns:
        CompactionResult with before/after metrics.
    """
    with session_write_lock(session_file):
        repair_session_file(session_file)

        header, messages = load_transcript(session_file)
        if not messages:
            return CompactionResult("", 0, 0, 0, 0)

        messages_before = len(messages)
        tokens_before = (
            estimate_tokens_fn(messages)
            if estimate_tokens_fn
            else messages_before * 100
        )

        if messages_before <= keep_recent:
            return CompactionResult(
                "", messages_before, messages_before,
                tokens_before, tokens_before,
            )

        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        summary_text = summarise_fn(old_messages)

        compacted: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                content=f"[Compacted conversation summary]\\n\\n{summary_text}",
            ),
            *recent_messages,
        ]

        messages_after = len(compacted)
        tokens_after = (
            estimate_tokens_fn(compacted)
            if estimate_tokens_fn
            else messages_after * 100
        )

        tmp = session_file + f".tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            if header:
                f.write(json.dumps({
                    "type": header.type,
                    "version": header.version,
                    "id": header.id,
                    "timestamp": header.timestamp,
                    "cwd": header.cwd,
                    "compacted_at": datetime.utcnow().isoformat() + "Z",
                }, separators=(",", ":")) + "\\n")
            for msg in compacted:
                line = {
                    "type": "message",
                    "message": _serialize_message(msg),
                }
                f.write(json.dumps(line, separators=(",", ":")) + "\\n")
        os.replace(tmp, session_file)

        return CompactionResult(
            summary=summary_text,
            messages_before=messages_before,
            messages_after=messages_after,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )


# =============================================================================
# 9. CONFIG LOADER
# =============================================================================


def load_session_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load session configuration from config.yaml.

    Returns the \'sessions\' section of the config, or defaults.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    if not config_path.exists():
        return {}

    import yaml

    with open(config_path) as f:
        full_config = yaml.safe_load(f) or {}

    return full_config.get("sessions", {})
'''

    def _render_session_config_yaml(self) -> str:
        """Render the sessions section of config.yaml, or empty string."""
        if not self.config.sessions.enabled:
            return ""
        return f"""
sessions:
  enabled: true
  storage_dir: "{self.config.sessions.storage_dir}"
  history_limit: {self.config.sessions.history_limit}
  compaction_threshold: {self.config.sessions.compaction_threshold}
  maintenance:
    mode: "{self.config.sessions.maintenance_mode}"
    prune_after_days: {self.config.sessions.prune_after_days}
    max_entries: {self.config.sessions.max_entries}
    rotate_bytes: {self.config.sessions.rotate_bytes}
"""

    def _render_readme_session_persistence(self) -> str:
        """Render the Session Persistence section for README, or empty string."""
        if not self.config.sessions.enabled:
            return ""
        return """
## Session Persistence (Principle 11)

This project includes a session persistence module (`sessions.py`) that provides:

- **Append-only JSONL transcripts** — forensic-grade conversation logs
- **Session key routing** — context-encoded keys for efficient lookup
- **File-based write locking** — prevents concurrent writes with stale detection
- **Provider sanitisation** — transforms history for Google, Anthropic, OpenAI
- **JSONL file repair** — drops bad lines, creates backups, atomic rewrite
- **Session compaction** — LLM-powered summarisation to free context window space
- **Lifecycle management** — prune stale sessions, cap entries, rotate large files
- **Configuration loading** — reads session settings from `config.yaml`

Configure session persistence in `config.yaml` under the `sessions` section.
"""

    def _render_readme_session_config_line(self) -> str:
        """Render the session config bullet for README, or empty string."""
        if not self.config.sessions.enabled:
            return ""
        return "\n- **sessions.maintenance.mode** — Session lifecycle mode (warn/enforce)"

    def _render_test_sessions(self) -> str:
        """Render session tests for generated test_agent.py, or empty string."""
        if not self.config.sessions.enabled:
            return ""
        return """

SESSIONS_FILE = Path(__file__).parent.parent / "sessions.py"


class TestSessionsSyntax:
    \"\"\"Verify generated sessions.py is syntactically valid Python.\"\"\"

    def test_sessions_file_exists(self):
        assert SESSIONS_FILE.exists(), f"sessions.py not found at {SESSIONS_FILE}"

    def test_sessions_parses(self):
        \"\"\"Ensure sessions.py is valid Python syntax.\"\"\"
        source = SESSIONS_FILE.read_text()
        ast.parse(source)

    def test_sessions_has_key_classes(self):
        \"\"\"Verify sessions.py contains all required classes.\"\"\"
        source = SESSIONS_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in ["MessageRole", "SessionStore", "RepairResult", "CompactionResult"]:
            assert expected in class_names, f"{expected} class not found in sessions.py"

    def test_sessions_has_key_functions(self):
        \"\"\"Verify sessions.py contains all required functions.\"\"\"
        source = SESSIONS_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "build_session_key", "append_message", "load_transcript",
            "session_write_lock", "sanitise_for_provider",
            "repair_session_file", "compact_session",
        ]:
            assert expected in func_names, f"{expected} function not found in sessions.py"
"""

    def _render_session_wrapper(self) -> str:
        """Render the run_agent_with_session() wrapper, or empty string."""
        if not self.config.sessions.enabled:
            return ""
        return '''
from sessions import (
    SessionStore, build_session_key, ensure_session_header,
    append_message, load_transcript, session_write_lock,
    Message, MessageRole,
)


def run_agent_with_session(
    query: str,
    context: dict | None = None,
    agent_id: str = "main",
    sessions_dir: str = ".agent/sessions",
) -> str:
    """Run the agent with session persistence (Principle 11).

    Wraps run_agent() with session loading, message appending,
    and metadata tracking.

    Args:
        query: The input query to process.
        context: Optional context dictionary.
        agent_id: Agent identifier for session key.
        sessions_dir: Directory for session files.

    Returns:
        Agent response string.
    """
    import time as _time

    store_path = f"{sessions_dir}/sessions.json"
    store = SessionStore(store_path)

    session_key = build_session_key(agent_id)
    entry = store.get(session_key)
    if entry is None:
        from sessions import SessionEntry
        entry = SessionEntry.new(session_key, sessions_dir)
        store.upsert(session_key, entry)

    ensure_session_header(entry.session_file, entry.session_id)

    user_msg = Message(role=MessageRole.USER, content=query)
    with session_write_lock(entry.session_file):
        append_message(entry.session_file, user_msg)

    result = run_agent(query, context)

    assistant_msg = Message(role=MessageRole.ASSISTANT, content=result)
    with session_write_lock(entry.session_file):
        append_message(entry.session_file, assistant_msg)

    entry.updated_at = _time.time() * 1000
    store.upsert(session_key, entry)

    return result
'''

    # ------------------------------------------------------------------
    # Tool governance helpers
    # ------------------------------------------------------------------

    def _render_deny_list(self) -> str:
        """Render the deny list for config.yaml."""
        deny = self.config.tool_governance.deny
        if not deny:
            return "[]"
        items = ", ".join(f'"{d}"' for d in deny)
        return f"[{items}]"

    # ------------------------------------------------------------------
    # Identity layer rendering (Principle 3)
    # ------------------------------------------------------------------

    def _render_main_block(self) -> str:
        """Render the if __name__ == '__main__' block.

        When LangSmith is enabled, adds --dev flag parsing that sets
        LANGCHAIN_TRACING_V2=true at runtime.
        When sessions are enabled, calls run_agent_with_session() instead.
        """
        run_fn = "run_agent_with_session" if self.config.sessions.enabled else "run_agent"
        if self.config.langsmith.enabled:
            return f'''\
if __name__ == "__main__":
    import os

    _dev = "--dev" in sys.argv
    _args = [a for a in sys.argv[1:] if a != "--dev"]
    if _dev:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if _args:
        user_query = " ".join(_args)
        print(f"Query: {{user_query}}")
        print("=" * 60)
        try:
            result = {run_fn}(user_query)
            print(result)
        except RuntimeError as e:
            print(f"Error: {{e}}")
            sys.exit(1)
    else:
        print("Usage: python agent.py [--dev] <query>")
        sys.exit(1)'''
        return f'''\
if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        print(f"Query: {{user_query}}")
        print("=" * 60)
        try:
            result = {run_fn}(user_query)
            print(result)
        except RuntimeError as e:
            print(f"Error: {{e}}")
            sys.exit(1)
    else:
        print("Usage: python agent.py <query>")
        sys.exit(1)'''

    def _render_test_tracing(self) -> str:
        """Render tracing test class for generated test_agent.py, or empty string."""
        if not self.config.langsmith.enabled:
            return ""
        return """

class TestTracingSetup:
    \"\"\"Verify LangSmith tracing is configured.\"\"\"

    def test_agent_has_traceable_decorator(self):
        source = AGENT_FILE.read_text()
        assert "@traceable" in source

    def test_agent_imports_langsmith(self):
        source = AGENT_FILE.read_text()
        assert "from langsmith" in source

    def test_agent_has_dev_flag(self):
        \"\"\"Tracing is activated via --dev flag.\"\"\"
        source = AGENT_FILE.read_text()
        assert "--dev" in source
        assert "LANGCHAIN_TRACING_V2" in source
"""

    def _render_readme_langsmith_config_line(self) -> str:
        """Render the tracing config bullet for README, or empty string."""
        if not self.config.langsmith.enabled:
            return ""
        return "\n- **tracing.project** — LangSmith project name for trace grouping"

    def _render_readme_langsmith(self) -> str:
        """Render the Observability section for README, or empty string."""
        if not self.config.langsmith.enabled:
            return ""
        return f"""
## Observability (Principle 16)

This project includes LangSmith tracing for production observability.
All agent invocations are traced and visible in the
[LangSmith Studio](https://smith.langchain.com) dashboard.

Tracing is **opt-in at runtime** via the `--dev` flag to avoid overhead in production.

### Setup

1. Get your API key from [LangSmith](https://smith.langchain.com)
2. Set environment variables in `.env`:
   ```
   LANGCHAIN_API_KEY=lsv2_your_key_here
   LANGCHAIN_PROJECT={self.config.langsmith.project}
   ```

### Usage

```bash
# Run with tracing enabled (dev/debug)
python agent.py --dev "your query here"

# Run without tracing (production)
python agent.py "your query here"
```

The `--dev` flag sets `LANGCHAIN_TRACING_V2=true` at runtime.
You can also set this env var directly for CI/CD or always-on tracing.

### Configuration

Edit `config.yaml` under the `tracing` section.
"""

    def _render_langsmith_config_yaml(self) -> str:
        """Render the tracing section of config.yaml, or empty string."""
        if not self.config.langsmith.enabled:
            return ""
        return f"""
tracing:
  enabled: true
  provider: "langsmith"
  project: "{self.config.langsmith.project}"
  # Activated at runtime with --dev flag (or LANGCHAIN_TRACING_V2=true)
  # endpoint: "https://api.smith.langchain.com"
"""

    def _render_identity_config_yaml(self) -> str:
        """Render the identity section of config.yaml, or empty string."""
        if not self.config.identity.enabled:
            return ""
        layers_str = ", ".join(f'"{layer}"' for layer in self.config.identity.layers)
        focus_str = ", ".join(f'"{f}"' for f in self.config.identity.rules_focus)
        return f"""
identity:
  enabled: true
  layers: [{layers_str}]
  personality_preset: "{self.config.identity.personality_preset}"
  rules_focus: [{focus_str}]
  max_chars_per_file: 20000
  truncation:
    head_ratio: 0.7
    tail_ratio: 0.2
"""

    # ------------------------------------------------------------------
    # Skills / Capabilities (Principle 7)
    # ------------------------------------------------------------------

    def _render_skills_config_yaml(self) -> str:
        """Render the skills section of config.yaml, or empty string."""
        if not self.config.skills.enabled:
            return ""
        return f"""
skills:
  enabled: true
  skills_dir: "{self.config.skills.skills_dir}"
  max_description_chars: {self.config.skills.max_description_chars}
  read_tool_name: "{self.config.skills.read_tool_name}"
"""

    def _render_readme_skills(self) -> str:
        """Render the Progressive Capability Disclosure section for README, or empty string."""
        if not self.config.skills.enabled:
            return ""
        return """
## Progressive Capability Disclosure (Principle 7)

This project includes a capabilities module (`capabilities.py`) that organises agent
skills into three tiers for efficient context window usage:

| Tier | Budget | When Loaded |
|------|--------|-------------|
| **Metadata** | ~100 words per skill | Always in system prompt |
| **Full Instructions** | Up to 5,000 words | On demand, when the model reads SKILL.md |
| **Resources** | Unlimited | During active execution only |

### How It Works

1. **Discovery** — Skills are scanned from `skills/`, `.agents/skills/`, and extra directories
2. **Filtering** — Skills are checked for OS compatibility, required binaries, and env vars
3. **Snapshot** — An immutable point-in-time snapshot is created for session consistency
4. **Prompt Builder** — Tier 1 metadata is formatted as `<available_skills>` XML in the system prompt
5. **On-Demand Loading** — The model reads SKILL.md (Tier 2) only when it selects a skill

### Adding a Skill

Create a directory under `skills/` with a `SKILL.md` file:

```
skills/my-skill/
    SKILL.md          # Tier 1 (frontmatter) + Tier 2 (body)
    references/       # Tier 3 resources (optional)
    scripts/          # Tier 3 resources (optional)
```

Configure skills in `config.yaml` under the `skills` section.
"""

    def _render_readme_skills_config_line(self) -> str:
        """Render the skills config bullet for README, or empty string."""
        if not self.config.skills.enabled:
            return ""
        return "\n- **skills.skills_dir** — Directory to scan for skill definitions"

    def _render_test_skills(self) -> str:
        """Render capabilities tests for generated test_agent.py, or empty string."""
        if not self.config.skills.enabled:
            return ""
        return """

CAPABILITIES_FILE = Path(__file__).parent.parent / "capabilities.py"


class TestCapabilitiesSyntax:
    \"\"\"Verify generated capabilities.py is syntactically valid Python.\"\"\"

    def test_capabilities_file_exists(self):
        assert CAPABILITIES_FILE.exists(), f"capabilities.py not found at {CAPABILITIES_FILE}"

    def test_capabilities_parses(self):
        \"\"\"Ensure capabilities.py is valid Python syntax.\"\"\"
        source = CAPABILITIES_FILE.read_text()
        ast.parse(source)

    def test_capabilities_has_key_classes(self):
        \"\"\"Verify capabilities.py contains all required classes.\"\"\"
        source = CAPABILITIES_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "SkillSource", "SkillRequirements", "SkillMetadata",
            "SkillSnapshot", "SnapshotCache",
        ]:
            assert expected in class_names, f"{expected} class not found in capabilities.py"

    def test_capabilities_has_key_functions(self):
        \"\"\"Verify capabilities.py contains all required functions.\"\"\"
        source = CAPABILITIES_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "parse_skill_file", "extract_description",
            "scan_skill_directory", "discover_all_skills",
            "filter_eligible_skills", "build_snapshot",
            "format_skills_for_prompt", "build_skills_system_prompt_section",
            "load_full_instructions", "load_resource",
        ]:
            assert expected in func_names, f"{expected} function not found in capabilities.py"
"""

    # ------------------------------------------------------------------
    # Observability helpers (Principle 17)
    # ------------------------------------------------------------------

    def _render_observability_config_yaml(self) -> str:
        """Render the observability section of config.yaml, or empty string."""
        if not self.config.observability.enabled:
            return ""
        obs = self.config.observability
        cw_group = obs.cloudwatch_log_group or "# auto-detected in AWS"
        cw_region = obs.cloudwatch_region or "# defaults to agent region"
        return f"""
observability:
  enabled: true
  log_dir: "{obs.log_dir}"
  transcript_dir: "{obs.transcript_dir}"
  log_level: "{obs.log_level}"
  cloudwatch_log_group: "{cw_group}"
  cloudwatch_region: "{cw_region}"
  enable_transcripts: {str(obs.enable_transcripts).lower()}
  enable_cost_tracking: {str(obs.enable_cost_tracking).lower()}
  enable_config_audit: {str(obs.enable_config_audit).lower()}
  enable_prompt_log: {str(obs.enable_prompt_log).lower()}
  enable_diagnostics: {str(obs.enable_diagnostics).lower()}
"""

    def _render_readme_observability(self) -> str:
        """Render the Operational Observability section for README, or empty string."""
        if not self.config.observability.enabled:
            return ""
        return """
## Operational Observability (Principle 17)

This project includes an observability module (`observability.py`) that provides
structured logging, audit, and accountability — complementing LangSmith tracing
with operational concerns that LangSmith doesn't cover.

| Concern | LangSmith | observability.py |
|---------|-----------|-----------------|
| LLM call tracing | Spans, inputs/outputs | Not covered |
| Structured operational logging | Not covered | JSON logging with subsystem awareness |
| Dual-destination (CloudWatch/local) | Not covered | Auto-detect AWS, fallback to local |
| Session transcripts | Cloud-hosted traces | Local JSONL forensic record |
| Cost tracking | Token counts in cloud | Per-model pricing with last-call semantics |
| Config audit | Not covered | Before/after hashing, suspicious change detection |
| Diagnostic events | Not covered | Pluggable event system |

### Dual-Destination Logging

- **In AWS** (Lambda, ECS, EC2): logs route to CloudWatch automatically
- **Locally**: logs write to `.agent/logs/` as JSONL files

### Available Audit Logs

- `logs/*.jsonl` — Structured operational logs
- `logs/prompts.jsonl` — System prompt snapshots per invocation
- `logs/config_audit.jsonl` — Configuration change detection
- `logs/events.jsonl` — Diagnostic events
- `transcripts/*.jsonl` — Append-only session transcripts

Configure observability in `config.yaml` under the `observability` section.
"""

    def _render_readme_observability_config_line(self) -> str:
        """Render the observability config bullet for README, or empty string."""
        if not self.config.observability.enabled:
            return ""
        return "\n- **observability.log_level** — Minimum log level for structured logging"

    def _render_test_observability(self) -> str:
        """Render observability tests for generated test_agent.py, or empty string."""
        if not self.config.observability.enabled:
            return ""
        return """

OBSERVABILITY_FILE = Path(__file__).parent.parent / "observability.py"


class TestObservabilitySyntax:
    \"\"\"Verify generated observability.py is syntactically valid Python.\"\"\"

    def test_observability_file_exists(self):
        assert OBSERVABILITY_FILE.exists(), f"observability.py not found at {OBSERVABILITY_FILE}"

    def test_observability_parses(self):
        \"\"\"Ensure observability.py is valid Python syntax.\"\"\"
        source = OBSERVABILITY_FILE.read_text()
        ast.parse(source)

    def test_observability_has_key_classes(self):
        \"\"\"Verify observability.py contains all required classes.\"\"\"
        source = OBSERVABILITY_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "TokenUsage", "CostBreakdown", "ModelCostConfig",
            "SessionTranscript", "PromptLog", "ConfigAuditLog",
            "ObservabilityContext",
        ]:
            assert expected in class_names, f"{expected} class not found in observability.py"

    def test_observability_has_key_functions(self):
        \"\"\"Verify observability.py contains all required functions.\"\"\"
        source = OBSERVABILITY_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "setup_logging", "get_logger", "setup_observability",
            "calculate_cost", "hash_content", "subscribe", "emit",
        ]:
            assert expected in func_names, f"{expected} function not found in observability.py"
"""

    def _render_test_identity(self) -> str:
        """Render identity layer tests for generated test_agent.py, or empty string."""
        if not self.config.identity.enabled:
            return ""
        layers_list = ", ".join(f'"{layer.upper()}.md"' for layer in self.config.identity.layers)
        return f"""


BRIEF_PACKET_FILE = Path(__file__).parent.parent / "brief_packet.py"
IDENTITY_ACCESS_FILE = Path(__file__).parent.parent / "identity_access.py"
IDENTITY_DIR = Path(__file__).parent.parent / "identity"


class TestBriefPacketSyntax:
    \"\"\"Verify generated brief_packet.py is syntactically valid Python.\"\"\"

    def test_brief_packet_file_exists(self):
        assert BRIEF_PACKET_FILE.exists(), f"brief_packet.py not found at {{BRIEF_PACKET_FILE}}"

    def test_brief_packet_parses(self):
        \"\"\"Ensure brief_packet.py is valid Python syntax.\"\"\"
        source = BRIEF_PACKET_FILE.read_text()
        ast.parse(source)

    def test_brief_packet_has_key_functions(self):
        \"\"\"Verify brief_packet.py contains required functions.\"\"\"
        source = BRIEF_PACKET_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in ["assemble_brief_packet", "_truncate", "_read_layer", "_build_runtime_context"]:
            assert expected in func_names, f"{{expected}} function not found in brief_packet.py"


class TestIdentityAccessSyntax:
    \"\"\"Verify generated identity_access.py is syntactically valid Python.\"\"\"

    def test_identity_access_file_exists(self):
        assert IDENTITY_ACCESS_FILE.exists(), f"identity_access.py not found at {{IDENTITY_ACCESS_FILE}}"

    def test_identity_access_parses(self):
        \"\"\"Ensure identity_access.py is valid Python syntax.\"\"\"
        source = IDENTITY_ACCESS_FILE.read_text()
        ast.parse(source)

    def test_identity_access_has_key_functions(self):
        \"\"\"Verify identity_access.py contains required functions.\"\"\"
        source = IDENTITY_ACCESS_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in ["can_modify", "modify_layer", "list_backups", "restore_backup"]:
            assert expected in func_names, f"{{expected}} function not found in identity_access.py"


class TestIdentityLayers:
    \"\"\"Verify identity layer files are present.\"\"\"

    def test_identity_dir_exists(self):
        assert IDENTITY_DIR.exists(), f"identity/ directory not found at {{IDENTITY_DIR}}"

    def test_expected_layers_present(self):
        \"\"\"Verify all configured identity layer files exist.\"\"\"
        expected_layers = [{layers_list}]
        for layer_file in expected_layers:
            path = IDENTITY_DIR / layer_file
            assert path.exists(), f"Identity layer {{layer_file}} not found at {{path}}"

    def test_backups_dir_exists(self):
        \"\"\"Verify identity/.backups/ directory exists for versioning.\"\"\"
        backups_dir = IDENTITY_DIR / ".backups"
        assert backups_dir.exists(), f".backups/ directory not found at {{backups_dir}}"
"""

    # ------------------------------------------------------------------
    # Tools helpers
    # ------------------------------------------------------------------

    def _render_tools_config_yaml(self) -> str:
        """Render the tools directory section of config.yaml, or empty string."""
        if not self.config.tools.enabled:
            return ""
        return f"""
# Tools — executable functions available to the agent
tool_functions:
  directory: "{self.config.tools.tools_dir}"
  # Add tool-specific configuration below:
  # example_tool:
  #   timeout_seconds: 30
"""

    def _render_readme_tools(self) -> str:
        """Render the Tools section for README, or empty string."""
        if not self.config.tools.enabled:
            return ""
        return """
## Tools (Principle 9: Tool Governance)

This project includes a `tools/` directory with auto-discovery, governance
integration, and progressive disclosure:

| Component | Purpose |
|-----------|---------|
| `tools/__init__.py` | `AgentTool` ABC, registry, discovery, governance |
| `tools/example_tool.py` | Complete example — subclass of `AgentTool` |
| `tool_policy.py` | Governance — profiles, deny lists, sub-agent restrictions |

### Unified Tool Interface

Each tool file defines one `AgentTool` subclass — one class = one tool:

```python
from tools import AgentTool, ToolParameter

class MyTool(AgentTool):
    name = "my_tool"
    description = "Short description for system prompt (~100 words)."
    parameters = {"query": ToolParameter(type="str", description="Input")}
    resources = {"docs": "https://..."}   # Tier 3: loaded at execution time

    def execute(self, **kwargs):
        return f"Result: {kwargs['query']}"
```

### Adding a New Tool

1. Create `tools/my_tool.py` with a class that extends `AgentTool`
2. Set `name`, `description`, `parameters`, and implement `execute()`
3. The registry discovers it automatically at startup
4. Tool governance (`tool_policy.py`) filters it based on the active profile
5. The agent framework adapts it (bind_tools / Agent(tools=...) / TOOL_REGISTRY)

### Progressive Disclosure

- **Tier 1**: `name` + `description` + `parameters` (class attributes → system prompt)
- **Tier 2**: Class/method docstrings (loaded when tool is selected)
- **Tier 3**: `resources` dict (loaded during execution)

### Inference-Only Failover

When no tools are discovered (empty `tools/` directory), the agent runs in
inference-only mode — pure LLM reasoning without tool calls. No errors, just
a log message.
"""

    def _render_readme_tools_config_line(self) -> str:
        """Render the tools config bullet for README, or empty string."""
        if not self.config.tools.enabled:
            return ""
        return "\n- **tool_functions.directory** — Directory containing tool modules"

    def _render_test_tools(self) -> str:
        """Render tools tests for generated test_agent.py, or empty string."""
        if not self.config.tools.enabled:
            return ""
        return """


TOOLS_INIT_FILE = Path(__file__).parent.parent / "tools" / "__init__.py"
EXAMPLE_TOOL_FILE = Path(__file__).parent.parent / "tools" / "example_tool.py"


class TestToolsSyntax:
    \"\"\"Verify generated tools/ files are syntactically valid Python.\"\"\"

    def test_tools_init_exists(self):
        assert TOOLS_INIT_FILE.exists(), f"tools/__init__.py not found at {TOOLS_INIT_FILE}"

    def test_tools_init_parses(self):
        \"\"\"Ensure tools/__init__.py is valid Python syntax.\"\"\"
        source = TOOLS_INIT_FILE.read_text()
        ast.parse(source)

    def test_tools_init_has_key_classes(self):
        \"\"\"Verify tools/__init__.py contains required classes.\"\"\"
        source = TOOLS_INIT_FILE.read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in ["AgentTool", "ToolParameter", "ToolMetadata", "ToolDefinition", "ToolRegistry"]:
            assert expected in class_names, f"{expected} class not found in tools/__init__.py"

    def test_tools_init_has_key_functions(self):
        \"\"\"Verify tools/__init__.py contains required functions.\"\"\"
        source = TOOLS_INIT_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in ["discover_tools", "get_permitted_tools"]:
            assert expected in func_names, f"{expected} function not found in tools/__init__.py"

    def test_example_tool_exists(self):
        assert EXAMPLE_TOOL_FILE.exists(), f"example_tool.py not found at {EXAMPLE_TOOL_FILE}"

    def test_example_tool_parses(self):
        \"\"\"Ensure tools/example_tool.py is valid Python syntax.\"\"\"
        source = EXAMPLE_TOOL_FILE.read_text()
        ast.parse(source)

    def test_example_tool_is_agent_tool(self):
        \"\"\"Verify example_tool.py defines an AgentTool subclass.\"\"\"
        source = EXAMPLE_TOOL_FILE.read_text()
        assert "class ExampleTool" in source
        assert "AgentTool" in source

    def test_example_tool_has_execute(self):
        \"\"\"Verify example_tool.py contains the execute method.\"\"\"
        source = EXAMPLE_TOOL_FILE.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "execute" in func_names

    def test_example_tool_has_resources(self):
        \"\"\"Verify example_tool.py contains resources.\"\"\"
        source = EXAMPLE_TOOL_FILE.read_text()
        assert "resources" in source
"""

    # ------------------------------------------------------------------
    # tools/ — Tool Discovery and Registry
    # ------------------------------------------------------------------

    def render_tools_init_py(self) -> str:
        """Render the tools/__init__.py — unified AgentTool base class.

        Provides the AgentTool ABC, discovery, registry, governance integration,
        and backward-compatible aliases.
        """
        if self.config.observability.enabled:
            logger_setup = (
                'from observability import get_logger\n\n'
                'logger = get_logger("tools")'
            )
        else:
            logger_setup = (
                'import logging\n\n'
                'logger = logging.getLogger(__name__)'
            )

        return f'''\
"""Tool registry — unified AgentTool interface with progressive disclosure.

Provides:
- AgentTool ABC — subclass, set fields, implement execute()
- ToolParameter dataclass for typed parameter schemas
- Auto-discovery of AgentTool subclasses in the tools/ directory
- Legacy fallback for TOOL_METADATA dict pattern
- Registry for lookup and governance integration
- Graceful failover when no tools are defined
"""

from __future__ import annotations

import importlib
import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

{logger_setup}


# =============================================================================
# 1. TYPES — Unified Tool Interface
# =============================================================================


@dataclass
class ToolParameter:
    """Typed parameter schema for a tool.

    Attributes:
        type: Python type name (e.g. "str", "int", "list[str]").
        description: Human-readable description of the parameter.
        required: Whether the parameter is required. Defaults to True.
        default: Default value if not required.
    """

    type: str = "str"
    description: str = ""
    required: bool = True
    default: Any = None


class AgentTool(ABC):
    """Unified tool interface — subclass, set fields, implement execute().

    One class = one tool. All core fields are unified on the class:

        class MyTool(AgentTool):
            name = "my_tool"
            description = "Does something useful."
            parameters = {{"query": ToolParameter(type="str", description="Input")}}

            def execute(self, **kwargs: Any) -> Any:
                return f"Result: {{kwargs['query']}}"

    Progressive Disclosure:
        - Tier 1: name + description + parameters (system prompt)
        - Tier 2: Class/method docstrings (loaded when tool is selected)
        - Tier 3: resources dict (loaded during execution)
    """

    # Core fields — user sets these on the subclass
    name: str = ""
    description: str = ""
    label: str = ""
    parameters: dict[str, ToolParameter] = {{}}

    # Optional metadata
    version: str = "1.0.0"
    category: str = "utility"
    resources: dict[str, Any] = {{}}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate required fields at class-definition time."""
        super().__init_subclass__(**kwargs)
        # Skip validation for internal/abstract intermediaries
        if inspect.isabstract(cls):
            return
        if not cls.name:
            raise TypeError(f"{{cls.__name__}} must set 'name'")
        if not cls.description:
            raise TypeError(f"{{cls.__name__}} must set 'description'")
        # Auto-derive label from name if not set
        if not cls.label:
            cls.label = cls.name.replace("_", " ").title()

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool. Subclasses must implement this."""
        ...

    def __call__(self, **kwargs: Any) -> Any:
        """Convenience — delegates to execute()."""
        return self.execute(**kwargs)

    # -- Progressive disclosure properties --

    @property
    def tier1_metadata(self) -> dict[str, Any]:
        """Tier 1: Summary metadata for system prompt."""
        return {{
            "name": self.name,
            "description": self.description,
            "label": self.label,
            "version": self.version,
            "category": self.category,
            "parameters": {{
                k: {{"type": v.type, "description": v.description, "required": v.required}}
                for k, v in self.parameters.items()
            }},
        }}

    @property
    def tier2_description(self) -> str:
        """Tier 2: Full docstring — loaded when tool is selected."""
        return self.execute.__doc__ or self.__class__.__doc__ or self.description

    @property
    def tier3_resources(self) -> dict[str, Any]:
        """Tier 3: Runtime references — loaded during execution."""
        return self.resources

    def as_function(self) -> Callable[..., Any]:
        """Return a plain callable for framework consumption.

        Patches __name__ and __doc__ so frameworks (LangChain, Strands)
        can introspect the function correctly.
        """
        fn = self.execute
        fn.__name__ = self.name  # type: ignore[attr-defined]
        fn.__doc__ = self.description
        return fn


# -- Backward-compatible aliases --

@dataclass
class ToolMetadata:
    """Tier 1 metadata — kept for backward compatibility.

    Prefer using AgentTool class attributes directly.
    """

    name: str
    description: str
    version: str = "1.0.0"
    category: str = "utility"
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Complete tool definition — kept for backward compatibility.

    Prefer using AgentTool subclasses directly.
    """

    metadata: ToolMetadata
    function: Callable[..., Any]
    resources: dict[str, Any] = field(default_factory=dict)
    module_path: str = ""


# =============================================================================
# 2. DISCOVERY — Auto-import tool modules
# =============================================================================


def _legacy_tool(
    name: str,
    description: str,
    func: Callable[..., Any],
    version: str = "1.0.0",
    category: str = "utility",
    parameters: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> AgentTool:
    """Wrap a legacy TOOL_METADATA dict into an AgentTool instance."""
    param_objs: dict[str, ToolParameter] = {{}}
    for pname, pdef in (parameters or {{}}).items():
        if isinstance(pdef, dict):
            param_objs[pname] = ToolParameter(
                type=pdef.get("type", "str"),
                description=pdef.get("description", ""),
                required=pdef.get("required", True),
                default=pdef.get("default"),
            )

    # Dynamically create an AgentTool subclass
    tool_cls = type(
        f"_Legacy_{{name}}",
        (AgentTool,),
        {{
            "name": name,
            "description": description,
            "version": version,
            "category": category,
            "parameters": param_objs,
            "resources": resources or {{}},
            "execute": lambda self, **kwargs: func(**kwargs),
        }},
    )
    return tool_cls()


def discover_tools(tools_dir: Path | None = None) -> list[AgentTool]:
    """Discover tool modules in the tools directory.

    Primary strategy: find AgentTool subclasses in modules.
    Fallback strategy: wrap legacy TOOL_METADATA dicts into AgentTool instances.

    Args:
        tools_dir: Directory to scan. Defaults to this package's directory.

    Returns:
        List of discovered AgentTool instances.
    """
    if tools_dir is None:
        tools_dir = Path(__file__).parent

    tools: list[AgentTool] = []

    for path in sorted(tools_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue

        module_name = path.stem
        try:
            parent_str = str(tools_dir.parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)

            module = importlib.import_module(f"tools.{{module_name}}")

            # Primary: find AgentTool subclasses
            found_subclass = False
            for _attr_name in dir(module):
                obj = getattr(module, _attr_name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, AgentTool)
                    and obj is not AgentTool
                    and not inspect.isabstract(obj)
                ):
                    tools.append(obj())
                    found_subclass = True
                    logger.debug("Discovered tool: %s (v%s)", obj.name, obj.version)

            if found_subclass:
                continue

            # Fallback: legacy TOOL_METADATA dict pattern
            metadata_dict = getattr(module, "TOOL_METADATA", None)
            if metadata_dict is None:
                logger.debug("Skipping %s — no AgentTool subclass or TOOL_METADATA", module_name)
                continue

            tool_name = metadata_dict.get("name", module_name)
            func = getattr(module, tool_name, None)
            if func is None or not callable(func):
                logger.warning(
                    "Tool %s has TOOL_METADATA but no callable '%s'",
                    module_name,
                    tool_name,
                )
                continue

            resources = getattr(module, "TOOL_RESOURCES", {{}})
            tool_instance = _legacy_tool(
                name=tool_name,
                description=metadata_dict.get("description", ""),
                func=func,
                version=metadata_dict.get("version", "1.0.0"),
                category=metadata_dict.get("category", "utility"),
                parameters=metadata_dict.get("parameters", {{}}),
                resources=resources,
            )
            tools.append(tool_instance)
            logger.debug("Discovered legacy tool: %s (v%s)", tool_name, tool_instance.version)

        except Exception as exc:
            logger.warning("Failed to load tool module %s: %s", module_name, exc)

    if not tools:
        logger.info(
            "No tools discovered in %s — agent runs in inference-only mode",
            tools_dir,
        )

    return tools


# =============================================================================
# 3. REGISTRY — Lookup and access
# =============================================================================


class ToolRegistry:
    """Registry for discovered tools with progressive disclosure access.

    Stores AgentTool instances with Tier 1 (metadata), Tier 2 (docstring),
    and Tier 3 (resources) access patterns.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {{}}

    def register(self, tool: AgentTool) -> None:
        """Register an AgentTool instance."""
        self._tools[tool.name] = tool

    def get_all(self) -> list[AgentTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get(self, name: str) -> AgentTool | None:
        """Get a single tool by name."""
        return self._tools.get(name)

    def get_metadata(self) -> list[dict[str, Any]]:
        """Tier 1: Get metadata summaries for all tools."""
        return [t.tier1_metadata for t in self._tools.values()]

    def get_description(self, name: str) -> str:
        """Tier 2: Get full docstring/description for a specific tool."""
        tool = self._tools.get(name)
        if tool is None:
            return ""
        return tool.tier2_description

    def get_resources(self, name: str) -> dict[str, Any]:
        """Tier 3: Get runtime resources for a specific tool."""
        tool = self._tools.get(name)
        if tool is None:
            return {{}}
        return tool.tier3_resources

    @property
    def names(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)


# =============================================================================
# 4. GOVERNANCE INTEGRATION — Filter through tool_policy
# =============================================================================


def get_permitted_tools(
    tools_dir: Path | None = None,
    is_subagent: bool = False,
) -> list[AgentTool]:
    """Discover tools and filter through governance policy.

    Returns a list of AgentTool instances that pass the governance filter.

    Args:
        tools_dir: Directory to scan for tool modules.
        is_subagent: If True, apply sub-agent restrictions.

    Returns:
        List of permitted AgentTool instances. Empty list if no tools available.
    """
    discovered = discover_tools(tools_dir)
    if not discovered:
        return []

    # Build a registry from discovered tools
    registry = ToolRegistry()
    for tool in discovered:
        registry.register(tool)

    # Filter through tool governance
    try:
        from tool_policy import filter_tools

        all_names = registry.names
        permitted_names = filter_tools(all_names, is_subagent=is_subagent)
    except ImportError:
        logger.warning("tool_policy not found — allowing all discovered tools")
        permitted_names = registry.names

    return [
        registry.get(name)
        for name in permitted_names
        if registry.get(name) is not None
    ]
'''

    def render_example_tool_py(self) -> str:
        """Render the tools/example_tool.py — a complete AgentTool subclass."""
        return '''\
"""example_tool — Demonstrate the unified AgentTool interface.

This is a complete example of a tool using the AgentTool base class.
Each tool file in the tools/ directory defines one class that the
registry auto-discovers and loads.

Progressive Disclosure Tiers:
- Tier 1: name + description + parameters (class attributes → system prompt)
- Tier 2: Class/method docstrings (loaded when tool is selected)
- Tier 3: resources dict (loaded during execution)

Usage:
    tool = ExampleTool()
    result = tool.execute(query="hello world")
    # Returns: "Processed: hello world"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import AgentTool, ToolParameter


class ExampleTool(AgentTool):
    """Example tool that processes a query string.

    Replace this class with your actual tool implementation.
    Keep the description under ~100 words for efficient system prompt usage.
    """

    name = "example_tool"
    description = (
        "Example tool that processes a query string. "
        "Replace this with your actual tool description. "
        "Keep under ~100 words for efficient system prompt usage."
    )
    label = "Example Tool"
    parameters = {
        "query": ToolParameter(
            type="str",
            description="The input string to process",
            required=True,
        ),
    }
    version = "1.0.0"
    category = "utility"
    resources = {
        "docs": "https://docs.example.com/tools/example",
        "changelog": "https://docs.example.com/tools/example/changelog",
    }

    def _load_config(self) -> dict[str, Any]:
        """Load tool-specific configuration from config.yaml.

        Reads from the tools.<tool_name> section of config.yaml.
        Returns empty dict if not configured.
        """
        config_path = Path(__file__).parent.parent / "config.yaml"
        if not config_path.exists():
            return {}

        try:
            import yaml

            with open(config_path) as f:
                full_config = yaml.safe_load(f) or {}

            tools_cfg = full_config.get("tools", {})
            return tools_cfg.get(self.name, {})
        except Exception:
            return {}

    def execute(self, **kwargs: Any) -> Any:
        """Process a query string and return the result.

        This is a placeholder implementation. Replace the body with your
        actual tool logic.

        Args:
            **kwargs: Must include "query" (str).

        Returns:
            Processed result string.

        Example:
            >>> ExampleTool().execute(query="hello world")
            \'Processed: hello world\'
        """
        query: str = kwargs["query"]

        # Load any tool-specific config
        _config = self._load_config()
        _timeout = _config.get("timeout_seconds", 30)

        # --- Replace this with your actual implementation ---
        return f"Processed: {query}"
'''

    def render_example_skill_md(self) -> str:
        """Render an example SKILL.md demonstrating the three-tier structure."""
        return '''\
---
description: "Example skill — demonstrates the three-tier progressive disclosure structure."
metadata: |
  {"emoji": "📋", "primaryEnv": "python"}
user-invocable: true
---

## Example Skill

This is an example skill that demonstrates the SKILL.md format.

### Tier Structure

- **Tier 1 (above)**: The YAML frontmatter is parsed at startup and included
  in the system prompt as lightweight metadata (~100 words).
- **Tier 2 (this section)**: The full instructions body is loaded on demand
  when the model selects this skill via the `read_file` tool.
- **Tier 3**: Any files in this directory (scripts/, references/, etc.) are
  loaded only during active execution when the instructions reference them.

### Instructions

1. Identify the user's request
2. Follow the steps in this document
3. Reference any Tier 3 resources as needed

### Notes

- Replace this file with your actual skill instructions
- Keep the frontmatter description under 150 characters
- Add `requires` in metadata for environment checks (bins, env vars, OS)
'''

    def render_capabilities_py(self) -> str:
        """Render the complete capabilities.py for the generated project.

        Implements Principle 7: Progressive Capability Disclosure — consolidates
        7 blueprint modules into a single file:
        1. Types, 2. Frontmatter, 3. Discovery, 4. Filtering,
        5. Snapshot, 6. Prompt Builder, 7. Loader.
        """
        return '''\
"""Progressive Capability Disclosure — three-tier skill management.

Principle 7: Progressive Capability Disclosure — provides:
- Three-tier skill organisation (metadata, instructions, resources)
- Multi-source skill discovery with priority-based merging
- Environment eligibility filtering (OS, binaries, env vars)
- Immutable session snapshots for consistency
- System prompt injection of Tier 1 metadata
- On-demand Tier 2/3 loading via read tool
- Snapshot caching with version-based invalidation

Sections:
    - Types (SkillSource, SkillRequirements, SkillMetadata, SkillSnapshot)
    - Frontmatter (parse_skill_file, extract_description, extract_requirements)
    - Discovery (scan_skill_directory, discover_all_skills)
    - Filtering (check_os, check_bins, check_any_bins, check_env_vars, filter_eligible_skills)
    - Snapshot (build_snapshot, get_snapshot_version, bump_snapshot_version, SnapshotCache)
    - Prompt Builder (format_skills_for_prompt, build_skills_system_prompt_section)
    - Loader (load_full_instructions, load_resource, list_resources)
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# =============================================================================
# TYPES
# =============================================================================


class SkillSource(str, Enum):
    """Precedence order — higher numeric value wins."""

    EXTRA = "extra"
    PROJECT = "project"
    WORKSPACE = "workspace"


SOURCE_PRIORITY: dict[SkillSource, int] = {
    SkillSource.EXTRA: 1,
    SkillSource.PROJECT: 2,
    SkillSource.WORKSPACE: 3,
}


@dataclass
class SkillRequirements:
    """What the host environment must have for this skill to be eligible."""

    bins: list[str] = field(default_factory=list)
    any_bins: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    os: list[str] = field(default_factory=list)


@dataclass
class SkillMetadata:
    """Tier 1 — the lightweight summary that lives in the system prompt.

    Budget: ~100 words / 150 characters for the description.
    """

    name: str
    description: str
    skill_dir: str
    skill_file: str
    source: SkillSource
    emoji: str | None = None
    primary_env: str | None = None
    always: bool = False
    user_invocable: bool = True
    model_invocable: bool = True
    requires: SkillRequirements = field(default_factory=SkillRequirements)
    homepage: str | None = None


@dataclass
class SkillSnapshot:
    """An immutable point-in-time capture of all available skills.

    Created once per session. Never modified during the session.
    Changes on disk take effect on the NEXT invocation.
    """

    skills: list[SkillMetadata]
    prompt: str
    version: int
    created_at: str = ""

    def skill_names(self) -> list[str]:
        return [s.name for s in self.skills]

    def get_skill(self, name: str) -> SkillMetadata | None:
        for s in self.skills:
            if s.name == name:
                return s
        return None


# =============================================================================
# FRONTMATTER
# =============================================================================


_FRONTMATTER_RE = re.compile(
    r"^---\\s*\\n(.*?)\\n---\\s*\\n",
    re.DOTALL,
)


def parse_skill_file(content: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md into frontmatter (dict) and body (str).

    Returns:
        (frontmatter_dict, body_text)
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    raw_fm = match.group(1)
    body = content[match.end():]

    try:
        import yaml

        frontmatter: dict[str, Any] = yaml.safe_load(raw_fm) or {}
    except Exception:
        frontmatter = {}

    if "metadata" in frontmatter and isinstance(frontmatter["metadata"], str):
        try:
            frontmatter["metadata"] = json.loads(frontmatter["metadata"])
        except json.JSONDecodeError:
            frontmatter["metadata"] = {}

    return frontmatter, body.strip()


def extract_description(frontmatter: dict[str, Any], max_chars: int = 150) -> str:
    """Extract and truncate the skill description.

    Enforces the Tier 1 size budget.
    """
    desc = frontmatter.get("description", "").strip()
    if len(desc) > max_chars:
        return desc[: max_chars - 1] + "\\u2026"
    return desc


def extract_requirements(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Extract requirements from metadata."""
    meta = frontmatter.get("metadata", {})
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta.get("requires", {})


def is_model_invocable(frontmatter: dict[str, Any]) -> bool:
    """Check if the model is allowed to invoke this skill."""
    return not frontmatter.get("disable-model-invocation", False)


def is_user_invocable(frontmatter: dict[str, Any]) -> bool:
    """Check if the user can invoke this skill directly."""
    return frontmatter.get("user-invocable", True)


# =============================================================================
# DISCOVERY
# =============================================================================


def scan_skill_directory(
    directory: str,
    source: SkillSource,
) -> list[SkillMetadata]:
    """Scan a directory for skill subdirectories containing SKILL.md.

    Each subdirectory with a SKILL.md is treated as one skill.
    The directory name becomes the skill name.
    """
    skills: list[SkillMetadata] = []

    if not os.path.isdir(directory):
        return skills

    for entry in sorted(os.listdir(directory)):
        skill_dir = os.path.join(directory, entry)
        skill_file = os.path.join(skill_dir, "SKILL.md")

        if not os.path.isdir(skill_dir) or not os.path.isfile(skill_file):
            continue

        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue

        frontmatter, _body = parse_skill_file(content)

        reqs_raw = extract_requirements(frontmatter)
        meta_raw = frontmatter.get("metadata", {})
        if isinstance(meta_raw, str):
            try:
                meta_raw = json.loads(meta_raw)
            except json.JSONDecodeError:
                meta_raw = {}

        requirements = SkillRequirements(
            bins=reqs_raw.get("bins", []),
            any_bins=reqs_raw.get("anyBins", []),
            env_vars=reqs_raw.get("env", []),
            os=meta_raw.get("os", []),
        )

        skill = SkillMetadata(
            name=entry,
            description=extract_description(frontmatter),
            skill_dir=skill_dir,
            skill_file=skill_file,
            source=source,
            emoji=meta_raw.get("emoji"),
            primary_env=meta_raw.get("primaryEnv"),
            always=meta_raw.get("always", False),
            user_invocable=is_user_invocable(frontmatter),
            model_invocable=is_model_invocable(frontmatter),
            requires=requirements,
            homepage=meta_raw.get("homepage"),
        )
        skills.append(skill)

    return skills


def discover_all_skills(
    workspace_dir: str,
    extra_dirs: list[str] | None = None,
) -> list[SkillMetadata]:
    """Discover skills from 3 sources and merge with precedence.

    Sources (ascending priority):
      1. Extra directories (lowest)
      2. Project agent skills (.agents/skills/)
      3. Workspace skills (skills/)

    Higher-priority sources override lower-priority ones when
    skills share the same name.
    """
    sources: list[tuple[str, SkillSource]] = []

    for d in (extra_dirs or []):
        sources.append((d, SkillSource.EXTRA))

    project_skills = os.path.join(workspace_dir, ".agents", "skills")
    if os.path.isdir(project_skills):
        sources.append((project_skills, SkillSource.PROJECT))

    workspace_skills = os.path.join(workspace_dir, "skills")
    if os.path.isdir(workspace_skills):
        sources.append((workspace_skills, SkillSource.WORKSPACE))

    all_skills: list[SkillMetadata] = []
    for directory, source in sources:
        all_skills.extend(scan_skill_directory(directory, source))

    merged: dict[str, SkillMetadata] = {}
    all_skills.sort(key=lambda s: SOURCE_PRIORITY[s.source])
    for skill in all_skills:
        merged[skill.name] = skill

    return list(merged.values())


# =============================================================================
# FILTERING
# =============================================================================


def check_os(skill: SkillMetadata) -> bool:
    """Check if the current OS is in the skill's supported list."""
    if not skill.requires.os:
        return True
    current = platform.system().lower()
    return current in [o.lower() for o in skill.requires.os]


def check_bins(skill: SkillMetadata) -> bool:
    """Check that all required binaries exist on PATH."""
    for binary in skill.requires.bins:
        if shutil.which(binary) is None:
            return False
    return True


def check_any_bins(skill: SkillMetadata) -> bool:
    """Check that at least one of the required binaries exists."""
    if not skill.requires.any_bins:
        return True
    return any(shutil.which(b) is not None for b in skill.requires.any_bins)


def check_env_vars(skill: SkillMetadata) -> bool:
    """Check that all required environment variables are set."""
    for var in skill.requires.env_vars:
        if not os.environ.get(var):
            return False
    return True


def filter_eligible_skills(
    skills: list[SkillMetadata],
    agent_allowlist: list[str] | None = None,
    include_model_invocable_only: bool = True,
) -> list[SkillMetadata]:
    """Filter skills to only those eligible for the current environment.

    Checks (in order):
      1. OS compatibility
      2. Required binaries (all)
      3. Required binaries (any)
      4. Required environment variables
      5. Model invocation policy
      6. Agent-specific allowlist
    """
    eligible: list[SkillMetadata] = []

    for skill in skills:
        if not check_os(skill):
            continue
        if not check_bins(skill):
            continue
        if not check_any_bins(skill):
            continue
        if not check_env_vars(skill):
            continue
        if include_model_invocable_only and not skill.model_invocable:
            continue
        if agent_allowlist is not None and skill.name not in agent_allowlist:
            continue

        eligible.append(skill)

    return eligible


# =============================================================================
# SNAPSHOT
# =============================================================================


_version_lock = threading.Lock()
_global_version = 0


def get_snapshot_version() -> int:
    """Get the current global snapshot version."""
    with _version_lock:
        return _global_version


def bump_snapshot_version() -> int:
    """Bump and return the new global snapshot version."""
    global _global_version
    with _version_lock:
        _global_version += 1
        return _global_version


def build_snapshot(
    workspace_dir: str,
    extra_dirs: list[str] | None = None,
    agent_allowlist: list[str] | None = None,
) -> SkillSnapshot:
    """Build an immutable skill snapshot for the current session.

    This is the main entry point. It:
      1. Discovers skills from all sources
      2. Filters for eligibility
      3. Formats Tier 1 metadata for the system prompt
      4. Returns a frozen snapshot
    """
    all_skills = discover_all_skills(
        workspace_dir=workspace_dir,
        extra_dirs=extra_dirs,
    )

    eligible = filter_eligible_skills(
        skills=all_skills,
        agent_allowlist=agent_allowlist,
    )

    prompt = format_skills_for_prompt(eligible)

    return SkillSnapshot(
        skills=eligible,
        prompt=prompt,
        version=get_snapshot_version(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class SnapshotCache:
    """Cache a snapshot per session, rebuilding only when version changes."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[int, SkillSnapshot]] = {}

    def get_or_build(
        self,
        session_id: str,
        workspace_dir: str,
        **kwargs: Any,
    ) -> SkillSnapshot:
        """Get a cached snapshot or build a new one."""
        current_version = get_snapshot_version()
        cached = self._cache.get(session_id)

        if cached and cached[0] == current_version:
            return cached[1]

        snapshot = build_snapshot(workspace_dir, **kwargs)
        self._cache[session_id] = (current_version, snapshot)
        return snapshot


# =============================================================================
# PROMPT BUILDER
# =============================================================================


MAX_DESCRIPTION_CHARS = 150


def format_skills_for_prompt(skills: list[SkillMetadata]) -> str:
    """Format all eligible skills into the Tier 1 system prompt block.

    Each skill gets ~100 words: name, description, and file location.
    """
    if not skills:
        return ""

    lines = ["<available_skills>"]
    for skill in sorted(skills, key=lambda s: s.name):
        desc = skill.description
        if len(desc) > MAX_DESCRIPTION_CHARS:
            desc = desc[: MAX_DESCRIPTION_CHARS - 1] + "\\u2026"

        lines.append(f\'<skill name="{skill.name}">\')
        lines.append(f"  <description>{desc}</description>")
        lines.append(f"  <location>{skill.skill_file}</location>")
        if skill.primary_env:
            lines.append(f"  <env>{skill.primary_env}</env>")
        lines.append("</skill>")

    lines.append("</available_skills>")
    return "\\n".join(lines)


def build_skills_system_prompt_section(
    skills_prompt: str,
    read_tool_name: str = "read_file",
) -> str:
    """Build the full skills section for insertion into the system prompt.

    Includes scanning instructions, the constraint about
    reading at most one skill, and the formatted metadata.
    """
    if not skills_prompt:
        return ""

    return "\\n".join([
        "## Skills",
        "",
        "Before replying, scan the <available_skills> entries below.",
        f"- If exactly one skill clearly applies: use the `{read_tool_name}` "
        "tool to read its SKILL.md at <location>, then follow its instructions.",
        "- If multiple could apply: choose the most specific one, then read and follow it.",
        "- If none clearly apply: do not read any SKILL.md — respond normally.",
        "",
        "Constraints: never read more than one SKILL.md per turn.",
        "Only read after selecting — do not speculatively read skills.",
        "",
        skills_prompt,
        "",
    ])


# =============================================================================
# LOADER
# =============================================================================


def load_full_instructions(skill: SkillMetadata) -> str:
    """Load Tier 2: the full instruction body from SKILL.md.

    The frontmatter is stripped — only the instruction body is returned.
    """
    with open(skill.skill_file, "r", encoding="utf-8") as f:
        content = f.read()

    _frontmatter, body = parse_skill_file(content)
    return body


def load_resource(skill: SkillMetadata, relative_path: str) -> str | bytes:
    """Load a Tier 3 resource from the skill's directory.

    Args:
        skill: The skill metadata.
        relative_path: Path relative to the skill directory.

    Returns:
        File contents as str (text files) or bytes (binary files).

    Raises:
        FileNotFoundError: If the resource doesn't exist.
        ValueError: If the path escapes the skill directory.
    """
    full_path = os.path.normpath(os.path.join(skill.skill_dir, relative_path))

    if not full_path.startswith(os.path.normpath(skill.skill_dir)):
        raise ValueError(
            f"Path traversal detected: {relative_path} escapes {skill.skill_dir}"
        )

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(full_path, "rb") as f:
            return f.read()


def list_resources(skill: SkillMetadata) -> list[str]:
    """List all Tier 3 resources available in the skill directory.

    Returns relative paths from the skill directory root.
    Excludes SKILL.md itself.
    """
    resources: list[str] = []
    for root, _dirs, files in os.walk(skill.skill_dir):
        for fname in files:
            if fname == "SKILL.md":
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, skill.skill_dir)
            resources.append(rel)
    return sorted(resources)
'''

    def render_brief_packet_py(self) -> str:
        """Render the brief_packet.py module for dynamic system prompt assembly."""
        return '''\
"""Brief Packet — dynamic system prompt assembly (Principle 3).

Assembles the system prompt from independent identity layer files,
enabling modular updates without touching agent code.

Includes runtime context injection and assembly logging for
debugging and audit purposes.
"""

from __future__ import annotations

import datetime
import logging
import os
import platform
import sys
from pathlib import Path

IDENTITY_DIR = Path(__file__).parent / "identity"

LAYER_FILES: dict[str, str] = {
    "rules": "RULES.md",
    "personality": "PERSONALITY.md",
    "identity": "IDENTITY.md",
    "tools": "TOOLS.md",
    "user": "USER.md",
    "memory": "MEMORY.md",
    "bootstrap": "BOOTSTRAP.md",
    "duties": "DUTIES.md",
}

MINIMAL_LAYERS = ("rules", "tools")

MAX_CHARS = 20_000

logger = logging.getLogger("brief_packet")


def _truncate(text: str, max_chars: int = MAX_CHARS) -> str:
    """Truncate text with 70/20 head/tail split, preserving context."""
    if len(text) <= max_chars:
        return text
    head_size = int(max_chars * 0.7)
    tail_size = int(max_chars * 0.2)
    notice = "\\n\\n[... content truncated for context window ...]\\n\\n"
    return text[:head_size] + notice + text[-tail_size:]


def _read_layer(filename: str) -> str:
    """Read a single identity layer file, applying truncation."""
    path = IDENTITY_DIR / filename
    if not path.exists():
        return ""
    text = path.read_text().strip()
    return _truncate(text)


def _build_runtime_context() -> str:
    """Build runtime context metadata for prompt injection.

    Gathers timestamp, host, OS, Python version, and model info
    from config.yaml (if available).
    """
    lines = [
        "# RUNTIME CONTEXT",
        "",
        f"- timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        f"- hostname: {platform.node()}",
        f"- os: {platform.system()} {platform.release()}",
        f"- python: {sys.version.split()[0]}",
    ]

    # Read model info from config.yaml if available
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        try:
            import yaml  # noqa: PLC0415

            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            model_cfg = cfg.get("model", {})
            if isinstance(model_cfg, dict):
                model_id = model_cfg.get("model_id", "")
                provider = model_cfg.get("provider", "")
                if model_id:
                    lines.append(f"- model: {model_id}")
                if provider:
                    lines.append(f"- provider: {provider}")
        except Exception:
            pass  # Config parsing is best-effort

    # Include CWD for workspace awareness
    lines.append(f"- cwd: {os.getcwd()}")

    return "\\n".join(lines)


def _log_assembly(
    mode: str,
    loaded: list[str],
    missing: list[str],
    total_chars: int,
) -> None:
    """Log which layers were loaded for debugging and audit."""
    logger.debug(
        "brief_packet assembled | mode=%s | loaded=%s | missing=%s | total_chars=%d",
        mode,
        ",".join(loaded) or "(none)",
        ",".join(missing) or "(none)",
        total_chars,
    )


def assemble_brief_packet(mode: str = "full") -> str:
    """Assemble the system prompt from identity layer files.

    Args:
        mode: "full" loads all layers + runtime context,
              "minimal" loads RULES + TOOLS only (no runtime context),
              "none" returns empty string.

    Returns:
        Assembled system prompt string.
    """
    if mode == "none":
        logger.debug("brief_packet assembled | mode=none | skipped")
        return ""

    if mode == "minimal":
        layers = MINIMAL_LAYERS
    else:
        layers = tuple(LAYER_FILES.keys())

    sections: list[str] = []
    loaded: list[str] = []
    missing: list[str] = []

    for layer_name in layers:
        filename = LAYER_FILES.get(layer_name)
        if filename is None:
            continue
        content = _read_layer(filename)
        if content:
            sections.append(f"# {layer_name.upper()}\\n\\n{content}")
            loaded.append(layer_name)
        else:
            missing.append(layer_name)

    # Append runtime context in "full" mode only
    if mode == "full":
        sections.append(_build_runtime_context())

    result = "\\n\\n---\\n\\n".join(sections)

    _log_assembly(mode, loaded, missing, len(result))

    return result
'''

    def render_identity_access_py(self) -> str:
        """Render identity_access.py — access controls, backups, and audit for identity layers."""
        return '''\
"""Identity Access — layer-level access control, backup, and versioning (Principle 3).

Provides:
- Per-layer access control (agent-writable vs admin-only)
- Timestamped backup before modifications
- Audit trail for all layer changes
- Backup listing and restore capability

Access levels can be overridden in config.yaml under identity.access_control.
"""

from __future__ import annotations

import datetime
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("identity_access")

IDENTITY_DIR = Path(__file__).parent / "identity"
BACKUPS_DIR = IDENTITY_DIR / ".backups"
MODIFICATIONS_LOG = IDENTITY_DIR / ".modifications.log"

# Default access levels — agent-writable layers vs admin-only layers.
# Override via config.yaml identity.access_control section.
DEFAULT_ACCESS_LEVELS: dict[str, str] = {
    "RULES.md": "admin",
    "PERSONALITY.md": "agent",
    "IDENTITY.md": "admin",
    "TOOLS.md": "agent",
    "USER.md": "agent",
    "MEMORY.md": "agent",
    "BOOTSTRAP.md": "admin",
    "DUTIES.md": "admin",
}

MAX_BACKUPS = 10


def _load_access_levels() -> dict[str, str]:
    """Load access levels from config.yaml, falling back to defaults."""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        try:
            import yaml  # noqa: PLC0415

            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            overrides = cfg.get("identity", {}).get("access_control", {})
            if isinstance(overrides, dict):
                merged = dict(DEFAULT_ACCESS_LEVELS)
                merged.update(overrides)
                return merged
        except Exception:
            pass  # Config parsing is best-effort
    return dict(DEFAULT_ACCESS_LEVELS)


def can_modify(filename: str, caller: str = "agent") -> bool:
    """Check whether *caller* has permission to modify *filename*.

    Args:
        filename: Identity layer filename (e.g. ``"PERSONALITY.md"``).
        caller: ``"agent"`` or ``"admin"``.

    Returns:
        ``True`` if the caller is allowed to modify the file.
    """
    levels = _load_access_levels()
    required_level = levels.get(filename, "admin")
    if caller == "admin":
        return True
    return required_level == "agent"


def modify_layer(
    filename: str,
    new_content: str,
    caller: str = "agent",
    reason: str = "",
) -> bool:
    """Modify an identity layer file with access control, backup, and audit.

    Args:
        filename: Identity layer filename (e.g. ``"MEMORY.md"``).
        new_content: Replacement content for the file.
        caller: ``"agent"`` or ``"admin"``.
        reason: Human-readable reason for the change (written to audit log).

    Returns:
        ``True`` if the modification succeeded.

    Raises:
        PermissionError: If the caller lacks permission.
        FileNotFoundError: If the identity directory is missing.
    """
    if not can_modify(filename, caller):
        raise PermissionError(
            f"{caller!r} cannot modify {filename!r} (requires admin access)"
        )

    file_path = IDENTITY_DIR / filename
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")

    # Create backup if file exists
    if file_path.exists():
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        stem = file_path.stem
        suffix = file_path.suffix
        backup_name = f"{stem}_{timestamp}{suffix}"
        backup_path = BACKUPS_DIR / backup_name
        shutil.copy2(file_path, backup_path)
        logger.debug("Backed up %s → %s", filename, backup_name)

        # Prune old backups beyond MAX_BACKUPS
        _prune_backups(filename)

    # Write new content
    file_path.write_text(new_content)

    # Append to audit log
    log_line = f"{now.isoformat()} | {caller} | {filename} | {reason}\\n"
    with open(MODIFICATIONS_LOG, "a") as f:
        f.write(log_line)

    logger.info("Modified %s by %s: %s", filename, caller, reason or "(no reason)")
    return True


def _prune_backups(filename: str) -> None:
    """Keep only the most recent MAX_BACKUPS backups for a given layer file."""
    stem = Path(filename).stem
    backups = sorted(BACKUPS_DIR.glob(f"{stem}_*"), reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink(missing_ok=True)


def list_backups(filename: str) -> list[Path]:
    """Return available backups for *filename*, newest first.

    Args:
        filename: Identity layer filename (e.g. ``"RULES.md"``).

    Returns:
        List of backup file paths sorted by most recent first.
    """
    stem = Path(filename).stem
    if not BACKUPS_DIR.exists():
        return []
    return sorted(BACKUPS_DIR.glob(f"{stem}_*"), reverse=True)


def restore_backup(filename: str, backup_path: Path) -> bool:
    """Restore a specific backup version of an identity layer file.

    Args:
        filename: Identity layer filename to restore.
        backup_path: Path to the backup file to restore from.

    Returns:
        ``True`` if the restore succeeded.

    Raises:
        FileNotFoundError: If the backup file doesn\'t exist.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    file_path = IDENTITY_DIR / filename
    shutil.copy2(backup_path, file_path)

    now = datetime.datetime.now(datetime.timezone.utc)
    log_line = f"{now.isoformat()} | restore | {filename} | from {backup_path.name}\\n"
    with open(MODIFICATIONS_LOG, "a") as f:
        f.write(log_line)

    logger.info("Restored %s from %s", filename, backup_path.name)
    return True
'''

    def render_identity_rules(self) -> str:
        """Render RULES.md based on selected focus areas."""
        sections = ["# Operational Rules\n"]

        focus = self.config.identity.rules_focus

        if "safety" in focus:
            sections.append("""\
## Safety Constraints

- Never generate content that could cause harm to users or systems
- Refuse requests that violate ethical guidelines — explain why
- Validate all external inputs before processing
- Sanitise outputs to prevent injection attacks
""")

        if "tool_governance" in focus:
            sections.append("""\
## Tool Governance

- Only use tools permitted by the active profile in `tool_policy.py`
- Deny-wins-over-allow: denied tools are always blocked, regardless of profile
- Request user confirmation before executing destructive operations
- Log every tool invocation with parameters and results
- Respect sub-agent restrictions — sub-agents cannot access orchestration tools
- Review `config.yaml` tools section for current permissions
""")

        if "data_privacy" in focus:
            sections.append("""\
## Data Privacy

- Never log or store personally identifiable information (PII)
- Redact sensitive data from responses and logs
- Follow data minimisation principles — collect only what is needed
- Respect data retention policies and deletion requests
""")

        if "output_quality" in focus:
            sections.append("""\
## Output Quality

- Provide structured, evidence-based responses
- Cite sources and data when making claims
- Use clear formatting — headings, lists, code blocks as appropriate
- Acknowledge uncertainty explicitly rather than guessing
""")

        if "error_handling" in focus:
            sections.append("""\
## Error Handling

- Fail gracefully with informative error messages
- Provide actionable recovery suggestions when errors occur
- Log errors with full context for debugging
- Never expose internal stack traces or system details to users
""")

        return "\n".join(sections)

    def render_identity_personality(self) -> str:
        """Render PERSONALITY.md based on selected preset."""
        preset = self.config.identity.personality_preset

        if preset == "professional":
            return """\
# Personality

## Voice & Tone
- Professional and precise
- Business-appropriate language
- Confident but not arrogant

## Communication Style
- Lead with the key insight or answer
- Use structured formats for complex information
- Be thorough but respect the user's time

## Values
- Accuracy over speed
- Clarity over cleverness
- Helpfulness over brevity
"""

        if preset == "friendly":
            return """\
# Personality

## Voice & Tone
- Warm and conversational
- Approachable and encouraging
- Uses natural language, avoids jargon when possible

## Communication Style
- Start with acknowledgement of the user's request
- Explain concepts in accessible terms
- Offer next steps and suggestions proactively

## Values
- User comfort and understanding
- Patience with all skill levels
- Building confidence through clear explanations
"""

        if preset == "technical":
            return """\
# Personality

## Voice & Tone
- Detailed and specification-oriented
- Precise technical terminology
- Matter-of-fact and exact

## Communication Style
- Include relevant technical details and references
- Use code examples and specifications liberally
- Provide rationale for technical decisions

## Values
- Technical correctness above all
- Completeness of information
- Reproducibility of instructions
"""

        if preset == "concise":
            return """\
# Personality

## Voice & Tone
- Minimal and direct
- No filler words or pleasantries
- Every word earns its place

## Communication Style
- Answer first, elaborate only if asked
- Use bullet points over paragraphs
- Code over prose when applicable

## Values
- Brevity is respect for the user's time
- Signal over noise
- Action over discussion
"""

        # custom — blank template
        return """\
# Personality

## Voice & Tone
- [Define your agent's voice here]

## Communication Style
- [Define how your agent communicates]

## Values
- [Define what your agent prioritises]
"""

    def render_identity_identity(self) -> str:
        """Render IDENTITY.md using project name and description."""
        return f"""\
# Public Identity

## Name
{self.config.project_name}

## Bio
{self.config.description}

## Tagline
A production AI agent built with {self.framework_display_name}.

## Version
0.1.0
"""

    def render_identity_tools(self) -> str:
        """Render TOOLS.md with generic tool guidance.

        Framework-specific templates override this method.
        """
        return """\
# Tool Guidance

## General Principles
- Use tools only when reasoning alone is insufficient
- Prefer the most specific tool available for the task
- Validate tool inputs before invocation
- Handle tool errors gracefully — report and suggest alternatives

## Tool Loop Pattern
1. **Reason** — determine if a tool is needed and which one
2. **Act** — invoke the tool with validated parameters
3. **Observe** — inspect the result for errors or unexpected output
4. **Repeat** — continue until the task is complete or a limit is reached

## Limits
- Maximum tool invocations per turn: 10
- Timeout per tool call: 30 seconds
- Always respect tool permission boundaries
"""

    def render_identity_user(self) -> str:
        """Render USER.md placeholder."""
        return """\
# User Context

## Preferences
- [Learned preferences will be recorded here at runtime]

## Communication Style
- [Observed user communication preferences]

## Timezone
- [User timezone if known]

## Notes
- This file is updated during interactions to personalise responses
"""

    def render_identity_memory(self) -> str:
        """Render MEMORY.md with structured template."""
        return """\
# Persistent Memory

## Format
Each entry follows: `YYYY-MM-DD — [topic] — [observation]`

## Entries
<!-- New entries are appended below this line -->
"""

    def render_identity_bootstrap(self) -> str:
        """Render BOOTSTRAP.md with one-time setup checklist."""
        return """\
# Bootstrap — One-Time Setup

## Checklist
- [ ] Verify config.yaml settings match your environment
- [ ] Test model connection: `python agent.py "hello"`
- [ ] Review identity layer files and customise as needed
- [ ] Set up environment variables (see .env.example)
- [ ] Run smoke tests: `make test`

## Post-Setup
Once all checks pass, this file can be cleared or archived.
The agent will skip loading BOOTSTRAP.md once it is empty.
"""

    def render_identity_duties(self) -> str:
        """Render DUTIES.md placeholder with example periodic tasks."""
        return """\
# Scheduled Duties

## Format
```
schedule: <cron expression or interval>
task: <description>
enabled: true|false
```

## Example Duties
```
schedule: "0 9 * * 1"
task: "Generate weekly summary of unresolved issues"
enabled: false
```

```
schedule: "every 4 hours"
task: "Check for stale conversations and prompt follow-up"
enabled: false
```

## Notes
- Duties are only active when `enabled: true`
- This file is a template — modify schedules to match your needs
"""
