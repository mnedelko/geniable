"""Direct Jira REST API client for querying issues.

Lightweight client that queries Jira directly using basic auth,
bypassing the Lambda backend for responsiveness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)


@dataclass
class JiraIssue:
    """Represents a Jira issue with essential fields."""

    key: str
    summary: str
    status: str
    priority: str
    description: str
    assignee: str | None
    created: str
    updated: str
    url: str
    issue_type: str = ""
    labels: list[str] = field(default_factory=list)

    @property
    def priority_sort_key(self) -> int:
        """Return numeric sort key for priority (lower = higher priority)."""
        priority_order = {
            "highest": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "lowest": 4,
        }
        return priority_order.get(self.priority.lower(), 5)


def _extract_text_from_adf(adf: dict | list | str | None) -> str:
    """Extract plain text from Atlassian Document Format (ADF).

    ADF is a nested JSON structure used by Jira Cloud v3 API.
    This recursively walks the document tree and extracts text content.

    Args:
        adf: ADF document node (dict with 'type' and 'content'),
             a list of nodes, a plain string, or None

    Returns:
        Plain text extracted from the ADF document
    """
    if adf is None:
        return ""

    if isinstance(adf, str):
        return adf

    if isinstance(adf, list):
        return "".join(_extract_text_from_adf(item) for item in adf)

    if not isinstance(adf, dict):
        return ""

    node_type: str = adf.get("type", "")
    text: str = adf.get("text", "")

    # For text nodes, return the text directly
    if node_type == "text":
        return str(text)

    # For container nodes, recurse into content
    content = adf.get("content", [])
    extracted = "".join(_extract_text_from_adf(child) for child in content)

    # Add newlines for block-level elements
    if node_type in ("paragraph", "heading", "bulletList", "orderedList", "blockquote"):
        extracted = extracted.strip() + "\n"
    elif node_type == "listItem":
        extracted = "- " + extracted.strip() + "\n"
    elif node_type == "hardBreak":
        extracted = "\n"
    elif node_type == "codeBlock":
        extracted = "```\n" + extracted.strip() + "\n```\n"

    return extracted


class JiraClient:
    """Direct Jira REST API client using basic auth."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        """Initialize the Jira client.

        Args:
            base_url: Jira instance URL (e.g., https://company.atlassian.net)
            email: Jira user email for basic auth
            api_token: Jira API token for basic auth
        """
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.session = requests.Session()
        self.session.auth = (email, api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def search_issues(
        self,
        project_key: str,
        max_results: int = 50,
    ) -> list[JiraIssue]:
        """Search for open issues in a project.

        Uses JQL to find issues that are not in the "Done" status category,
        ordered by priority (descending) then updated date (descending).

        Args:
            project_key: Jira project key (e.g., "AIEV")
            max_results: Maximum number of results to return

        Returns:
            List of JiraIssue objects

        Raises:
            requests.HTTPError: If the API request fails
        """
        jql = (
            f'project = "{project_key}" '
            f'AND statusCategory != "Done" '
            f"ORDER BY priority ASC, updated DESC"
        )

        fields = "summary,status,priority,description,assignee,created,updated,issuetype,labels"

        # Try GET first, fall back to POST if 410 (Atlassian deprecation)
        try:
            return self._search_get(jql, fields, max_results)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 410:
                logger.info("GET search returned 410, falling back to POST search")
                return self._search_post(jql, fields, max_results)
            raise

    def _search_get(self, jql: str, fields: str, max_results: int) -> list[JiraIssue]:
        """Search issues using GET /rest/api/3/search."""
        url = f"{self.base_url}/rest/api/3/search"
        params: dict[str, str | int] = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results,
        }

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        return self._parse_issues(data.get("issues", []))

    def _search_post(self, jql: str, fields: str, max_results: int) -> list[JiraIssue]:
        """Search issues using POST /rest/api/3/search (fallback)."""
        url = f"{self.base_url}/rest/api/3/search"
        payload = {
            "jql": jql,
            "fields": [f.strip() for f in fields.split(",")],
            "maxResults": max_results,
        }

        response = self.session.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        return self._parse_issues(data.get("issues", []))

    def get_issue(self, issue_key: str) -> JiraIssue:
        """Get a single issue by key.

        Args:
            issue_key: Issue key (e.g., "AIEV-37")

        Returns:
            JiraIssue object

        Raises:
            requests.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        params = {
            "fields": "summary,status,priority,description,assignee,created,updated,issuetype,labels",
        }

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        issues = self._parse_issues([data])
        return issues[0]

    def transition_issue(self, issue_key: str, target_status: str = "Done") -> None:
        """Transition an issue to a target status.

        Finds the available transition matching the target status name
        and applies it. Jira transitions are workflow-specific, so the
        exact transition ID must be discovered at runtime.

        Args:
            issue_key: Issue key (e.g., "AIEV-37")
            target_status: Target status name to transition to (default: "Done")

        Raises:
            requests.HTTPError: If the API request fails
            ValueError: If no matching transition is found
        """
        # Get available transitions for this issue
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        transitions = response.json().get("transitions", [])

        # Find the transition matching the target status (case-insensitive)
        transition_id = None
        for t in transitions:
            if t.get("name", "").lower() == target_status.lower():
                transition_id = t["id"]
                break
            # Also check the "to" status name
            to_status = t.get("to", {}).get("name", "")
            if to_status.lower() == target_status.lower():
                transition_id = t["id"]
                break

        if transition_id is None:
            available = [t.get("name", "unknown") for t in transitions]
            raise ValueError(
                f"No '{target_status}' transition available for {issue_key}. "
                f"Available transitions: {', '.join(available)}"
            )

        # Apply the transition
        payload = {"transition": {"id": transition_id}}
        response = self.session.post(url, json=payload, timeout=30)
        response.raise_for_status()

        logger.info(
            "Transitioned %s to '%s' (transition ID: %s)", issue_key, target_status, transition_id
        )

    def _parse_issues(self, issues_data: list[dict]) -> list[JiraIssue]:
        """Parse raw Jira API issue data into JiraIssue objects.

        Args:
            issues_data: List of issue dicts from Jira API

        Returns:
            List of JiraIssue objects
        """
        issues = []
        for issue in issues_data:
            fields = issue.get("fields", {})

            # Extract status name
            status_obj = fields.get("status", {})
            status = status_obj.get("name", "Unknown") if status_obj else "Unknown"

            # Extract priority name
            priority_obj = fields.get("priority", {})
            priority = priority_obj.get("name", "Medium") if priority_obj else "Medium"

            # Extract description (may be ADF or plain text)
            raw_description = fields.get("description")
            description = _extract_text_from_adf(raw_description).strip()

            # Extract assignee
            assignee_obj = fields.get("assignee")
            assignee = (
                assignee_obj.get("displayName", assignee_obj.get("emailAddress"))
                if assignee_obj
                else None
            )

            # Extract issue type
            issuetype_obj = fields.get("issuetype", {})
            issue_type = issuetype_obj.get("name", "") if issuetype_obj else ""

            # Extract labels
            labels = fields.get("labels", []) or []

            # Build issue URL
            key = issue.get("key", "")
            url = f"{self.base_url}/browse/{key}"

            issues.append(
                JiraIssue(
                    key=key,
                    summary=fields.get("summary", ""),
                    status=status,
                    priority=priority,
                    description=description,
                    assignee=assignee,
                    created=fields.get("created", ""),
                    updated=fields.get("updated", ""),
                    url=url,
                    issue_type=issue_type,
                    labels=labels,
                )
            )

        return issues
