"""Tests for the issues command module."""

from __future__ import annotations

from cli.commands.issues import _build_resolve_prompt, _format_priority_style
from cli.issue_display import IssueDisplay

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_issue(
    key: str = "AIEV-37",
    summary: str = "Fix authentication timeout in login flow",
    status: str = "To Do",
    priority: str = "High",
    description: str = "The login flow times out after 30 seconds.",
    assignee: str | None = "Test User",
    issue_type: str = "Bug",
    labels: list[str] | None = None,
) -> IssueDisplay:
    return IssueDisplay(
        key=key,
        summary=summary,
        status=status,
        priority=priority,
        description=description,
        assignee=assignee,
        created="2025-01-01T00:00:00.000+0000",
        updated="2025-01-15T00:00:00.000+0000",
        url=f"https://test.atlassian.net/browse/{key}",
        issue_type=issue_type,
        labels=labels or [],
    )


# ---------------------------------------------------------------------------
# Prompt Building Tests
# ---------------------------------------------------------------------------


class TestBuildResolvePrompt:
    """Tests for _build_resolve_prompt."""

    def test_contains_issue_key(self) -> None:
        issue = _make_issue(key="AIEV-42")
        prompt = _build_resolve_prompt(issue)
        assert "AIEV-42" in prompt

    def test_contains_summary(self) -> None:
        issue = _make_issue(summary="Fix the login bug")
        prompt = _build_resolve_prompt(issue)
        assert "Fix the login bug" in prompt

    def test_contains_priority(self) -> None:
        issue = _make_issue(priority="Critical")
        prompt = _build_resolve_prompt(issue)
        assert "Critical" in prompt

    def test_contains_description(self) -> None:
        issue = _make_issue(description="Detailed description of the problem")
        prompt = _build_resolve_prompt(issue)
        assert "Detailed description of the problem" in prompt

    def test_contains_url(self) -> None:
        issue = _make_issue(key="AIEV-99")
        prompt = _build_resolve_prompt(issue)
        assert "https://test.atlassian.net/browse/AIEV-99" in prompt

    def test_empty_description(self) -> None:
        issue = _make_issue(description="")
        prompt = _build_resolve_prompt(issue)
        # Should still be valid prompt without crashing
        assert "AIEV-37" in prompt

    def test_unassigned_shows_unassigned(self) -> None:
        issue = _make_issue(assignee=None)
        prompt = _build_resolve_prompt(issue)
        assert "Unassigned" in prompt

    def test_labels_included(self) -> None:
        issue = _make_issue(labels=["bug", "urgent"])
        prompt = _build_resolve_prompt(issue)
        assert "bug" in prompt
        assert "urgent" in prompt

    def test_no_labels_no_labels_section(self) -> None:
        issue = _make_issue(labels=[])
        prompt = _build_resolve_prompt(issue)
        assert "Labels" not in prompt

    def test_contains_workflow_steps(self) -> None:
        issue = _make_issue()
        prompt = _build_resolve_prompt(issue)
        assert "Understand" in prompt
        assert "Research" in prompt
        assert "Explore" in prompt
        assert "Plan" in prompt
        assert "Confirm" in prompt
        assert "Execute" in prompt
        assert "Verify" in prompt
        assert "Close Issue" in prompt

    def test_contains_mark_done_command(self) -> None:
        issue = _make_issue(key="AIEV-42")
        prompt = _build_resolve_prompt(issue)
        assert "geni issues mark-done AIEV-42" in prompt

    def test_mark_done_step_asks_user(self) -> None:
        issue = _make_issue()
        prompt = _build_resolve_prompt(issue)
        assert "mark" in prompt.lower() and "Done" in prompt


# ---------------------------------------------------------------------------
# Priority Styling Tests
# ---------------------------------------------------------------------------


class TestFormatPriorityStyle:
    """Tests for _format_priority_style."""

    def test_high_is_red(self) -> None:
        result = _format_priority_style("High")
        assert "[red]" in result
        assert "High" in result

    def test_critical_is_bold_red(self) -> None:
        result = _format_priority_style("Highest")
        assert "[bold red]" in result

    def test_medium_is_yellow(self) -> None:
        result = _format_priority_style("Medium")
        assert "[yellow]" in result

    def test_low_is_green(self) -> None:
        result = _format_priority_style("Low")
        assert "[green]" in result

    def test_unknown_unchanged(self) -> None:
        result = _format_priority_style("Custom")
        assert result == "Custom"
