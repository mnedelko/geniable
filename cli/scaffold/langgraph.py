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
        return f"""\
# =============================================================================
# 3. BEDROCK CLIENT (lazy initialization)
# =============================================================================
{_principle_comments(3)}
_llm = None


def get_llm():
    \"\"\"Get or create the LLM client (lazy init for faster cold starts).\"\"\"
    global _llm
    if _llm is None:
        import boto3
        from langchain_aws import ChatBedrockConverse

        bedrock_client = boto3.client("bedrock-runtime", region_name=CONFIG.region)
        _llm = ChatBedrockConverse(
            model_id=CONFIG.model_id,
            client=bedrock_client,
            temperature=CONFIG.temperature,
            max_tokens=CONFIG.max_tokens,
        )
    return _llm
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
    return build_graph().compile()
"""

    def render_section_8_entrypoint(self) -> str:
        return f"""\
# =============================================================================
# 8. ENTRY POINT
# =============================================================================
{_principle_comments(8)}

def run_agent(query: str, context: dict | None = None) -> str:
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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        print(f"Query: {{user_query}}")
        print("=" * 60)
        try:
            result = run_agent(user_query)
            print(result)
        except RuntimeError as e:
            print(f"Error: {{e}}")
            sys.exit(1)
    else:
        print("Usage: python agent.py <query>")
        sys.exit(1)
"""
