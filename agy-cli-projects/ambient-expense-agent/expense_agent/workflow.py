# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import base64
import json
import re
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import Workflow
from google.adk.workflow import node
from google.genai import types

from .config import APP_NAME
from .config import AUTO_APPROVE_THRESHOLD_USD
from .config import HUMAN_REVIEW_INTERRUPT_ID
from .config import MODEL_NAME
from .config import PROMPT_INJECTION_PATTERNS
from .schemas import ApprovalRecord
from .schemas import Expense
from .schemas import HumanDecision
from .schemas import RiskReview
from .schemas import RoutedExpense
from .schemas import SecurityReport


SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_RE = re.compile(
    r"\b(?:\d[ -]*?){13,19}\b",
)


def _content_text(node_input: Any) -> str:
    """Extract text from ADK Content or return string input as-is."""
    if isinstance(node_input, str):
        return node_input
    if isinstance(node_input, dict):
        return json.dumps(node_input)
    parts = getattr(node_input, "parts", None) or []
    text_parts = [part.text for part in parts if getattr(part, "text", None)]
    if text_parts:
        return "\n".join(text_parts)
    raise ValueError("Expense event must be JSON text or a JSON-like dict.")


def _decode_data_payload(data: Any) -> dict[str, Any]:
    """Decode Pub/Sub-style data that may be base64 JSON or plain JSON."""
    if isinstance(data, dict):
        return data
    if not isinstance(data, str):
        raise ValueError("Expense event data must be a JSON object or string.")

    try:
        decoded = base64.b64decode(data, validate=True).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return json.loads(data)


def _load_json_object_from_text(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object, allowing explanatory text around it in the UI."""
    decoder = json.JSONDecoder()
    stripped = raw_text.strip()
    if stripped.startswith("{"):
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
        raise ValueError("Expense event must be a JSON object.")

    for start in (index for index, char in enumerate(raw_text) if char == "{"):
        try:
            value, _ = decoder.raw_decode(raw_text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    raise json.JSONDecodeError("No JSON object found", raw_text, 0)


def _looks_like_credit_card(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    if not 13 <= len(digits) <= 19:
        return False

    total = 0
    reverse_digits = digits[::-1]
    for index, digit in enumerate(reverse_digits):
        value = int(digit)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def scrub_description(description: str) -> tuple[str, list[str]]:
    """Redact PII before text enters workflow state, model input, or logs."""
    redacted_categories: list[str] = []

    scrubbed, ssn_count = SSN_RE.subn("[REDACTED_SSN]", description)
    if ssn_count:
        redacted_categories.append("ssn")

    def redact_card(match: re.Match[str]) -> str:
        candidate = match.group(0)
        if _looks_like_credit_card(candidate):
            if "credit_card" not in redacted_categories:
                redacted_categories.append("credit_card")
            return "[REDACTED_CREDIT_CARD]"
        return candidate

    scrubbed = CREDIT_CARD_RE.sub(redact_card, scrubbed)
    return scrubbed, redacted_categories


def _detect_prompt_injection(description: str) -> list[str]:
    lowered = description.lower()
    return [pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in lowered]


def parse_expense_event(node_input: Any) -> Event:
    """Extract and validate an expense from a Pub/Sub or local JSON event."""
    raw_text = _content_text(node_input).strip()
    try:
        raw_event = _load_json_object_from_text(raw_text)
        pubsub_message = raw_event.get("message")
        if isinstance(pubsub_message, dict):
            expense_payload = _decode_data_payload(
                pubsub_message.get("data", pubsub_message)
            )
        else:
            expense_payload = _decode_data_payload(raw_event.get("data", raw_event))
        expense = Expense(**expense_payload)
    except Exception as exc:
        message = (
            "This workflow expects an expense JSON event. Paste an object like "
            '{"amount": 150.0, "submitter": "alice@company.com", '
            '"category": "software", "description": "IDE License", '
            '"date": "2026-06-06"}.'
        )
        return Event(
            output={"error": type(exc).__name__, "message": message},
            route="invalid_input",
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=message)],
            ),
        )

    clean_description, redacted_categories = scrub_description(
        str(expense_payload.get("description", ""))
    )
    expense_payload["description"] = clean_description
    expense = Expense(**expense_payload)
    return Event(
        output={
            **expense.model_dump(),
            "redacted_categories": redacted_categories,
        },
        state={
            "expense": expense.model_dump(),
            "redacted_categories": redacted_categories,
        },
        route="expense",
    )


def explain_invalid_input(node_input: dict[str, Any]) -> Event:
    """Return a playground-friendly message for non-expense chat input."""
    message = node_input["message"]
    return Event(
        output=node_input,
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=message)],
        ),
    )


def route_by_amount(node_input: dict[str, Any]) -> Event:
    """Apply the deterministic threshold policy before any LLM is called."""
    expense = Expense(**node_input)
    redacted_categories = list(node_input.get("redacted_categories") or [])
    route = (
        "auto_approve"
        if expense.amount < AUTO_APPROVE_THRESHOLD_USD
        else "risk_review"
    )
    routed = RoutedExpense(
        expense=expense,
        route=route,
        threshold=AUTO_APPROVE_THRESHOLD_USD,
        redacted_categories=redacted_categories,
    )
    return Event(
        output=routed.model_dump(),
        route=route,
        state={
            "expense": expense.model_dump(),
            "threshold": AUTO_APPROVE_THRESHOLD_USD,
            "route": route,
        },
    )


def auto_approve(node_input: dict[str, Any]) -> Event:
    """Approve low-value expenses without calling an LLM."""
    routed = RoutedExpense(**node_input)
    record = ApprovalRecord(
        status="approved",
        expense=routed.expense,
        reason=(
            f"Auto-approved because amount ${routed.expense.amount:.2f} is "
            f"below the ${routed.threshold:.2f} threshold."
        ),
        threshold=routed.threshold,
        security_report={
            "redacted_categories": routed.redacted_categories,
            "security_event": False,
            "prompt_injection_detected": False,
        },
    )
    return Event(
        output=record.model_dump(),
        state={"approval_record": record.model_dump()},
    )


def security_checkpoint(
    node_input: dict[str, Any], ctx: Context | None = None
) -> Event:
    """Scrubbed high-value expense checkpoint before LLM review."""
    routed = RoutedExpense(**node_input)
    redacted_categories = list(routed.redacted_categories)
    if ctx is not None:
        redacted_categories = list(
            ctx.state.get("redacted_categories") or redacted_categories
        )
    matched_patterns = _detect_prompt_injection(routed.expense.description)
    security_event = bool(matched_patterns)
    report = SecurityReport(
        expense=routed.expense,
        prompt_injection_detected=security_event,
        security_event=security_event,
        redacted_categories=redacted_categories,
        matched_patterns=matched_patterns,
        route="security_event" if security_event else "clean",
    )
    return Event(
        output=report.model_dump(),
        route=report.route,
        state={
            "expense": routed.expense.model_dump(),
            "security_report": report.model_dump(),
            "redacted_categories": redacted_categories,
        },
    )


risk_review_agent = LlmAgent(
    name="risk_review_agent",
    model=MODEL_NAME,
    instruction=(
        "You are a corporate expense compliance reviewer. Review only the "
        "expense report provided as input. Identify reimbursement risk factors "
        "such as unusually high value, vague descriptions, policy-sensitive "
        "categories, missing business purpose, duplicate-looking requests, or "
        "items that should require manager review. Return a concise alert and "
        "a recommended action. Do not approve or reject finally; high-value "
        "expenses always proceed to human review."
    ),
    output_schema=RiskReview,
    output_key="risk_review",
)


@node(rerun_on_resume=True)
async def request_human_review(ctx: Context, node_input: dict[str, Any]):
    """Pause for a human approve/reject decision after LLM risk review."""
    if HUMAN_REVIEW_INTERRUPT_ID not in (ctx.resume_inputs or {}):
        expense = Expense(**ctx.state["expense"])
        security_report_data = ctx.state.get("security_report") or {}
        security_report = (
            SecurityReport(**security_report_data) if security_report_data else None
        )
        risk_review = None
        if security_report and security_report.security_event:
            review_summary = (
                "Security event: prompt-injection attempt detected. "
                f"Matched patterns: {', '.join(security_report.matched_patterns)}"
            )
        else:
            risk_review = RiskReview(**node_input)
            review_summary = (
                f"Risk level: {risk_review.risk_level}\n"
                f"Alert: {risk_review.alert}"
            )
        yield RequestInput(
            interrupt_id=HUMAN_REVIEW_INTERRUPT_ID,
            message=(
                "Human review required for high-value expense.\n"
                f"Submitter: {expense.submitter}\n"
                f"Amount: ${expense.amount:.2f}\n"
                f"Category: {expense.category}\n"
                f"Description: {expense.description}\n"
                f"Date: {expense.date}\n"
                f"{review_summary}\n"
                f"Redactions: {', '.join(ctx.state.get('redacted_categories') or []) or 'none'}\n"
                "Respond with decision='approve' or decision='reject', plus "
                "optional reviewer and notes."
            ),
            payload={
                "expense": expense.model_dump(),
                "risk_review": risk_review.model_dump() if risk_review else None,
                "security_report": security_report.model_dump()
                if security_report
                else None,
            },
            response_schema=HumanDecision,
        )
        return

    decision = HumanDecision(**ctx.resume_inputs[HUMAN_REVIEW_INTERRUPT_ID])
    expense = Expense(**ctx.state["expense"])
    risk_review_data = ctx.state.get("risk_review")
    security_report_data = ctx.state.get("security_report")
    risk_review = RiskReview(**risk_review_data) if risk_review_data else None
    status = "approved" if decision.decision == "approve" else "rejected"
    record = ApprovalRecord(
        status=status,
        expense=expense,
        reason=f"Human reviewer {decision.reviewer} chose to {decision.decision}.",
        threshold=float(ctx.state.get("threshold", AUTO_APPROVE_THRESHOLD_USD)),
        risk_review=risk_review.model_dump() if risk_review else None,
        security_report=security_report_data,
        human_decision=decision.model_dump(),
    )
    yield Event(
        output=record.model_dump(),
        state={
            "human_decision": decision.model_dump(),
            "approval_record": record.model_dump(),
        },
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text=(
                        f"Expense {status}. "
                        f"Reviewer: {decision.reviewer}. Notes: {decision.notes}"
                    )
                )
            ],
        ),
    )


root_agent = Workflow(
    name="ambient_expense_workflow",
    description=(
        "Event-driven expense approval workflow with deterministic low-value "
        "approval, LLM risk review for high-value expenses, and human approval."
    ),
    edges=[
        ("START", parse_expense_event),
        (
            parse_expense_event,
            {
                "expense": route_by_amount,
                "invalid_input": explain_invalid_input,
            },
        ),
        (
            route_by_amount,
            {
                "auto_approve": auto_approve,
                "risk_review": security_checkpoint,
            },
        ),
        (
            security_checkpoint,
            {
                "clean": risk_review_agent,
                "security_event": request_human_review,
            },
        ),
        (risk_review_agent, request_human_review),
    ],
)

app = App(
    root_agent=root_agent,
    name=APP_NAME,
)
