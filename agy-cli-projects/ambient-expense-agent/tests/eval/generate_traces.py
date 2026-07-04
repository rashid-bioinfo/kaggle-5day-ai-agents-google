"""Generate local ADK workflow traces for the ambient expense agent evals."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path
import uuid
from typing import Any

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

from app.agent import app as adk_app
from expense_agent.config import HUMAN_REVIEW_INTERRUPT_ID


DEFAULT_DATASET = Path("tests/eval/datasets/basic-dataset.json")
DEFAULT_OUTPUT = Path("artifacts/traces/generated_traces.json")


def _json_dump(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _pubsub_envelope(case_id: str, expense: dict[str, Any]) -> dict[str, Any]:
    encoded = base64.b64encode(_json_dump(expense).encode()).decode()
    return {
        "subscription": "projects/local/subscriptions/expense-events",
        "message": {
            "messageId": case_id,
            "data": encoded,
            "attributes": {"source": "eval"},
        },
    }


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    texts = [part.text for part in parts if getattr(part, "text", None)]
    return "\n".join(texts)


def _event_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json", exclude_none=True)
    return {"repr": repr(event)}


def _extract_function_call(event_dict: dict[str, Any]) -> dict[str, Any] | None:
    for part in ((event_dict.get("content") or {}).get("parts") or []):
        function_call = part.get("function_call")
        if function_call:
            return function_call
    return None


def _summarize_event(event: Any) -> dict[str, Any]:
    event_dict = _event_dict(event)
    actions = event_dict.get("actions") or {}
    return {
        "author": event_dict.get("author"),
        "node_path": (event_dict.get("node_info") or {}).get("path"),
        "route": actions.get("route"),
        "state_delta": actions.get("state_delta") or {},
        "output": event_dict.get("output"),
        "long_running_tool_ids": event_dict.get("long_running_tool_ids") or [],
        "function_call": _extract_function_call(event_dict),
        "text": _content_text(event.content),
    }


def _trace_text_event(author: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "author": author,
        "content": {
            "role": "model" if author != "user" else "user",
            "parts": [{"text": _json_dump(payload)}],
        },
    }


def _human_decision(case: dict[str, Any], request_payload: dict[str, Any] | None) -> dict[str, str]:
    expected = case.get("expected") or {}
    is_security_event = bool(
        ((request_payload or {}).get("security_report") or {}).get("security_event")
    )
    should_reject = is_security_event or expected.get("prompt_injection") is True
    return {
        "decision": "reject" if should_reject else "approve",
        "reviewer": "eval_human_reviewer",
        "notes": (
            "Rejected automatically by eval harness because this is a security event."
            if should_reject
            else "Approved automatically by eval harness for a clean request."
        ),
    }


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case["eval_case_id"]
    envelope = _pubsub_envelope(case_id, case["expense"])
    prompt_text = json.dumps(envelope)
    runner = InMemoryRunner(app=adk_app)
    session = await runner.session_service.create_session(
        app_name=adk_app.name,
        user_id=f"eval-{case_id}",
        session_id=f"eval-{case_id}-{uuid.uuid4().hex[:8]}",
        state={"eval_case_id": case_id},
    )

    events = [
        _trace_text_event(
            "user",
            {
                "kind": "pubsub_trigger",
                "case_id": case_id,
                "envelope": envelope,
                "expense": case["expense"],
                "expected": case.get("expected", {}),
            },
        )
    ]
    summaries: list[dict[str, Any]] = []
    human_request_payload: dict[str, Any] | None = None

    async for event in runner.run_async(
        user_id=f"eval-{case_id}",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_text)],
        ),
    ):
        summary = _summarize_event(event)
        summaries.append(summary)
        events.append(_trace_text_event("ambient_expense_workflow", {"kind": "adk_event", **summary}))
        function_call = summary.get("function_call") or {}
        if (
            function_call.get("name") == "adk_request_input"
            or HUMAN_REVIEW_INTERRUPT_ID in summary.get("long_running_tool_ids", [])
        ):
            human_request_payload = (function_call.get("args") or {}).get("payload")

    automated_decision = None
    if human_request_payload is not None:
        automated_decision = _human_decision(case, human_request_payload)
        events.append(
            _trace_text_event(
                "human_reviewer",
                {
                    "kind": "automated_human_review",
                    "interrupt_id": HUMAN_REVIEW_INTERRUPT_ID,
                    "request_payload": human_request_payload,
                    "decision": automated_decision,
                },
            )
        )
        events.append(
            _trace_text_event(
                "ambient_expense_workflow",
                {
                    "kind": "final_human_review_outcome",
                    "status": (
                        "approved"
                        if automated_decision["decision"] == "approve"
                        else "rejected"
                    ),
                    "human_decision": automated_decision,
                },
            )
        )

    return {
        "eval_case_id": case_id,
        "expense": case["expense"],
        "expected": case.get("expected", {}),
        "automated_human_decision": automated_decision,
        "agent_data": {
            "agents": {
                "ambient_expense_workflow": {
                    "agent_id": "ambient_expense_workflow",
                    "agent_type": "ADK Workflow",
                    "instruction": "Route expense events by amount, security-screen high-value requests, use LLM risk review only for clean high-value expenses, and request human approval.",
                }
            },
            "turns": [{"turn_index": 0, "events": events}],
        },
        "trace_summary": summaries,
    }


async def _generate(dataset_path: Path, output_path: Path) -> None:
    dataset = json.loads(dataset_path.read_text())
    cases = dataset["eval_cases"]
    generated = []
    for case in cases:
        generated.append(await _run_case(case))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"eval_cases": generated}, indent=2))
    print(f"Wrote {len(generated)} traces to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    asyncio.run(_generate(args.dataset, args.output))


if __name__ == "__main__":
    main()
