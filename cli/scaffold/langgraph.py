"""LangGraph template — closest to the reference agent.py.

Overrides sections 1, 3, 4, 5, 6, 8 with LangGraph-specific patterns:
StateGraph builder, TypedDict state, ChatBedrockConverse client.
"""

from __future__ import annotations

from cli.scaffold.base import BaseTemplate, _principle_comments


class LangGraphTemplate(BaseTemplate):
    """LangGraph agent template."""

    @property
    def framework_display_name(self) -> str:
        return "LangGraph"

    @property
    def framework_dependencies(self) -> list[str]:
        return [
            "langgraph>=0.2.0",
            "langchain-aws>=0.2.0",
            "langchain-core>=0.3.0",
        ]

    def render_identity_tools(self) -> str:
        """Render LangGraph-specific TOOLS.md."""
        return """\
# Tool Guidance — LangGraph

## StateGraph Tool Nodes
- Define tools as graph nodes that receive and return `AgentState`
- Use `add_node("tool_name", tool_function)` to register tool nodes
- Connect tool nodes with `add_edge()` or `add_conditional_edges()`

## LangChain Tool Binding
- Bind tools to the LLM with `llm.bind_tools([tool1, tool2])`
- Tools must have docstrings — LangChain uses them as tool descriptions
- Use `@tool` decorator from `langchain_core.tools` for simple tools

## State Management in Tools
- Tool functions receive the full `AgentState` TypedDict
- Return a dict with only the keys you want to update
- Never mutate the input state directly — return new values

## ToolMessage Response Format
- When a tool call is made, respond with `ToolMessage(content=result)`
- Include `tool_call_id` to match the response to the invocation
- Return structured JSON when the result has multiple fields

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
            # Single provider — simple client, still imports resilience for future use
            return f"""\
# =============================================================================
# 3. LLM CLIENT (lazy initialization with resilience)
# =============================================================================
{_principle_comments(3)}
_llm = None


def _create_llm_for_provider(provider: str, model_id: str):
    \"\"\"Create an LLM client for the given provider.\"\"\"
    if provider == "bedrock":
        import boto3
        from langchain_aws import ChatBedrockConverse
        bedrock_client = boto3.client("bedrock-runtime", region_name=CONFIG.region)
        return ChatBedrockConverse(
            model_id=model_id, client=bedrock_client,
            temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_id, temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_id, temperature=CONFIG.temperature, max_output_tokens=CONFIG.max_tokens)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_id, temperature=CONFIG.temperature)
    else:
        raise ValueError(f"Unknown provider: {{provider}}")


def get_llm():
    \"\"\"Get or create the LLM client (lazy init for faster cold starts).\"\"\"
    global _llm
    if _llm is None:
        _llm = _create_llm_for_provider(CONFIG.provider, CONFIG.model_id)
    return _llm
"""

        # Multi-provider with resilience
        return f"""\
# =============================================================================
# 3. LLM CLIENT (with resilience — fallback cascades + auth rotation)
# =============================================================================
{_principle_comments(3)}
from resilience import (
    CooldownEngine, CredentialRotator, HealthStore,
    ModelCandidate, ModelFallbackRunner, ProfileHealthRecord,
)


def _create_llm_for_provider(provider: str, model_id: str):
    \"\"\"Create an LLM client for the given provider.\"\"\"
    if provider == "bedrock":
        import boto3
        from langchain_aws import ChatBedrockConverse
        bedrock_client = boto3.client("bedrock-runtime", region_name=CONFIG.region)
        return ChatBedrockConverse(
            model_id=model_id, client=bedrock_client,
            temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_id, temperature=CONFIG.temperature, max_tokens=CONFIG.max_tokens)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_id, temperature=CONFIG.temperature, max_output_tokens=CONFIG.max_tokens)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_id, temperature=CONFIG.temperature)
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


def get_llm():
    \"\"\"Get LLM with resilience — fallback cascade + auth rotation.\"\"\"
    global _runner
    if _runner is None:
        _runner = _build_fallback_runner()

    def invoke_fn(provider, model_id, profile):
        return _create_llm_for_provider(provider, model_id)

    return _runner.run(invoke_fn)
"""

    def render_section_4_state(self) -> str:
        return f"""\
# =============================================================================
# 4. STATE DEFINITION
# =============================================================================
{_principle_comments(4)}
from typing import TypedDict


class AgentState(TypedDict, total=False):
    \"\"\"State flowing through the agent graph.\"\"\"

    # Input
    query: str
    context: dict | None

    # Output
    response: str
    error: str | None
"""

    def render_section_5_worker(self) -> str:
        if self.config.tools.enabled:
            return f"""\
# =============================================================================
# 5. WORKER NODE
# =============================================================================
{_principle_comments(5)}
from tools import get_permitted_tools


def worker(state: AgentState) -> dict:
    \"\"\"Worker node — loads prompt, formats input, invokes LLM with tools.\"\"\"
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        system_prompt = load_system_prompt()
    except FileNotFoundError as e:
        return {{"error": f"Prompt not found: {{e}}"}}

    query = state.get("query", "")
    if not query:
        return {{"error": "No query provided"}}

    try:
        llm = get_llm()

        # Bind tools discovered from tools/ directory (Principle 9: Tool Governance)
        permitted = get_permitted_tools()
        if permitted:
            from langchain_core.tools import StructuredTool

            tools_for_llm = [
                StructuredTool.from_function(
                    func=t.as_function(),
                    name=t.name,
                    description=t.description,
                )
                for t in permitted
            ]
            llm = llm.bind_tools(tools_for_llm)
        else:
            log_invocation("tools", "No tools available — running in inference-only mode")

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ])
    except Exception as e:
        return {{"error": f"LLM invocation failed: {{e!s}}"}}

    return {{"response": response.content}}
"""

        return f"""\
# =============================================================================
# 5. WORKER NODE
# =============================================================================
{_principle_comments(5)}

def worker(state: AgentState) -> dict:
    \"\"\"Worker node — loads prompt, formats input, invokes LLM.\"\"\"
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        system_prompt = load_system_prompt()
    except FileNotFoundError as e:
        return {{"error": f"Prompt not found: {{e}}"}}

    query = state.get("query", "")
    if not query:
        return {{"error": "No query provided"}}

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ])
    except Exception as e:
        return {{"error": f"LLM invocation failed: {{e!s}}"}}

    return {{"response": response.content}}
"""

    def render_section_6_graph(self) -> str:
        if self.config.tools.enabled:
            return f"""\
# =============================================================================
# 6. GRAPH CONSTRUCTION
# =============================================================================
{_principle_comments(6)}

def build_graph():
    \"\"\"Build the agent graph: START -> worker -> END.\"\"\"
    from langgraph.graph import END, START, StateGraph

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("worker", worker)
    graph_builder.add_edge(START, "worker")
    graph_builder.add_edge("worker", END)
    return graph_builder


def create_agent():
    \"\"\"Create and compile the agent.

    Tools are discovered from tools/ directory, filtered through tool_policy,
    and bound to the LLM in the worker node (Section 5).
    \"\"\"
    return build_graph().compile()
"""

        return f"""\
# =============================================================================
# 6. GRAPH CONSTRUCTION
# =============================================================================
{_principle_comments(6)}

def build_graph():
    \"\"\"Build the agent graph: START -> worker -> END.\"\"\"
    from langgraph.graph import END, START, StateGraph

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("worker", worker)
    graph_builder.add_edge(START, "worker")
    graph_builder.add_edge("worker", END)
    return graph_builder


def create_agent():
    \"\"\"Create and compile the agent.\"\"\"
    # Tool Governance (Principle 9): When adding tools, filter through tool_policy:
    #   from tool_policy import filter_tools
    #   permitted = filter_tools(["tool_a", "tool_b"])
    #   llm = llm.bind_tools(permitted)
    return build_graph().compile()
"""

    def render_section_8_entrypoint(self) -> str:
        langsmith_import = ""
        langsmith_decorator = ""
        langsmith_comment = ""
        if self.config.langsmith.enabled:
            langsmith_import = "from langsmith import traceable\n\n"
            langsmith_decorator = f'@traceable(name="{self.config.project_name}")\n'
            langsmith_comment = (
                "\n# LangSmith tracing: LangChain calls are auto-traced via LANGCHAIN_TRACING_V2.\n"
                "# The @traceable decorator adds a top-level span wrapping the full execution.\n"
                "# Tracing is activated at runtime with the --dev flag.\n"
            )
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
    initial_state: AgentState = {{
        "query": query,
        "context": context,
    }}

    agent = create_agent()
    final_state = agent.invoke(initial_state)

    if final_state.get("error"):
        raise RuntimeError(final_state["error"])

    return final_state.get("response", "")

{session_wrapper}
{main_block}
{langsmith_comment}"""
