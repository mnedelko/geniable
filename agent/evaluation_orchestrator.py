"""Evaluation orchestrator for coordinating evaluations.

The orchestrator manages the evaluation workflow, selecting appropriate
evaluators and aggregating results.
"""

import logging
from typing import Any, Dict, List

from agent.api_clients.evaluation_client import EvaluationServiceClient
from agent.mcp_client import MCPClient
from agent.models.evaluation import EvaluationResponse, EvaluationResult

logger = logging.getLogger(__name__)


class EvaluationOrchestrator:
    """Orchestrates evaluation execution across threads.

    Responsibilities:
    - Selecting applicable evaluators based on thread data
    - Building evaluation requests
    - Aggregating and analyzing results
    """

    def __init__(
        self,
        evaluation_endpoint: str,
        api_key: str = None,
        auth_token: str = None,
    ):
        """Initialize the orchestrator.

        Args:
            evaluation_endpoint: URL of the Evaluation Service
            api_key: Optional API key (legacy)
            auth_token: Cognito JWT token for authentication
        """
        self._client = EvaluationServiceClient(
            endpoint=evaluation_endpoint,
            api_key=api_key,
            auth_token=auth_token,
        )
        self._mcp = MCPClient(evaluation_endpoint, api_key, auth_token=auth_token)

    def evaluate_thread(self, thread_data: Dict[str, Any]) -> EvaluationResponse:
        """Run all applicable evaluations on a thread.

        Args:
            thread_data: Thread data dictionary

        Returns:
            Aggregated evaluation response
        """
        thread_id = thread_data.get("thread_id", "unknown")

        # Discover available tools
        tools = self._mcp.discover()

        # Build evaluation requests
        evaluations = []
        for tool in tools:
            input_data = self._build_input(tool.name, thread_data)
            if input_data:
                evaluations.append({"tool": tool.name, "input": input_data})
                logger.debug(f"Queued evaluation: {tool.name}")

        if not evaluations:
            logger.warning(f"No applicable evaluations for thread {thread_id}")
            return EvaluationResponse(
                thread_id=thread_id,
                execution_id="none",
                timestamp="",
                results=[],
            )

        # Execute batch
        logger.info(f"Executing {len(evaluations)} evaluations for thread {thread_id}")
        return self._client.execute_batch(thread_id, evaluations)

    def _build_input(self, tool_name: str, thread_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build input for a specific tool.

        Args:
            tool_name: Name of the tool
            thread_data: Thread data

        Returns:
            Input dictionary or None if data is insufficient
        """
        # Tool-specific input mappings
        mappings = {
            "latency_evaluation": {
                "duration_seconds": thread_data.get("duration_seconds"),
            },
            "token_usage_evaluation": {
                "total_tokens": thread_data.get("total_tokens"),
                "prompt_tokens": thread_data.get("prompt_tokens"),
                "completion_tokens": thread_data.get("completion_tokens"),
            },
            "error_detection": {
                "thread_data": {
                    "errors": thread_data.get("errors", []),
                    "steps": thread_data.get("steps", []),
                    "status": thread_data.get("status"),
                },
            },
            "content_quality_evaluation": {
                "user_query": thread_data.get("user_query"),
                "final_response": thread_data.get("final_response"),
            },
        }

        input_data = mappings.get(tool_name, {})

        # Check for required data
        required = self._mcp.get_required_fields(tool_name)
        for field in required:
            if field not in input_data or input_data[field] is None:
                return None

        return input_data

    def get_failing_evaluations(self, response: EvaluationResponse) -> List[EvaluationResult]:
        """Get evaluations that failed or had warnings.

        Args:
            response: Evaluation response

        Returns:
            List of failed/warning results
        """
        return [r for r in response.results if r.status in ("fail", "warning")]

    def calculate_overall_score(self, response: EvaluationResponse) -> float:
        """Calculate weighted overall score.

        Args:
            response: Evaluation response

        Returns:
            Overall score (0-1)
        """
        if not response.results:
            return 1.0

        total_score = sum(r.score for r in response.results)
        return total_score / len(response.results)
