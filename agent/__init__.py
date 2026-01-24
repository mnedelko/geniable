"""Local Agent for LangSmith thread analysis.

The Local Agent runs in the user's environment and orchestrates:
- MCP-based tool discovery from AWS Evaluation Service
- Thread fetching from AWS Integration Service
- Local and remote evaluation execution
- Report generation
- Issue card creation
"""

from agent.agent import Agent
from agent.mcp_client import MCPClient

__all__ = ["Agent", "MCPClient"]
