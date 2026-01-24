"""MCP (Model Context Protocol) client for tool discovery.

The MCPClient provides a clean interface for discovering and using
evaluation tools from the AWS Evaluation Service.
"""

import logging
from typing import Any, Dict, List, Optional

from agent.api_clients.evaluation_client import EvaluationServiceClient
from agent.models.mcp import MCPToolDefinition

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client for tool discovery and validation.

    Acts as a facade over the EvaluationServiceClient, providing
    MCP-specific functionality like schema validation and tool caching.
    """

    def __init__(
        self,
        evaluation_endpoint: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        """Initialize the MCP client.

        Args:
            evaluation_endpoint: URL of the Evaluation Service
            api_key: Optional API key for authentication (legacy)
            auth_token: Cognito JWT token for authentication
        """
        self._client = EvaluationServiceClient(
            endpoint=evaluation_endpoint,
            api_key=api_key,
            auth_token=auth_token,
        )
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._discovered = False

    def discover(self, force: bool = False) -> List[MCPToolDefinition]:
        """Discover available tools from the service.

        Args:
            force: Force refresh even if already discovered

        Returns:
            List of available tools
        """
        if self._discovered and not force:
            return list(self._tools.values())

        tools = self._client.discover_tools(force_refresh=force)
        self._tools = {tool.name: tool for tool in tools}
        self._discovered = True

        logger.info(f"MCP discovery complete: {len(self._tools)} tools available")
        return tools

    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Get a specific tool by name.

        Args:
            name: Tool name

        Returns:
            Tool definition or None
        """
        if not self._discovered:
            self.discover()
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all available tool names.

        Returns:
            List of tool names
        """
        if not self._discovered:
            self.discover()
        return list(self._tools.keys())

    def validate_input(self, tool_name: str, input_data: Dict[str, Any]) -> bool:
        """Validate input data against tool schema.

        Args:
            tool_name: Name of the tool
            input_data: Input data to validate

        Returns:
            True if input is valid

        Note: This is a basic validation. For full JSON Schema validation,
        use the jsonschema library.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False

        schema = tool.input_schema
        required = schema.get("required", [])

        # Check required fields
        for field in required:
            if field not in input_data:
                logger.warning(f"Missing required field '{field}' for tool '{tool_name}'")
                return False

        return True

    def get_required_fields(self, tool_name: str) -> List[str]:
        """Get required input fields for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of required field names
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return []
        return tool.input_schema.get("required", [])

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get human-readable tool information.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool info dictionary or None
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "version": tool.version,
            "required_fields": self.get_required_fields(tool_name),
        }
