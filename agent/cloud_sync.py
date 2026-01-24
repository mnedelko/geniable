"""Cloud sync client for syncing state to AWS.

Provides methods to sync thread analysis state to the AWS Integration Service,
which stores it in DynamoDB for cross-session persistence and status queries.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class CloudSyncClient:
    """Client for syncing processing state to AWS.

    Uses the Integration Service API to sync thread analysis state
    to DynamoDB for persistence and querying.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        enabled: bool = True,
    ):
        """Initialize the cloud sync client.

        Args:
            endpoint: Base URL of the Integration Service
            api_key: Optional API Gateway key
            timeout: Request timeout in seconds
            enabled: Whether cloud sync is enabled
        """
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.enabled = enabled

        self._session = requests.Session()
        if api_key:
            self._session.headers["X-Api-Key"] = api_key
        self._session.headers["Content-Type"] = "application/json"

    def sync_thread_result(
        self,
        thread_id: str,
        name: str,
        status: str,
        processed_at: str,
        issues_created: int = 0,
        jira_issue_ids: Optional[List[str]] = None,
        jira_issue_urls: Optional[List[str]] = None,
        notion_issue_ids: Optional[List[str]] = None,
        notion_issue_urls: Optional[List[str]] = None,
        documentation_path: Optional[str] = None,
        analysis_summary: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sync a single thread's analysis result to AWS.

        Args:
            thread_id: Thread identifier
            name: Thread name
            status: Processing status (success, error, skipped)
            processed_at: Processing timestamp
            issues_created: Number of issues created
            jira_issue_ids: List of Jira issue IDs
            jira_issue_urls: List of Jira issue URLs
            notion_issue_ids: List of Notion page IDs
            notion_issue_urls: List of Notion page URLs
            documentation_path: Path to the analysis report
            analysis_summary: Brief summary of the analysis
            error_message: Error message if status is error

        Returns:
            Sync response dict with success status
        """
        if not self.enabled:
            logger.debug("Cloud sync disabled, skipping thread sync")
            return {"success": True, "skipped": True, "reason": "cloud sync disabled"}

        thread_state = {
            "thread_id": thread_id,
            "name": name,
            "status": status,
            "processed_at": processed_at,
            "issues_created": issues_created,
            "jira_issue_ids": jira_issue_ids or [],
            "jira_issue_urls": jira_issue_urls or [],
            "notion_issue_ids": notion_issue_ids or [],
            "notion_issue_urls": notion_issue_urls or [],
            "documentation_path": documentation_path or "",
            "analysis_summary": analysis_summary or "",
        }

        if error_message:
            thread_state["error_message"] = error_message

        try:
            response = self._session.post(
                f"{self.endpoint}/state/sync",
                json={"thread": thread_state},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Synced thread {thread_id} to AWS")
            return result

        except Exception as e:
            logger.warning(f"Failed to sync thread {thread_id} to AWS: {e}")
            return {"success": False, "error": str(e)}

    def sync_full_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Sync full project processing state to AWS.

        Args:
            state: Full processing state dict with:
                - project: Project name
                - last_poll: Last poll timestamp
                - processed_thread_ids: List of processed thread IDs
                - processing_history: List of processing history entries

        Returns:
            Sync response dict with success status
        """
        if not self.enabled:
            logger.debug("Cloud sync disabled, skipping full state sync")
            return {"success": True, "skipped": True, "reason": "cloud sync disabled"}

        try:
            response = self._session.post(
                f"{self.endpoint}/state/sync",
                json={"project_state": state},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Synced full state for project {state.get('project', 'unknown')} to AWS")
            return result

        except Exception as e:
            logger.warning(f"Failed to sync full state to AWS: {e}")
            return {"success": False, "error": str(e)}

    def get_aws_state(self, project: str = "default") -> Dict[str, Any]:
        """Get current state from AWS.

        Args:
            project: Project name

        Returns:
            Project state summary from AWS
        """
        if not self.enabled:
            logger.debug("Cloud sync disabled, cannot get AWS state")
            return {"success": False, "error": "cloud sync disabled"}

        try:
            response = self._session.get(
                f"{self.endpoint}/state/status",
                params={"project": project},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.warning(f"Failed to get AWS state: {e}")
            return {"error": str(e)}

    def get_thread_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific thread's state from AWS.

        Args:
            thread_id: Thread identifier

        Returns:
            Thread state dict or None if not found
        """
        if not self.enabled:
            logger.debug("Cloud sync disabled, cannot get thread state")
            return None

        try:
            response = self._session.get(
                f"{self.endpoint}/state/thread/{thread_id}",
                timeout=self.timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.warning(f"Failed to get thread state from AWS: {e}")
            return None

    def validate_connection(self) -> bool:
        """Validate connection to the cloud sync service.

        Returns:
            True if connection is valid
        """
        if not self.enabled:
            return False

        try:
            response = self._session.get(
                f"{self.endpoint}/state/status",
                params={"project": "test"},
                timeout=10,
            )
            # 200 or 503 (not configured) both indicate the endpoint is reachable
            return response.status_code in (200, 503)
        except Exception:
            return False
