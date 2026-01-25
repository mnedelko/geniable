"""Client for the AWS Integration Service."""

import logging
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Type for progress callback: (phase, current, total, thread_id)
ProgressCallback = Callable[[str, int, int, str], None]


class ThreadData:
    """Thread data from the Integration Service."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def thread_id(self) -> str:
        return self._data.get("thread_id", "")

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def status(self) -> str:
        return self._data.get("status", "unknown")

    @property
    def duration_seconds(self) -> float:
        return self._data.get("duration_seconds", 0.0)

    @property
    def total_tokens(self) -> int:
        return self._data.get("total_tokens", 0)

    @property
    def user_query(self) -> str:
        return self._data.get("user_query", "")

    @property
    def final_response(self) -> Optional[str]:
        return self._data.get("final_response")

    @property
    def annotation_text(self) -> Optional[str]:
        return self._data.get("annotation_text")

    @property
    def errors(self) -> List[str]:
        return self._data.get("errors", [])

    @property
    def langsmith_url(self) -> Optional[str]:
        return self._data.get("langsmith_url")

    def to_dict(self) -> Dict[str, Any]:
        return self._data


class FetchResult:
    """Result of fetching threads, including metadata about filtering."""

    def __init__(
        self,
        threads: List[ThreadData],
        total_in_queue: int,
        returned: int,
        skipped: int,
    ):
        self.threads = threads
        self.total_in_queue = total_in_queue
        self.returned = returned
        self.skipped = skipped

    @property
    def has_threads(self) -> bool:
        return len(self.threads) > 0


class IntegrationServiceClient:
    """Client for interacting with the AWS Integration Service.

    Provides access to:
    - Annotated threads from LangSmith
    - Ticket creation in Jira/Notion
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
            endpoint: Base URL of the Integration Service
            api_key: Optional API Gateway key (legacy)
            auth_token: Optional Cognito auth token (Bearer token)
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        if api_key:
            self._session.headers["X-Api-Key"] = api_key
        if auth_token:
            self._session.headers["Authorization"] = f"Bearer {auth_token}"
        self._session.headers["Content-Type"] = "application/json"

    def get_thread_details(self, thread_id: str) -> ThreadData:
        """Fetch full details for a single thread.

        Args:
            thread_id: The thread ID to fetch details for

        Returns:
            Thread data with full details
        """
        try:
            response = self._session.get(
                f"{self.endpoint}/threads/{thread_id}/details",
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return ThreadData(data)

        except Exception as e:
            logger.error(f"Failed to fetch thread details for {thread_id}: {e}")
            raise

    def fetch_threads(
        self,
        limit: int = 50,
        with_details: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> FetchResult:
        """Fetch annotated threads from LangSmith with filtering metadata.

        Uses a two-step approach to avoid timeouts:
        1. Fetch summaries only (fast) - AWS filters out previously analyzed threads
        2. Fetch details for each thread individually

        Args:
            limit: Maximum threads to return
            with_details: Whether to include full thread details
            progress_callback: Optional callback for progress updates
                               Called with (phase, current, total, thread_id)

        Returns:
            FetchResult with threads and metadata (total, returned, skipped)
        """
        try:
            # Step 1: Fetch summaries only (fast, never times out)
            # AWS service automatically filters out previously analyzed threads
            logger.info(f"Fetching thread summaries (limit={limit})")
            if progress_callback:
                progress_callback("summaries", 0, 0, "")

            params = {
                "limit": limit,
                "with_details": "false",  # Always get summaries first
                "skip_processed": "true",  # AWS filters already-analyzed threads
            }

            response = self._session.get(
                f"{self.endpoint}/threads/annotated",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            threads_data = data.get("threads", [])
            pagination = data.get("pagination", {})

            # Extract filtering stats from AWS response
            total_in_queue = pagination.get("total", len(threads_data))
            returned = pagination.get("returned", len(threads_data))
            skipped = total_in_queue - returned

            logger.info(
                f"Found {total_in_queue} threads in queue, "
                f"{skipped} skipped (previously analyzed), "
                f"{returned} new threads to analyze"
            )

            if not threads_data:
                if progress_callback:
                    progress_callback("complete", 0, 0, "")
                return FetchResult(
                    threads=[],
                    total_in_queue=total_in_queue,
                    returned=0,
                    skipped=skipped,
                )

            # Step 2: If details requested, fetch each thread's details individually
            threads: List[ThreadData] = []
            if with_details:
                logger.info(f"Fetching details for {len(threads_data)} threads one-by-one")
                if progress_callback:
                    progress_callback("details", 0, len(threads_data), "")

                for i, thread_summary in enumerate(threads_data):
                    thread_id = thread_summary.get("thread_id")
                    if thread_id:
                        if progress_callback:
                            progress_callback("details", i + 1, len(threads_data), thread_id)
                        try:
                            logger.info(
                                f"Fetching details {i + 1}/{len(threads_data)}: {thread_id}"
                            )
                            thread_details = self.get_thread_details(thread_id)
                            threads.append(thread_details)
                        except Exception as e:
                            logger.warning(f"Failed to get details for thread {thread_id}: {e}")
                            # Fall back to summary data
                            threads.append(ThreadData(thread_summary))
            else:
                threads = [ThreadData(t) for t in threads_data]

            if progress_callback:
                progress_callback("complete", len(threads_data), len(threads_data), "")

            return FetchResult(
                threads=threads,
                total_in_queue=total_in_queue,
                returned=returned,
                skipped=skipped,
            )

        except Exception as e:
            logger.error(f"Failed to fetch threads: {e}")
            raise

    def get_annotated_threads(
        self,
        limit: int = 50,
        with_details: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[ThreadData]:
        """Fetch annotated threads from LangSmith.

        Uses a two-step approach to avoid timeouts:
        1. Fetch summaries only (fast)
        2. Fetch details for each thread individually

        Args:
            limit: Maximum threads to return
            with_details: Whether to include full thread details
            progress_callback: Optional callback for progress updates
                               Called with (phase, current, total, thread_id)

        Returns:
            List of thread data objects
        """
        result = self.fetch_threads(limit, with_details, progress_callback)
        return result.threads

    def mark_threads_done(
        self,
        thread_ids: List[str],
        project: str = "default",
    ) -> Dict[str, Any]:
        """Mark threads as analyzed/done in AWS.

        Syncs the processing state to AWS so these threads won't be
        returned in future fetch calls.

        Args:
            thread_ids: List of thread IDs to mark as done
            project: Project name for state tracking

        Returns:
            Sync result from AWS
        """
        try:
            # Build thread state objects
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            threads = [
                {
                    "thread_id": tid,
                    "status": "processed",
                    "processed_at": now,
                    "issues_created": 0,  # Will be updated if tickets are created
                }
                for tid in thread_ids
            ]

            payload = {
                "project": project,
                "threads": threads,
            }

            response = self._session.post(
                f"{self.endpoint}/users/me/state/sync",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Marked {len(thread_ids)} threads as done: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to mark threads as done: {e}")
            raise

    def create_ticket(
        self,
        provider: str,
        issue_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a ticket in the target system.

        Args:
            provider: Provider name ('jira' or 'notion')
            issue_data: Issue data matching the IssueRequest schema

        Returns:
            Ticket creation response
        """
        try:
            request_data = {
                "provider": provider,
                "issue": issue_data,
            }

            response = self._session.post(
                f"{self.endpoint}/integrations/ticket",
                json=request_data,
                timeout=self.timeout,
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            raise

    def validate_connection(self) -> bool:
        """Validate connection to the Integration Service.

        Returns:
            True if connection is valid
        """
        try:
            response = self._session.get(
                f"{self.endpoint}/threads/annotated",
                params={"limit": 1, "with_details": "false"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False
