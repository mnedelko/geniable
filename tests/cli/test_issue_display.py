"""Tests for the IssueDisplay dataclass."""

from __future__ import annotations

from cli.issue_display import IssueDisplay


class TestIssueDisplay:
    """Tests for IssueDisplay dataclass."""

    def test_priority_sort_key_ordering(self) -> None:
        high = IssueDisplay(
            key="X-1", summary="", status="", priority="High",
            description="", assignee=None, created="", updated="", url="",
        )
        medium = IssueDisplay(
            key="X-2", summary="", status="", priority="Medium",
            description="", assignee=None, created="", updated="", url="",
        )
        low = IssueDisplay(
            key="X-3", summary="", status="", priority="Low",
            description="", assignee=None, created="", updated="", url="",
        )
        assert high.priority_sort_key < medium.priority_sort_key < low.priority_sort_key

    def test_highest_priority(self) -> None:
        issue = IssueDisplay(
            key="X-1", summary="", status="", priority="Highest",
            description="", assignee=None, created="", updated="", url="",
        )
        assert issue.priority_sort_key == 0

    def test_unknown_priority_sort_key(self) -> None:
        issue = IssueDisplay(
            key="X-1", summary="", status="", priority="Custom",
            description="", assignee=None, created="", updated="", url="",
        )
        assert issue.priority_sort_key == 5

    def test_from_dict(self) -> None:
        data = {
            "key": "AIEV-42",
            "summary": "Fix login bug",
            "status": "To Do",
            "priority": "High",
            "description": "Login is broken",
            "assignee": "Test User",
            "created": "2025-01-01",
            "updated": "2025-01-15",
            "url": "https://test.atlassian.net/browse/AIEV-42",
            "issue_type": "Bug",
            "labels": ["bug", "urgent"],
        }
        issue = IssueDisplay.from_dict(data)
        assert issue.key == "AIEV-42"
        assert issue.summary == "Fix login bug"
        assert issue.status == "To Do"
        assert issue.priority == "High"
        assert issue.description == "Login is broken"
        assert issue.assignee == "Test User"
        assert issue.issue_type == "Bug"
        assert issue.labels == ["bug", "urgent"]

    def test_from_dict_defaults(self) -> None:
        data = {"key": "X-1"}
        issue = IssueDisplay.from_dict(data)
        assert issue.key == "X-1"
        assert issue.summary == ""
        assert issue.status == "Unknown"
        assert issue.priority == "Medium"
        assert issue.assignee is None
        assert issue.labels == []

    def test_from_dict_none_assignee(self) -> None:
        data = {"key": "X-1", "assignee": None}
        issue = IssueDisplay.from_dict(data)
        assert issue.assignee is None
