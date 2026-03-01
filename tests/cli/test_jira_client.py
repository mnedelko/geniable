"""Tests for the Jira REST API client."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests

from cli.jira_client import JiraClient, JiraIssue, _extract_text_from_adf

# ---------------------------------------------------------------------------
# ADF Text Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractTextFromADF:
    """Tests for _extract_text_from_adf helper."""

    def test_none_returns_empty(self) -> None:
        assert _extract_text_from_adf(None) == ""

    def test_plain_string_passthrough(self) -> None:
        assert _extract_text_from_adf("hello world") == "hello world"

    def test_simple_paragraph(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }
        result = _extract_text_from_adf(adf)
        assert "Hello world" in result

    def test_multiple_paragraphs(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "First paragraph"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second paragraph"}],
                },
            ],
        }
        result = _extract_text_from_adf(adf)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_bullet_list(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 1"}],
                                }
                            ],
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 2"}],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        result = _extract_text_from_adf(adf)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_code_block(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "codeBlock",
                    "content": [{"type": "text", "text": "print('hello')"}],
                }
            ],
        }
        result = _extract_text_from_adf(adf)
        assert "print('hello')" in result
        assert "```" in result

    def test_empty_dict(self) -> None:
        assert _extract_text_from_adf({}) == ""

    def test_list_input(self) -> None:
        result = _extract_text_from_adf(
            [
                {"type": "text", "text": "a"},
                {"type": "text", "text": "b"},
            ]
        )
        assert result == "ab"

    def test_non_dict_non_string(self) -> None:
        assert _extract_text_from_adf(42) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# JiraIssue Tests
# ---------------------------------------------------------------------------


class TestJiraIssue:
    """Tests for JiraIssue dataclass."""

    def test_priority_sort_key(self) -> None:
        high = JiraIssue(
            key="X-1",
            summary="",
            status="",
            priority="High",
            description="",
            assignee=None,
            created="",
            updated="",
            url="",
        )
        medium = JiraIssue(
            key="X-2",
            summary="",
            status="",
            priority="Medium",
            description="",
            assignee=None,
            created="",
            updated="",
            url="",
        )
        low = JiraIssue(
            key="X-3",
            summary="",
            status="",
            priority="Low",
            description="",
            assignee=None,
            created="",
            updated="",
            url="",
        )
        assert high.priority_sort_key < medium.priority_sort_key < low.priority_sort_key

    def test_unknown_priority_sort_key(self) -> None:
        issue = JiraIssue(
            key="X-1",
            summary="",
            status="",
            priority="Custom",
            description="",
            assignee=None,
            created="",
            updated="",
            url="",
        )
        assert issue.priority_sort_key == 5


# ---------------------------------------------------------------------------
# JiraClient Tests
# ---------------------------------------------------------------------------


def _make_api_issue(
    key: str = "PROJ-1",
    summary: str = "Test issue",
    status: str = "To Do",
    priority: str = "High",
    description: str | dict | None = None,
    assignee: str | None = "Test User",
    issue_type: str = "Bug",
    labels: list[str] | None = None,
) -> dict:
    """Build a mock Jira API issue response."""
    fields: dict = {
        "summary": summary,
        "status": {"name": status},
        "priority": {"name": priority},
        "description": description,
        "assignee": {"displayName": assignee} if assignee else None,
        "created": "2025-01-01T00:00:00.000+0000",
        "updated": "2025-01-15T00:00:00.000+0000",
        "issuetype": {"name": issue_type},
        "labels": labels or [],
    }
    return {"key": key, "fields": fields}


class TestJiraClient:
    """Tests for JiraClient."""

    def setup_method(self) -> None:
        self.client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )

    def test_init_strips_trailing_slash(self) -> None:
        client = JiraClient(
            base_url="https://test.atlassian.net/",
            email="test@example.com",
            api_token="test-token",
        )
        assert client.base_url == "https://test.atlassian.net"

    def test_search_issues_get(self) -> None:
        """Test search_issues using GET endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "issues": [
                _make_api_issue("PROJ-1", "Issue 1", "To Do", "High"),
                _make_api_issue("PROJ-2", "Issue 2", "In Progress", "Medium"),
            ]
        }
        mock_response.raise_for_status = MagicMock()

        # Override the session on our existing client
        self.client.session.get = MagicMock(return_value=mock_response)

        issues = self.client.search_issues("PROJ")

        assert len(issues) == 2
        assert issues[0].key == "PROJ-1"
        assert issues[0].summary == "Issue 1"
        assert issues[0].status == "To Do"
        assert issues[0].priority == "High"
        assert issues[1].key == "PROJ-2"

    def test_search_issues_fallback_to_post(self) -> None:
        """Test search_issues falls back to POST on 410."""
        # GET returns 410
        mock_410 = MagicMock()
        mock_410.status_code = 410
        http_error = requests.HTTPError(response=mock_410)
        self.client.session.get = MagicMock(side_effect=http_error)

        # POST succeeds
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"issues": [_make_api_issue("PROJ-1", "Issue 1")]}
        mock_post_response.raise_for_status = MagicMock()
        self.client.session.post = MagicMock(return_value=mock_post_response)

        issues = self.client.search_issues("PROJ")

        assert len(issues) == 1
        assert issues[0].key == "PROJ-1"
        self.client.session.post.assert_called_once()

    def test_get_issue(self) -> None:
        """Test get_issue fetches a single issue."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_issue(
            "PROJ-42", "Fix login bug", "In Progress", "High"
        )
        mock_response.raise_for_status = MagicMock()
        self.client.session.get = MagicMock(return_value=mock_response)

        issue = self.client.get_issue("PROJ-42")

        assert issue.key == "PROJ-42"
        assert issue.summary == "Fix login bug"
        assert issue.status == "In Progress"
        assert issue.url == "https://test.atlassian.net/browse/PROJ-42"

    def test_parse_adf_description(self) -> None:
        """Test that ADF descriptions are converted to plain text."""
        adf_description = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Fix the authentication timeout"}],
                }
            ],
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_issue(
            "PROJ-1", "Auth timeout", description=adf_description
        )
        mock_response.raise_for_status = MagicMock()
        self.client.session.get = MagicMock(return_value=mock_response)

        issue = self.client.get_issue("PROJ-1")

        assert "Fix the authentication timeout" in issue.description

    def test_parse_null_assignee(self) -> None:
        """Test that null assignee is handled."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_issue(
            "PROJ-1", "Unassigned issue", assignee=None
        )
        mock_response.raise_for_status = MagicMock()
        self.client.session.get = MagicMock(return_value=mock_response)

        issue = self.client.get_issue("PROJ-1")

        assert issue.assignee is None

    def test_parse_labels(self) -> None:
        """Test that labels are parsed correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_issue(
            "PROJ-1", "Labeled issue", labels=["bug", "urgent"]
        )
        mock_response.raise_for_status = MagicMock()
        self.client.session.get = MagicMock(return_value=mock_response)

        issue = self.client.get_issue("PROJ-1")

        assert issue.labels == ["bug", "urgent"]

    def test_jql_construction(self) -> None:
        """Test that the JQL query is constructed correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"issues": []}
        mock_response.raise_for_status = MagicMock()
        self.client.session.get = MagicMock(return_value=mock_response)

        self.client.search_issues("AIEV", max_results=25)

        call_args = self.client.session.get.call_args
        params = call_args[1]["params"]
        assert 'project = "AIEV"' in params["jql"]
        assert 'statusCategory != "Done"' in params["jql"]
        assert params["maxResults"] == 25
