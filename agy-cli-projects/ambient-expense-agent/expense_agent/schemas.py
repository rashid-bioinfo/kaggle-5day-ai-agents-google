"""Typed payloads used by the expense approval workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class Expense(BaseModel):
    """Expense report fields extracted from an event payload."""

    amount: float = Field(ge=0)
    submitter: str
    category: str
    description: str
    date: str


class RoutedExpense(BaseModel):
    """Expense plus the deterministic route chosen by Python policy."""

    expense: Expense
    route: Literal["auto_approve", "risk_review"]
    threshold: float
    redacted_categories: list[str] = Field(default_factory=list)


class SecurityReport(BaseModel):
    """Security checkpoint result before an expense can reach the LLM."""

    expense: Expense
    prompt_injection_detected: bool
    security_event: bool
    redacted_categories: list[str] = Field(default_factory=list)
    matched_patterns: list[str] = Field(default_factory=list)
    route: Literal["clean", "security_event"]


class ApprovalRecord(BaseModel):
    """Final decision record emitted by the workflow."""

    status: Literal["approved", "rejected", "needs_human_review"]
    expense: Expense
    reason: str
    threshold: float
    risk_review: dict | None = None
    security_report: dict | None = None
    human_decision: dict | None = None


class RiskReview(BaseModel):
    """Structured risk judgment returned by the LLM for high-value expenses."""

    risk_level: Literal["low", "medium", "high"]
    alert: str
    risk_factors: list[str] = Field(default_factory=list)
    recommended_action: Literal["approve", "reject", "needs_human_review"]


class HumanDecision(BaseModel):
    """Expected human response when the workflow pauses for review."""

    decision: Literal["approve", "reject"]
    reviewer: str = "human_reviewer"
    notes: str = ""
