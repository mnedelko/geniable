"""Evaluation request/response models."""

from typing import Any

from pydantic import BaseModel, Field


class SingleEvaluationRequest(BaseModel):
    """Single evaluation tool request."""

    tool: str
    input: dict[str, Any]


class EvaluationRequest(BaseModel):
    """Batch evaluation request."""

    thread_id: str
    evaluations: list[SingleEvaluationRequest]


class EvaluationResult(BaseModel):
    """Result from a single evaluation."""

    tool: str
    status: str
    score: float
    message: str | None = None
    execution_time_ms: int = 0
    error: str | None = None
    details: dict[str, Any] | None = None


class EvaluationSummary(BaseModel):
    """Summary of batch evaluation results."""

    total_evaluations: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    errors: int = 0


class EvaluationResponse(BaseModel):
    """Response from batch evaluation."""

    thread_id: str
    execution_id: str
    timestamp: str
    results: list[EvaluationResult] = Field(default_factory=list)
    summary: EvaluationSummary = Field(default_factory=EvaluationSummary)
