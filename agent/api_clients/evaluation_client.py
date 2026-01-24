"""Client for the AWS Evaluation Service."""

import logging
from typing import Any, Dict, List, Optional

import requests

from agent.models.mcp import MCPDiscoveryResponse, MCPToolDefinition
from agent.models.evaluation import EvaluationRequest, EvaluationResponse, SingleEvaluationRequest

logger = logging.getLogger(__name__)


class EvaluationServiceClient:
    """Client for interacting with the AWS Evaluation Service.

    Provides MCP-compatible tool discovery and evaluation execution.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize the client.

        Args:
            endpoint: Base URL of the Evaluation Service
            api_key: Optional API Gateway key (legacy)
            auth_token: Cognito JWT token for authentication
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        if auth_token:
            self._session.headers["Authorization"] = f"Bearer {auth_token}"
        if api_key:
            self._session.headers["X-Api-Key"] = api_key
        self._session.headers["Content-Type"] = "application/json"

        # Cached tools
        self._tools: Optional[Dict[str, MCPToolDefinition]] = None

    def discover_tools(self, force_refresh: bool = False) -> List[MCPToolDefinition]:
        """Discover available evaluation tools.

        Args:
            force_refresh: Force refresh of cached tools

        Returns:
            List of available tool definitions
        """
        if self._tools is not None and not force_refresh:
            return list(self._tools.values())

        try:
            response = self._session.get(
                f"{self.endpoint}/evaluations/discovery",
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            discovery = MCPDiscoveryResponse(**data)

            # Cache tools by name
            self._tools = {tool.name: tool for tool in discovery.tools}

            logger.info(f"Discovered {len(self._tools)} evaluation tools")
            return discovery.tools

        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            raise

    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Get a specific tool definition.

        Args:
            name: Tool name

        Returns:
            Tool definition or None if not found
        """
        if self._tools is None:
            self.discover_tools()

        return self._tools.get(name)

    def execute_evaluation(
        self,
        thread_id: str,
        tool_name: str,
        input_data: Dict[str, Any],
    ) -> EvaluationResponse:
        """Execute a single evaluation.

        Args:
            thread_id: Thread being evaluated
            tool_name: Name of evaluation tool
            input_data: Input data for the tool

        Returns:
            Evaluation response
        """
        return self.execute_batch(
            thread_id=thread_id,
            evaluations=[{"tool": tool_name, "input": input_data}],
        )

    def execute_batch(
        self,
        thread_id: str,
        evaluations: List[Dict[str, Any]],
    ) -> EvaluationResponse:
        """Execute multiple evaluations in a batch.

        Args:
            thread_id: Thread being evaluated
            evaluations: List of evaluation requests

        Returns:
            Batch evaluation response
        """
        try:
            request_data = {
                "thread_id": thread_id,
                "evaluations": evaluations,
            }

            response = self._session.post(
                f"{self.endpoint}/evaluations/execute",
                json=request_data,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return EvaluationResponse(**data)

        except Exception as e:
            logger.error(f"Failed to execute evaluations: {e}")
            raise

    def execute_all(
        self,
        thread_id: str,
        thread_data: Dict[str, Any],
    ) -> EvaluationResponse:
        """Execute all available evaluations on a thread.

        Args:
            thread_id: Thread ID
            thread_data: Thread data to evaluate

        Returns:
            Evaluation response with all results
        """
        tools = self.discover_tools()

        evaluations = []
        for tool in tools:
            # Build input based on tool requirements
            input_data = self._build_tool_input(tool, thread_data)
            if input_data:
                evaluations.append({"tool": tool.name, "input": input_data})

        if not evaluations:
            logger.warning("No applicable evaluations for thread")
            return EvaluationResponse(
                thread_id=thread_id,
                execution_id="none",
                timestamp="",
                results=[],
            )

        return self.execute_batch(thread_id, evaluations)

    def _build_tool_input(
        self, tool: MCPToolDefinition, thread_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Build input for a tool based on thread data.

        Args:
            tool: Tool definition
            thread_data: Thread data

        Returns:
            Input dictionary or None if required data is missing
        """
        schema = tool.input_schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        input_data = {}

        # Map thread data to tool input
        field_mappings = {
            "duration_seconds": ["duration_seconds"],
            "total_tokens": ["total_tokens"],
            "prompt_tokens": ["prompt_tokens"],
            "completion_tokens": ["completion_tokens"],
            "user_query": ["user_query"],
            "final_response": ["final_response"],
            "thread_data": ["*"],  # Special: pass entire thread
        }

        for field, sources in field_mappings.items():
            if field in properties:
                if sources == ["*"]:
                    # Pass entire thread data
                    input_data[field] = thread_data
                else:
                    for source in sources:
                        if source in thread_data and thread_data[source] is not None:
                            input_data[field] = thread_data[source]
                            break

        # Check required fields
        for req in required:
            if req not in input_data:
                logger.debug(f"Missing required field '{req}' for tool '{tool.name}'")
                return None

        return input_data if input_data else None
