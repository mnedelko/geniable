"""Strands template — uses strands-agents SDK patterns.

Overrides sections 1, 3, 4, 5, 6, 8 with Strands-specific patterns:
Model-first approach, @tool decorator, Agent() constructor.
"""

from __future__ import annotations

from cli.scaffold.base import BaseTemplate, _principle_comments


class StrandsTemplate(BaseTemplate):
    """Strands agent template."""

    @property
    def framework_display_name(self) -> str:
        return "Strands Agents"

    @property
    def framework_dependencies(self) -> list[str]:
        return [
            "strands-agents>=0.1.0",
            "strands-agents-tools>=0.1.0",
        ]

    def render_identity_tools(self) -> str:
        """Render Strands-specific TOOLS.md."""
        return """\
# Tool Guidance — Strands Agents

## @tool Decorator
- Use the `@tool` decorator to register functions as agent tools
- The function docstring becomes the tool description for the model
- Type hints on parameters are used to generate the tool schema

## Tool Function Signatures
- Tool functions should have clear, typed parameters
- Return strings or serialisable objects — the agent formats the response
- Use descriptive parameter names — the model sees them

## Agent Tool List
- Pass tools to `Agent(tools=[tool1, tool2])` during construction
- Tools are available to the model in every conversation turn
- Order does not matter — the model selects tools by description

## Tool Result Handling
- Strands automatically wraps tool returns as tool results
- Errors raised in tools are caught and reported to the model
- Use structured returns (dicts, dataclasses) for complex results

## Limits
- Maximum tool invocations per turn: 10
- Timeout per tool call: 30 seconds
- Always respect tool permission boundaries
"""

    def render_section_1_imports(self) -> str:
        return f"""\
# =============================================================================
# 1. IMPORTS
# =============================================================================
{_principle_comments(1)}
import json
import logging
import sys
"""

    def render_section_3_client(self) -> str:
        has_fallbacks = bool(self.config.fallback_models)

        if not has_fallbacks:
            return f"""\
# =============================================================================
# 3. MODEL CONFIGURATION (with resilience)
# =============================================================================
{_principle_comments(3)}
# Strands manages the model client internally — no separate client needed.
# The model is configured when creating the Agent instance (Section 6).

_model = None


def _create_model_for_provider(provider: str, model_id: str):
    \"\"\"Create a Strands model for the given provider.\"\"\"
    if provider == "bedrock":
        from strands.models.bedrock import BedrockModel
        return BedrockModel(
            model_id=model_id, region_name=CONFIG.region,
            temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens,
        )
    elif provider == "openai":
        from strands.models.openai import OpenAIModel
        return OpenAIModel(model_id=model_id, temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens)
    elif provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(model_id=model_id, temperature=CONFIG.temperature)
    else:
        raise ValueError(f"Unknown provider: {{provider}}")


def get_model():
    \"\"\"Get or create the Strands model (lazy init).\"\"\"
    global _model
    if _model is None:
        _model = _create_model_for_provider(CONFIG.provider, CONFIG.model_id)
    return _model
"""

        return f"""\
# =============================================================================
# 3. MODEL CONFIGURATION (with resilience — fallback cascades + auth rotation)
# =============================================================================
{_principle_comments(3)}
from resilience import (
    CooldownEngine, CredentialRotator, HealthStore,
    ModelCandidate, ModelFallbackRunner, ProfileHealthRecord,
)


def _create_model_for_provider(provider: str, model_id: str):
    \"\"\"Create a Strands model for the given provider.\"\"\"
    if provider == "bedrock":
        from strands.models.bedrock import BedrockModel
        return BedrockModel(
            model_id=model_id, region_name=CONFIG.region,
            temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens,
        )
    elif provider == "openai":
        from strands.models.openai import OpenAIModel
        return OpenAIModel(model_id=model_id, temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens)
    elif provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(model_id=model_id, temperature=CONFIG.temperature)
    else:
        raise ValueError(f"Unknown provider: {{provider}}")


def _build_fallback_runner() -> ModelFallbackRunner:
    \"\"\"Build ModelFallbackRunner from config.\"\"\"
    cooldown_cfg = getattr(CONFIG, "cooldown_config", {{}})
    engine = CooldownEngine(
        transient_tiers=cooldown_cfg.get("transient_tiers"),
        billing_tiers=cooldown_cfg.get("billing_tiers"),
    )

    health_store = HealthStore()
    existing_records = health_store.load()
    records_by_id = {{r.profile_id: r for r in existing_records}}

    def _get_or_create_profile(profile_id: str) -> ProfileHealthRecord:
        if profile_id in records_by_id:
            return records_by_id[profile_id]
        record = ProfileHealthRecord(profile_id=profile_id)
        records_by_id[profile_id] = record
        return record

    primary = ModelCandidate(
        provider=CONFIG.provider,
        model_id=CONFIG.model_id,
        profiles=[_get_or_create_profile(f"{{CONFIG.provider}}/default")],
    )

    fallbacks = []
    for fb in getattr(CONFIG, "fallbacks", []):
        fallbacks.append(ModelCandidate(
            provider=fb["provider"],
            model_id=fb["model_id"],
            profiles=[_get_or_create_profile(f"{{fb['provider']}}/default")],
        ))

    return ModelFallbackRunner(primary=primary, fallbacks=fallbacks, cooldown_engine=engine)


_runner: ModelFallbackRunner | None = None


def get_model():
    \"\"\"Get Strands model with resilience — fallback cascade + auth rotation.\"\"\"
    global _runner
    if _runner is None:
        _runner = _build_fallback_runner()

    def invoke_fn(provider, model_id, profile):
        return _create_model_for_provider(provider, model_id)

    return _runner.run(invoke_fn)
"""

    def render_section_4_state(self) -> str:
        return f"""\
# =============================================================================
# 4. STATE DEFINITION
# =============================================================================
{_principle_comments(4)}
from dataclasses import dataclass, field


@dataclass
class AgentState:
    \"\"\"Agent state — simpler than LangGraph, just a data container.\"\"\"

    query: str = ""
    context: dict = field(default_factory=dict)
    response: str = ""
    error: str | None = None
"""

    def render_section_5_worker(self) -> str:
        if self.config.tools.enabled:
            return f"""\
# =============================================================================
# 5. TOOL FUNCTIONS
# =============================================================================
{_principle_comments(5)}
from tools import get_permitted_tools

# Tools are discovered from tools/ directory and filtered by tool_policy.
# The permitted tools are passed to Agent(tools=[...]) in Section 6.
"""

        return f"""\
# =============================================================================
# 5. TOOL FUNCTIONS
# =============================================================================
{_principle_comments(5)}

def process_query_tool(query: str) -> str:
    \"\"\"Process a user query and return a response.

    Args:
        query: The user query to process.

    Returns:
        Processed response string.
    \"\"\"
    # This is a placeholder tool — add your domain logic here
    return f"Processed: {{query}}"
"""

    def render_section_6_graph(self) -> str:
        if self.config.tools.enabled:
            return f"""\
# =============================================================================
# 6. AGENT CONSTRUCTION
# =============================================================================
{_principle_comments(6)}

def create_agent():
    \"\"\"Create the Strands agent with discovered tools and governance.\"\"\"
    from strands import Agent

    system_prompt = load_system_prompt()
    model = get_model()

    # Tool Governance (Principle 9): discover and filter tools from tools/ directory
    permitted = get_permitted_tools()
    if permitted:
        permitted_tools = [t.as_function() for t in permitted]
    else:
        log_invocation("tools", "No tools available — running in inference-only mode")
        permitted_tools = []

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=permitted_tools,
    )
    return agent
"""

        return f"""\
# =============================================================================
# 6. AGENT CONSTRUCTION
# =============================================================================
{_principle_comments(6)}

def create_agent():
    \"\"\"Create the Strands agent with configured model and tools.\"\"\"
    from strands import Agent
    from tool_policy import filter_tools

    system_prompt = load_system_prompt()
    model = get_model()

    # Tool Governance (Principle 9): filter tools through policy
    all_tools = [process_query_tool]
    tool_names = [t.__name__ for t in all_tools]
    permitted_names = filter_tools(tool_names)
    permitted_tools = [t for t in all_tools if t.__name__ in permitted_names]

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=permitted_tools,
    )
    return agent
"""

    def render_section_8_entrypoint(self) -> str:
        langsmith_import = ""
        langsmith_decorator = ""
        if self.config.langsmith.enabled:
            langsmith_import = "from langsmith import traceable\n\n"
            langsmith_decorator = f'@traceable(name="{self.config.project_name}")\n'
        session_wrapper = self._render_session_wrapper()
        main_block = self._render_main_block()
        return f"""\
# =============================================================================
# 8. ENTRY POINT
# =============================================================================
{_principle_comments(8)}{langsmith_import}{langsmith_decorator}def run_agent(query: str, context: dict | None = None) -> str:
    \"\"\"Run the agent with a query string.

    Args:
        query: The input query to process.
        context: Optional context dictionary.

    Returns:
        Agent response string.

    Raises:
        RuntimeError: If the agent encounters an error.
    \"\"\"
    try:
        agent = create_agent()
        response = agent(query)
        return str(response)
    except Exception as e:
        raise RuntimeError(f"Agent invocation failed: {{e!s}}") from e

{session_wrapper}
{main_block}
"""
