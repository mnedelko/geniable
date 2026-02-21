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
# 3. MODEL CONFIGURATION
# =============================================================================
{_principle_comments(3)}
# Strands manages the model client internally — no separate client needed.
# The model is configured when creating the Agent instance (Section 6).

_model = None


def get_model():
    \"\"\"Get or create the Strands Bedrock model (lazy init).\"\"\"
    global _model
    if _model is None:
        from strands.models.bedrock import BedrockModel

        _model = BedrockModel(
            model_id=CONFIG.model_id,
            region_name=CONFIG.region,
            temperature=CONFIG.temperature,
            max_tokens=CONFIG.max_tokens,
        )
    return _model
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
        return f"""\
# =============================================================================
# 6. AGENT CONSTRUCTION
# =============================================================================
{_principle_comments(6)}

def create_agent():
    \"\"\"Create the Strands agent with configured model and tools.\"\"\"
    from strands import Agent

    system_prompt = load_system_prompt()
    model = get_model()

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[process_query_tool],
    )
    return agent
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
    try:
        agent = create_agent()
        response = agent(query)
        return str(response)
    except Exception as e:
        raise RuntimeError(f"Agent invocation failed: {{e!s}}") from e


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
