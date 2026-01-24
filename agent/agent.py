"""Main agent orchestrator.

The Agent class is the primary entry point for the local analysis workflow.
It coordinates all components to:
1. Discover evaluation tools via MCP
2. Fetch annotated threads from the Integration Service
3. Run evaluations on each thread
4. Generate issue cards for failing evaluations
5. Create tickets in Jira/Notion
6. Generate individual analysis reports per thread
7. Track processed threads to avoid duplicate processing
8. Sync state to AWS for cross-session persistence
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from agent.api_clients.integration_client import IntegrationServiceClient, ThreadData, ProgressCallback
from agent.api_clients.evaluation_client import EvaluationServiceClient
from agent.mcp_client import MCPClient
from agent.evaluation_orchestrator import EvaluationOrchestrator
from agent.report_generator import ReportGenerator
from agent.state_manager import StateManager
from agent.cloud_sync import CloudSyncClient
from agent.models.evaluation import EvaluationResponse

from shared.models.issue_card import IssueCard, Sources, EvaluationResult, AffectedCode

logger = logging.getLogger(__name__)


class AgentConfig:
    """Configuration for the Agent."""

    def __init__(
        self,
        integration_endpoint: str,
        evaluation_endpoint: str,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        provider: str = "jira",
        report_dir: Path = None,
        project: str = "default",
        jira_project_key: Optional[str] = None,
        notion_database_id: Optional[str] = None,
        cloud_sync_enabled: bool = False,
        cloud_sync_mode: Literal["immediate", "batch", "manual"] = "immediate",
    ):
        self.integration_endpoint = integration_endpoint
        self.evaluation_endpoint = evaluation_endpoint
        self.api_key = api_key
        self.auth_token = auth_token
        self.provider = provider
        self.report_dir = report_dir or Path("./reports")
        self.project = project
        self.jira_project_key = jira_project_key
        self.notion_database_id = notion_database_id
        self.cloud_sync_enabled = cloud_sync_enabled
        self.cloud_sync_mode = cloud_sync_mode


class AnalysisResult:
    """Result from analyzing a single thread."""

    def __init__(
        self,
        thread: ThreadData,
        evaluation: EvaluationResponse,
        issue_card: Optional[IssueCard] = None,
        ticket_id: Optional[str] = None,
        report_path: Optional[str] = None,
    ):
        self.thread = thread
        self.evaluation = evaluation
        self.issue_card = issue_card
        self.ticket_id = ticket_id
        self.report_path = report_path

    @property
    def has_issues(self) -> bool:
        """Check if any evaluations failed."""
        return any(
            r.status in ("fail", "warning")
            for r in self.evaluation.results
        )

    @property
    def issues_count(self) -> int:
        """Count the number of issues (warnings + failures)."""
        return sum(
            1 for r in self.evaluation.results
            if r.status in ("fail", "warning")
        )


class Agent:
    """Main agent for orchestrating thread analysis.

    The agent coordinates the complete analysis workflow from
    fetching threads to creating tickets and generating reports.
    """

    def __init__(self, config: AgentConfig):
        """Initialize the agent.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.run_id = str(uuid.uuid4())[:8]

        # Initialize clients
        self._integration = IntegrationServiceClient(
            endpoint=config.integration_endpoint,
            api_key=config.api_key,
            auth_token=config.auth_token,
        )
        self._evaluation = EvaluationServiceClient(
            endpoint=config.evaluation_endpoint,
            api_key=config.api_key,
            auth_token=config.auth_token,
        )
        self._mcp = MCPClient(config.evaluation_endpoint, config.api_key, auth_token=config.auth_token)
        self._orchestrator = EvaluationOrchestrator(
            evaluation_endpoint=config.evaluation_endpoint,
            api_key=config.api_key,
            auth_token=config.auth_token,
        )
        self._reporter = ReportGenerator(config.report_dir)
        self._state = StateManager(
            project=config.project,
            state_dir=str(config.report_dir),
        )

        # Initialize cloud sync client if enabled
        self._cloud_sync: Optional[CloudSyncClient] = None
        if config.cloud_sync_enabled:
            self._cloud_sync = CloudSyncClient(
                endpoint=config.integration_endpoint,
                api_key=config.api_key,
                enabled=True,
            )
            logger.info(f"Cloud sync enabled with mode: {config.cloud_sync_mode}")

    def discover_tools(self) -> List[str]:
        """Discover available evaluation tools.

        Returns:
            List of tool names
        """
        tools = self._mcp.discover()
        return [t.name for t in tools]

    def fetch_threads(
        self,
        limit: int = 50,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[ThreadData]:
        """Fetch annotated threads from the Integration Service.

        Args:
            limit: Maximum threads to fetch
            progress_callback: Optional callback for progress updates

        Returns:
            List of thread data objects
        """
        logger.info(f"Fetching up to {limit} annotated threads...")
        return self._integration.get_annotated_threads(
            limit=limit,
            progress_callback=progress_callback,
        )

    def analyze_thread(self, thread: ThreadData) -> AnalysisResult:
        """Analyze a single thread.

        Args:
            thread: Thread data to analyze

        Returns:
            Analysis result
        """
        logger.info(f"Analyzing thread: {thread.thread_id}")

        # Run evaluations
        evaluation = self._orchestrator.evaluate_thread(thread.to_dict())

        # Create issue card if there are failures
        issue_card = None
        if any(r.status in ("fail", "warning") for r in evaluation.results):
            issue_card = self._create_issue_card(thread, evaluation)

        return AnalysisResult(
            thread=thread,
            evaluation=evaluation,
            issue_card=issue_card,
        )

    def _create_issue_card(
        self, thread: ThreadData, evaluation: EvaluationResponse
    ) -> IssueCard:
        """Create an issue card from evaluation results.

        Args:
            thread: Thread data
            evaluation: Evaluation results

        Returns:
            Issue card
        """
        # Determine priority based on evaluation scores
        min_score = min(r.score for r in evaluation.results) if evaluation.results else 1.0
        if min_score < 0.3:
            priority = "CRITICAL"
        elif min_score < 0.5:
            priority = "HIGH"
        elif min_score < 0.7:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Determine category from failing evaluations
        failing = [r for r in evaluation.results if r.status in ("fail", "warning")]
        if any("error" in r.tool.lower() for r in failing):
            category = "BUG"
        elif any("latency" in r.tool.lower() or "token" in r.tool.lower() for r in failing):
            category = "PERFORMANCE"
        elif any("content" in r.tool.lower() or "quality" in r.tool.lower() for r in failing):
            category = "QUALITY"
        else:
            category = "TECHNICAL_DEBT"

        # Build title
        title = f"[{priority}] {thread.name[:60]}"

        # Build details
        details_parts = []
        for result in evaluation.results:
            status_icon = "✅" if result.status == "pass" else "⚠️" if result.status == "warning" else "❌"
            details_parts.append(f"- {status_icon} {result.tool}: {result.message or result.status}")

        details = "\n".join(details_parts)

        # Build recommendation
        recommendations = []
        for result in failing:
            if "latency" in result.tool.lower():
                recommendations.append("- Investigate execution bottlenecks")
            elif "token" in result.tool.lower():
                recommendations.append("- Optimize prompt/response lengths")
            elif "error" in result.tool.lower():
                recommendations.append("- Review and fix error conditions")
            elif "content" in result.tool.lower():
                recommendations.append("- Improve response quality and relevance")

        recommendation = "\n".join(recommendations) if recommendations else "Review evaluation results"

        # Create issue card
        return IssueCard(
            title=title,
            priority=priority,
            category=category,
            status="BACKLOG",
            details=details,
            description=thread.annotation_text or f"Issue detected in thread: {thread.name}",
            recommendation=recommendation,
            sources=Sources(
                thread_id=thread.thread_id,
                thread_name=thread.name,
                langsmith_url=thread.langsmith_url,
            ),
            evaluation_results=[
                EvaluationResult(
                    tool=r.tool,
                    status=r.status,
                    score=r.score,
                    message=r.message,
                )
                for r in evaluation.results
            ],
        )

    def create_ticket(self, issue_card: IssueCard) -> Optional[Dict[str, Any]]:
        """Create a ticket for an issue card.

        Args:
            issue_card: Issue card to create

        Returns:
            Full ticket response dict with keys: success, issue_id, issue_key, issue_url, provider
            Returns None on failure
        """
        try:
            issue_data = {
                "title": issue_card.title,
                "priority": issue_card.priority,
                "category": issue_card.category,
                "status": issue_card.status,
                "details": issue_card.details,
                "description": issue_card.description,
                "recommendation": issue_card.recommendation,
                "sources": {
                    "thread_id": issue_card.sources.thread_id,
                    "thread_name": issue_card.sources.thread_name,
                    "langsmith_url": issue_card.sources.langsmith_url,
                },
                "evaluation_results": [
                    {"tool": r.tool, "status": r.status, "score": r.score}
                    for r in issue_card.evaluation_results
                ],
            }

            response = self._integration.create_ticket(
                provider=self.config.provider,
                issue_data=issue_data,
            )

            if response.get("success"):
                return response
            else:
                logger.error(f"Ticket creation failed: {response.get('error')}")
                return None

        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None

    def run(
        self,
        limit: int = 50,
        create_tickets: bool = True,
        dry_run: bool = False,
        skip_processed: bool = True,
        force_reprocess: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Run the complete analysis workflow.

        Args:
            limit: Maximum threads to analyze
            create_tickets: Whether to create tickets for issues
            dry_run: If True, don't create tickets
            skip_processed: If True, skip already-processed threads
            force_reprocess: If True, reprocess all threads regardless of state
            progress_callback: Optional callback for progress updates during thread fetching

        Returns:
            Run summary dictionary
        """
        logger.info(f"Starting analysis run: {self.run_id}")

        # Discover tools
        tools = self.discover_tools()
        logger.info(f"Discovered {len(tools)} evaluation tools: {tools}")

        # Fetch threads
        threads = self.fetch_threads(limit=limit, progress_callback=progress_callback)
        logger.info(f"Fetched {len(threads)} annotated threads")

        if not threads:
            return {
                "run_id": self.run_id,
                "threads_analyzed": 0,
                "threads_skipped": 0,
                "issues_found": 0,
                "tickets_created": 0,
                "report_paths": [],
                "state_file": str(self._state.state_file),
            }

        # Filter out already-processed threads if requested
        threads_to_process = threads
        skipped_count = 0
        if skip_processed and not force_reprocess:
            thread_ids = [t.thread_id for t in threads]
            unprocessed_ids = self._state.get_unprocessed_threads(thread_ids)
            threads_to_process = [t for t in threads if t.thread_id in unprocessed_ids]
            skipped_count = len(threads) - len(threads_to_process)
            if skipped_count > 0:
                logger.info(f"Skipping {skipped_count} already-processed threads")

        if not threads_to_process:
            logger.info("No new threads to process")
            return {
                "run_id": self.run_id,
                "threads_analyzed": 0,
                "threads_skipped": skipped_count,
                "issues_found": 0,
                "tickets_created": 0,
                "report_paths": [],
                "state_file": str(self._state.state_file),
            }

        # Analyze each thread and generate individual reports
        results: List[AnalysisResult] = []
        report_paths: List[str] = []

        for thread in threads_to_process:
            try:
                result = self.analyze_thread(thread)

                # Generate individual thread report
                report_path = self._reporter.generate_thread_report(
                    thread=thread.to_dict(),
                    eval_result=result.evaluation,
                    run_id=self.run_id,
                )
                result.report_path = str(report_path)
                report_paths.append(str(report_path))

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to analyze thread {thread.thread_id}: {e}")
                # Record the error in state
                if not dry_run:
                    self._state.record_processing(
                        thread_id=thread.thread_id,
                        name=thread.name,
                        status="error",
                        error_message=str(e),
                    )

        # Count issues
        issues_found = sum(1 for r in results if r.has_issues)

        # Create tickets and record processing
        tickets_created = 0
        total_issues_synced = 0

        for result in results:
            ticket_ids = []
            ticket_urls = []
            jira_tickets_for_report = []
            notion_tickets_for_report = []

            if result.issue_card and create_tickets and not dry_run:
                ticket_response = self.create_ticket(result.issue_card)
                if ticket_response:
                    ticket_id = ticket_response.get("issue_key") or ticket_response.get("issue_id")
                    ticket_url = ticket_response.get("issue_url", "")
                    provider = ticket_response.get("provider", self.config.provider)

                    result.ticket_id = ticket_id
                    ticket_ids.append(ticket_id)
                    if ticket_url:
                        ticket_urls.append(ticket_url)
                    tickets_created += 1
                    total_issues_synced += 1

                    # Prepare ticket info for report update
                    if provider == "jira":
                        jira_tickets_for_report.append({
                            "key": ticket_response.get("issue_key", ticket_id),
                            "url": ticket_url,
                        })
                    else:
                        notion_tickets_for_report.append({
                            "id": ticket_id,
                            "url": ticket_url,
                        })

                    # Update the report with ticket information
                    if result.report_path:
                        self._reporter.update_report_with_tickets(
                            report_path=Path(result.report_path),
                            jira_tickets=jira_tickets_for_report if provider == "jira" else None,
                            notion_tickets=notion_tickets_for_report if provider == "notion" else None,
                        )

            # Record successful processing in state
            if not dry_run:
                jira_ids = ticket_ids if self.config.provider == "jira" else None
                notion_ids = ticket_ids if self.config.provider == "notion" else None
                jira_urls = ticket_urls if self.config.provider == "jira" else None
                notion_urls = ticket_urls if self.config.provider == "notion" else None

                self._state.record_processing(
                    thread_id=result.thread.thread_id,
                    name=result.thread.name,
                    status="success" if not result.has_issues else "success",
                    issues_created=result.issues_count,
                    documentation_path=result.report_path,
                    jira_issue_ids=jira_ids,
                    notion_issue_ids=notion_ids,
                    jira_issue_urls=jira_urls,
                    notion_issue_urls=notion_urls,
                )

                # Immediate cloud sync if enabled
                if (
                    self._cloud_sync
                    and self.config.cloud_sync_mode == "immediate"
                ):
                    self._cloud_sync.sync_thread_result(
                        thread_id=result.thread.thread_id,
                        name=result.thread.name,
                        status="success",
                        processed_at=datetime.now(timezone.utc).isoformat(),
                        issues_created=result.issues_count,
                        jira_issue_ids=jira_ids,
                        jira_issue_urls=jira_urls,
                        notion_issue_ids=notion_ids,
                        notion_issue_urls=notion_urls,
                        documentation_path=result.report_path,
                        analysis_summary=f"Analyzed thread with {result.issues_count} issues",
                    )

        # Update sync summary
        if not dry_run and tickets_created > 0:
            self._state.update_sync_summary(
                total_issues_synced=total_issues_synced,
                jira_project_key=self.config.jira_project_key if self.config.provider == "jira" else None,
                notion_database_id=self.config.notion_database_id if self.config.provider == "notion" else None,
            )

        # Batch cloud sync if enabled
        if (
            not dry_run
            and self._cloud_sync
            and self.config.cloud_sync_mode == "batch"
        ):
            state = self._state.load()
            self._cloud_sync.sync_full_state(state.model_dump())
            logger.info("Batch cloud sync completed")

        summary = {
            "run_id": self.run_id,
            "threads_analyzed": len(results),
            "threads_skipped": skipped_count,
            "issues_found": issues_found,
            "tickets_created": tickets_created,
            "report_paths": report_paths,
            "state_file": str(self._state.state_file),
            "dry_run": dry_run,
            "cloud_sync_enabled": self.config.cloud_sync_enabled,
        }

        logger.info(f"Run complete: {summary}")
        return summary

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about processed threads.

        Returns:
            Dictionary with processing stats
        """
        return self._state.get_stats()

    def clear_state(self) -> None:
        """Clear all processing state (resets processed thread tracking)."""
        self._state.clear_state()
        logger.info("Processing state cleared")

    def sync_to_cloud(self) -> Dict[str, Any]:
        """Manually sync processing state to cloud.

        This method can be called when cloud_sync_mode is set to 'manual'
        to push the current state to AWS.

        Returns:
            Sync result dictionary
        """
        if not self._cloud_sync:
            return {"success": False, "error": "Cloud sync not enabled"}

        state = self._state.load()
        result = self._cloud_sync.sync_full_state(state.model_dump())
        logger.info(f"Manual cloud sync result: {result}")
        return result

    def get_cloud_state(self) -> Dict[str, Any]:
        """Get current state from cloud.

        Returns:
            Cloud state summary or error dict
        """
        if not self._cloud_sync:
            return {"success": False, "error": "Cloud sync not enabled"}

        return self._cloud_sync.get_aws_state(self.config.project)
