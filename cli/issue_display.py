"""Provider-agnostic issue display model.

Used by CLI commands to display issues fetched from the Lambda backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IssueDisplay:
    """Represents an issue with essential fields for CLI display."""

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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IssueDisplay:
        """Create an IssueDisplay from a dict returned by the Lambda backend."""
        return cls(
            key=data.get("key", ""),
            summary=data.get("summary", ""),
            status=data.get("status", "Unknown"),
            priority=data.get("priority", "Medium"),
            description=data.get("description", ""),
            assignee=data.get("assignee"),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            url=data.get("url", ""),
            issue_type=data.get("issue_type", ""),
            labels=data.get("labels", []),
        )
