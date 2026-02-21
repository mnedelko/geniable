"""Pi template — based on Pi agent framework patterns.

Overrides sections 1, 3, 4, 5, 6, 8 with Pi-specific patterns:
Declarative agent config, workspace/session management, gateway-style execution.
Based on patterns from AGENT-ORCHESTRATION.md.
"""

from __future__ import annotations

from cli.scaffold.base import BaseTemplate, _principle_comments


class PiTemplate(BaseTemplate):
    """Pi framework agent template."""

    @property
    def framework_display_name(self) -> str:
        return "Pi Agent Framework"

    @property
    def framework_dependencies(self) -> list[str]:
        return [
            "litellm>=1.0.0",
        ]

    def render_identity_tools(self) -> str:
        """Render Pi-specific TOOLS.md."""
        return """\
# Tool Guidance — Pi Agent Framework

## register_tool() Decorator
- Use `@register_tool("name", "description")` to register tool functions
- The name and description are passed to the model for tool selection
- Tool functions are stored in `TOOL_REGISTRY` for runtime lookup

## TOOL_REGISTRY Management
- All registered tools are available via `TOOL_REGISTRY` dict
- Access tools by name: `TOOL_REGISTRY["tool_name"]["function"]`
- The registry is populated at import time via decorators

## Declarative Tool Configuration
- Tools are listed in `create_agent_config()` by registry key
- The agent config controls which tools are active per session
- Use config.yaml `tools.profile` to set access levels (minimal/coding/full)

## Tool Invocation
- Pi invokes tools through the provider abstraction layer
- Tool results are returned to the model as structured responses
- Errors are caught and formatted as error responses

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
from typing import Any
"""

    def render_section_3_client(self) -> str:
        has_fallbacks = bool(self.config.fallback_models)

        if not has_fallbacks:
            return f"""\
# =============================================================================
# 3. MODEL CLIENT (via provider abstraction with resilience)
# =============================================================================
{_principle_comments(3)}
# Pi uses a provider abstraction layer — the model is accessed through
# a unified interface that supports fallback cascades (Principle 5).

_client = None


def get_client():
    \"\"\"Get or create the model client (lazy init).\"\"\"
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("bedrock-runtime", region_name=CONFIG.region)
    return _client


def _invoke_bedrock(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke a Bedrock model.\"\"\"
    client = get_client()
    body = json.dumps({{
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": CONFIG.max_tokens,
        "temperature": CONFIG.temperature,
        "system": system_prompt,
        "messages": [{{"role": "user", "content": user_message}}],
    }})
    response = client.invoke_model(
        modelId=model_id, body=body,
        contentType="application/json", accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def _invoke_openai(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke an OpenAI model.\"\"\"
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {{"role": "system", "content": system_prompt}},
            {{"role": "user", "content": user_message}},
        ],
        max_tokens=CONFIG.max_tokens,
        temperature=CONFIG.temperature,
    )
    return response.choices[0].message.content or ""


def _invoke_google(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke a Google AI model.\"\"\"
    from google import genai
    client = genai.Client()
    response = client.models.generate_content(
        model=model_id,
        contents=f"{{system_prompt}}\\n\\n{{user_message}}",
    )
    return response.text or ""


def _invoke_ollama(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke an Ollama model.\"\"\"
    import ollama
    response = ollama.chat(
        model=model_id,
        messages=[
            {{"role": "system", "content": system_prompt}},
            {{"role": "user", "content": user_message}},
        ],
    )
    return response["message"]["content"]


def invoke_model(system_prompt: str, user_message: str) -> str:
    \"\"\"Invoke the model through the provider abstraction.

    Args:
        system_prompt: System instructions for the model.
        user_message: User input to process.

    Returns:
        Model response text.
    \"\"\"
    provider = CONFIG.provider
    if provider == "bedrock":
        return _invoke_bedrock(system_prompt, user_message, CONFIG.model_id)
    elif provider == "openai":
        return _invoke_openai(system_prompt, user_message, CONFIG.model_id)
    elif provider == "google":
        return _invoke_google(system_prompt, user_message, CONFIG.model_id)
    elif provider == "ollama":
        return _invoke_ollama(system_prompt, user_message, CONFIG.model_id)
    else:
        raise ValueError(f"Unknown provider: {{provider}}")
"""

        return f"""\
# =============================================================================
# 3. MODEL CLIENT (with resilience — fallback cascades + auth rotation)
# =============================================================================
{_principle_comments(3)}
from resilience import (
    CooldownEngine, CredentialRotator, HealthStore,
    ModelCandidate, ModelFallbackRunner, ProfileHealthRecord,
)


def _invoke_bedrock(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke a Bedrock model.\"\"\"
    import boto3
    client = boto3.client("bedrock-runtime", region_name=CONFIG.region)
    body = json.dumps({{
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": CONFIG.max_tokens,
        "temperature": CONFIG.temperature,
        "system": system_prompt,
        "messages": [{{"role": "user", "content": user_message}}],
    }})
    response = client.invoke_model(
        modelId=model_id, body=body,
        contentType="application/json", accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def _invoke_openai(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke an OpenAI model.\"\"\"
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {{"role": "system", "content": system_prompt}},
            {{"role": "user", "content": user_message}},
        ],
        max_tokens=CONFIG.max_tokens,
        temperature=CONFIG.temperature,
    )
    return response.choices[0].message.content or ""


def _invoke_google(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke a Google AI model.\"\"\"
    from google import genai
    client = genai.Client()
    response = client.models.generate_content(
        model=model_id,
        contents=f"{{system_prompt}}\\n\\n{{user_message}}",
    )
    return response.text or ""


def _invoke_ollama(system_prompt: str, user_message: str, model_id: str) -> str:
    \"\"\"Invoke an Ollama model.\"\"\"
    import ollama
    response = ollama.chat(
        model=model_id,
        messages=[
            {{"role": "system", "content": system_prompt}},
            {{"role": "user", "content": user_message}},
        ],
    )
    return response["message"]["content"]


_INVOKE_MAP = {{
    "bedrock": _invoke_bedrock,
    "openai": _invoke_openai,
    "google": _invoke_google,
    "ollama": _invoke_ollama,
}}


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


def invoke_model(system_prompt: str, user_message: str) -> str:
    \"\"\"Invoke model through resilience layer — fallback cascade + auth rotation.

    Args:
        system_prompt: System instructions for the model.
        user_message: User input to process.

    Returns:
        Model response text.
    \"\"\"
    global _runner
    if _runner is None:
        _runner = _build_fallback_runner()

    def invoke_fn(provider, model_id, profile):
        fn = _INVOKE_MAP.get(provider)
        if fn is None:
            raise ValueError(f"Unknown provider: {{provider}}")
        return fn(system_prompt, user_message, model_id)

    return _runner.run(invoke_fn)
"""

    def render_section_4_state(self) -> str:
        return f"""\
# =============================================================================
# 4. STATE DEFINITION
# =============================================================================
{_principle_comments(4)}
# Pi manages state through workspace files and session persistence.
# This is a minimal in-memory state for single invocations.


class AgentState:
    \"\"\"Session-managed agent state.

    In a full Pi deployment, state is persisted to workspace files
    and session JSONL logs (Principle 10).
    \"\"\"

    def __init__(self) -> None:
        self.query: str = ""
        self.context: dict[str, Any] = {{}}
        self.response: str = ""
        self.error: str | None = None
        self.tool_calls: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {{
            "query": self.query,
            "context": self.context,
            "response": self.response,
            "error": self.error,
            "tool_calls": self.tool_calls,
        }}
"""

    def render_section_5_worker(self) -> str:
        return f"""\
# =============================================================================
# 5. TOOL FUNCTIONS
# =============================================================================
{_principle_comments(5)}
# Pi registers tools declaratively. Each tool function is registered
# with the agent and made available to the model's tool loop.

TOOL_REGISTRY: dict[str, Any] = {{}}


def register_tool(name: str, description: str):
    \"\"\"Decorator to register a tool function with the agent.\"\"\"
    def decorator(func):
        TOOL_REGISTRY[name] = {{
            "function": func,
            "name": name,
            "description": description,
        }}
        return func
    return decorator


@register_tool("process_query", "Process a user query and return a response")
def process_query(query: str) -> str:
    \"\"\"Process a user query.

    Args:
        query: The user query to process.

    Returns:
        Processed response string.
    \"\"\"
    return f"Processed: {{query}}"
"""

    def render_section_6_graph(self) -> str:
        return f"""\
# =============================================================================
# 6. AGENT CONSTRUCTION
# =============================================================================
{_principle_comments(6)}
# Pi uses declarative agent configuration. The agent execution loop
# is managed by the framework — you configure, Pi orchestrates.


def create_agent_config() -> dict[str, Any]:
    \"\"\"Create the declarative agent configuration.

    Returns a config dict that Pi uses to set up the agent's model,
    tools, workspace, and execution parameters.
    \"\"\"
    from tool_policy import filter_tools

    # Tool Governance (Principle 9): filter tools through policy
    all_tool_names = list(TOOL_REGISTRY.keys())
    permitted_names = filter_tools(all_tool_names)

    return {{
        "model": {{
            "primary": CONFIG.model_id,
            "region": CONFIG.region,
            "max_tokens": CONFIG.max_tokens,
            "temperature": CONFIG.temperature,
        }},
        "tools": permitted_names,
        "workspace": str(BASE_DIR),
        "operational": {{
            "max_iterations": 10,
            "timeout_seconds": 120,
        }},
    }}
"""

    def render_section_8_entrypoint(self) -> str:
        langsmith_import = ""
        langsmith_decorator = ""
        if self.config.langsmith.enabled:
            langsmith_import = "from langsmith import traceable\n\n"
            langsmith_decorator = f'@traceable(name="{self.config.project_name}")\n'
        main_block = self._render_main_block()
        return f"""\
# =============================================================================
# 8. ENTRY POINT
# =============================================================================
{_principle_comments(8)}{langsmith_import}{langsmith_decorator}def run_agent(query: str, context: dict | None = None) -> str:
    \"\"\"Run the agent with a query string.

    In a full Pi deployment, this would be invoked by the gateway
    when a message arrives (Principle 1: Serverless Agency).

    Args:
        query: The input query to process.
        context: Optional context dictionary.

    Returns:
        Agent response string.

    Raises:
        RuntimeError: If the agent encounters an error.
    \"\"\"
    state = AgentState()
    state.query = query
    state.context = context or {{}}

    try:
        system_prompt = load_system_prompt()
        state.response = invoke_model(system_prompt, query)
    except FileNotFoundError as e:
        raise RuntimeError(f"Prompt not found: {{e}}") from e
    except Exception as e:
        raise RuntimeError(f"Agent invocation failed: {{e!s}}") from e

    log_invocation("run_agent", f"query_length={{len(query)}}")
    return state.response


{main_block}
"""
