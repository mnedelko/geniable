"""Issue Card schema for ticket creation.

This module defines the complete Issue Card data model that is used
when creating tickets in Jira or Notion. It supports all 9 required fields
as specified in the architecture document.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AffectedCode(BaseModel):
    """Reference to affected code location with improvement suggestions."""

    file: Optional[str] = Field(default=None, description="File path")
    lines: Optional[str] = Field(default=None, description="Line range (e.g., '145-180')")
    component: Optional[str] = Field(default=None, description="Component or class name")
    function: Optional[str] = Field(default=None, description="Function or method name")
    suggestion: Optional[str] = Field(
        default=None, description="Improvement suggestion for this code"
    )


class Sources(BaseModel):
    """Thread and run references for traceability."""

    thread_id: str = Field(..., description="LangSmith thread UUID")
    thread_name: str = Field(..., description="Human-readable thread name")
    run_id: Optional[str] = Field(default=None, description="LangSmith run UUID")
    langsmith_url: Optional[str] = Field(
        default=None, description="Direct link to LangSmith thread"
    )


class EvaluationResult(BaseModel):
    """Result from a single evaluation tool."""

    tool: str = Field(..., description="Name of the evaluation tool")
    status: Literal["pass", "warning", "fail", "error"] = Field(
        ..., description="Evaluation outcome"
    )
    score: float = Field(..., ge=0, le=1, description="Normalized score (0-1)")
    message: Optional[str] = Field(default=None, description="Detailed result message")


class IssueCard(BaseModel):
    """Complete Issue Card schema for ticket creation.

    This model represents all the data needed to create an issue ticket
    in either Jira or Notion. It includes the 9 required fields plus
    additional metadata for comprehensive issue tracking.

    Required Fields:
        1. title - Issue title
        2. priority - CRITICAL, HIGH, MEDIUM, or LOW
        3. category - Issue classification
        4. status - Workflow status (default: BACKLOG)
        5. details - Detailed issue description
        6. description - Brief summary
        7. recommendation - Suggested fixes
        8. affected_code - Code location and suggestions
        9. sources - Thread ID, name, run ID
    """

    # Required fields (1-9 as per requirements)
    title: str = Field(..., min_length=1, description="Issue title")
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        default="MEDIUM", description="Issue priority level"
    )
    category: Literal[
        "BUG",
        "PERFORMANCE",
        "OPTIMIZATION",
        "FEATURE_IDEA",
        "DOCUMENTATION",
        "UI_UX",
        "TECHNICAL_DEBT",
        "ERROR",
        "QUALITY",
        "SECURITY",
    ] = Field(..., description="Issue category classification")
    status: str = Field(default="BACKLOG", description="Issue workflow status")
    details: str = Field(..., description="Detailed issue description with context")
    description: str = Field(..., description="Brief summary of the issue")
    recommendation: str = Field(..., description="Suggested fixes or improvement actions")
    affected_code: Optional[AffectedCode] = Field(
        default=None, description="Code location and improvement suggestions"
    )
    sources: Sources = Field(..., description="Thread and run references")

    # Additional metadata
    evaluation_results: List[EvaluationResult] = Field(
        default_factory=list, description="Results from evaluation tools"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    issue_id: Optional[str] = Field(default=None, description="Generated issue ID (e.g., IA-001)")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "title": "High Latency in Thread: User Query Processing",
                "priority": "HIGH",
                "category": "PERFORMANCE",
                "status": "BACKLOG",
                "details": "Thread execution took 45.2 seconds, exceeding the 30s threshold.",
                "description": "Performance issue affecting user experience during query processing.",
                "recommendation": "1. Investigate retrieval step bottleneck\n2. Consider caching",
                "affected_code": {
                    "file": "src/retrieval/vector_search.py",
                    "lines": "145-180",
                    "component": "VectorSearchService",
                    "function": "search_similar",
                    "suggestion": "Add connection pooling",
                },
                "sources": {
                    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
                    "thread_name": "User Query: How to configure...",
                    "run_id": "run-uuid",
                    "langsmith_url": "https://smith.langchain.com/...",
                },
                "evaluation_results": [
                    {"tool": "latency_evaluation", "status": "fail", "score": 0.3}
                ],
            }
        }
