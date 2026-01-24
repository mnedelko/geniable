"""State manager for tracking processed threads.

Maintains local state of which threads have been processed to avoid
duplicate processing and enable incremental analysis runs.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProcessingHistoryEntry(BaseModel):
    """Record of a processed thread."""

    thread_id: str
    name: str
    status: str  # success, error, skipped
    processed_at: str
    issues_created: int = 0
    issues_synced_to_jira: bool = False
    issues_synced_to_notion: bool = False
    jira_issue_ids: List[str] = Field(default_factory=list)
    notion_issue_ids: List[str] = Field(default_factory=list)
    jira_issue_urls: List[str] = Field(default_factory=list)
    notion_issue_urls: List[str] = Field(default_factory=list)
    documentation_path: Optional[str] = None
    error_message: Optional[str] = None


class SyncSummary(BaseModel):
    """Summary of synchronization status."""

    last_sync: str
    total_issues_synced: int = 0
    jira_project_key: Optional[str] = None
    notion_database_id: Optional[str] = None


class ProcessingState(BaseModel):
    """Complete state of thread processing."""

    project: str
    last_poll: str
    processed_thread_ids: List[str] = Field(default_factory=list)
    processing_history: List[ProcessingHistoryEntry] = Field(default_factory=list)
    sync_summary: Optional[SyncSummary] = None
    pending_issues: List[Dict[str, Any]] = Field(default_factory=list)


class StateManager:
    """Manages local state for processed threads.

    State is stored in a JSON file in the reports directory.
    """

    def __init__(self, project: str, state_dir: Optional[str] = None):
        """Initialize state manager.

        Args:
            project: LangSmith project name
            state_dir: Directory for state file (defaults to ./reports)
        """
        self.project = project
        self.state_dir = Path(state_dir or "./reports")
        self.state_file = self.state_dir / "processing_state.json"
        self._state: Optional[ProcessingState] = None

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> ProcessingState:
        """Load state from file or create new state."""
        if self._state is not None:
            return self._state

        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                self._state = ProcessingState(**data)
            except (json.JSONDecodeError, Exception) as e:
                # If state file is corrupted, start fresh
                print(f"Warning: Could not load state file: {e}")
                self._state = self._create_new_state()
        else:
            self._state = self._create_new_state()

        return self._state

    def _create_new_state(self) -> ProcessingState:
        """Create a new empty state."""
        return ProcessingState(
            project=self.project,
            last_poll=datetime.now(timezone.utc).isoformat(),
            processed_thread_ids=[],
            processing_history=[],
        )

    def save(self) -> None:
        """Save state to file."""
        if self._state is None:
            return

        self._ensure_dir()

        with open(self.state_file, "w") as f:
            json.dump(self._state.model_dump(), f, indent=2, default=str)

    def is_processed(self, thread_id: str) -> bool:
        """Check if a thread has already been processed.

        Args:
            thread_id: Thread ID to check

        Returns:
            True if thread has been processed
        """
        state = self.load()
        return thread_id in state.processed_thread_ids

    def get_unprocessed_threads(self, thread_ids: List[str]) -> List[str]:
        """Filter out already-processed threads.

        Args:
            thread_ids: List of thread IDs to filter

        Returns:
            List of thread IDs that haven't been processed
        """
        state = self.load()
        return [tid for tid in thread_ids if tid not in state.processed_thread_ids]

    def record_processing(
        self,
        thread_id: str,
        name: str,
        status: str,
        issues_created: int = 0,
        documentation_path: Optional[str] = None,
        jira_issue_ids: Optional[List[str]] = None,
        notion_issue_ids: Optional[List[str]] = None,
        jira_issue_urls: Optional[List[str]] = None,
        notion_issue_urls: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Record that a thread has been processed.

        Args:
            thread_id: Thread ID
            name: Thread name
            status: Processing status (success, error, skipped)
            issues_created: Number of issues created
            documentation_path: Path to the analysis report
            jira_issue_ids: List of Jira issue IDs created
            notion_issue_ids: List of Notion page IDs created
            jira_issue_urls: List of Jira issue URLs created
            notion_issue_urls: List of Notion page URLs created
            error_message: Error message if status is error
        """
        state = self.load()

        # Add to processed list if not already there
        if thread_id not in state.processed_thread_ids:
            state.processed_thread_ids.append(thread_id)

        # Create history entry
        entry = ProcessingHistoryEntry(
            thread_id=thread_id,
            name=name,
            status=status,
            processed_at=datetime.now(timezone.utc).isoformat(),
            issues_created=issues_created,
            issues_synced_to_jira=bool(jira_issue_ids),
            issues_synced_to_notion=bool(notion_issue_ids),
            jira_issue_ids=jira_issue_ids or [],
            notion_issue_ids=notion_issue_ids or [],
            jira_issue_urls=jira_issue_urls or [],
            notion_issue_urls=notion_issue_urls or [],
            documentation_path=documentation_path,
            error_message=error_message,
        )

        # Check if entry already exists and update it, otherwise append
        existing_idx = None
        for i, h in enumerate(state.processing_history):
            if h.thread_id == thread_id:
                existing_idx = i
                break

        if existing_idx is not None:
            state.processing_history[existing_idx] = entry
        else:
            state.processing_history.append(entry)

        # Update last poll time
        state.last_poll = datetime.now(timezone.utc).isoformat()

        self.save()

    def update_sync_summary(
        self,
        total_issues_synced: int,
        jira_project_key: Optional[str] = None,
        notion_database_id: Optional[str] = None,
    ) -> None:
        """Update the sync summary.

        Args:
            total_issues_synced: Total number of issues synced
            jira_project_key: Jira project key
            notion_database_id: Notion database ID
        """
        state = self.load()

        state.sync_summary = SyncSummary(
            last_sync=datetime.now(timezone.utc).isoformat(),
            total_issues_synced=total_issues_synced,
            jira_project_key=jira_project_key,
            notion_database_id=notion_database_id,
        )

        self.save()

    def get_processing_history(
        self, thread_id: Optional[str] = None
    ) -> List[ProcessingHistoryEntry]:
        """Get processing history.

        Args:
            thread_id: Optional thread ID to filter by

        Returns:
            List of processing history entries
        """
        state = self.load()

        if thread_id:
            return [h for h in state.processing_history if h.thread_id == thread_id]

        return state.processing_history

    def clear_state(self) -> None:
        """Clear all state (useful for testing or reset)."""
        self._state = self._create_new_state()
        self.save()

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics.

        Returns:
            Dictionary with processing stats
        """
        state = self.load()

        success_count = sum(
            1 for h in state.processing_history if h.status == "success"
        )
        error_count = sum(1 for h in state.processing_history if h.status == "error")
        total_issues = sum(h.issues_created for h in state.processing_history)

        return {
            "project": state.project,
            "last_poll": state.last_poll,
            "total_processed": len(state.processed_thread_ids),
            "successful": success_count,
            "errors": error_count,
            "total_issues_created": total_issues,
        }
