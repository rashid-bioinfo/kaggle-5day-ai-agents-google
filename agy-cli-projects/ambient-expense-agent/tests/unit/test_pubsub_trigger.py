import base64
import json

from fastapi.testclient import TestClient

from app.fast_api_app import app
from app.fast_api_app import normalize_subscription_name


def test_normalize_subscription_name() -> None:
    assert (
        normalize_subscription_name(
            "projects/demo/subscriptions/expense-events"
        )
        == "expense-events"
    )
    assert normalize_subscription_name("expense-events") == "expense-events"


def test_pubsub_trigger_low_value_expense_runs_workflow() -> None:
    expense = {
        "amount": 42.0,
        "submitter": "alice@company.com",
        "category": "software",
        "description": "IDE License",
        "date": "2026-06-06",
    }
    envelope = {
        "subscription": "projects/demo/subscriptions/expense-events",
        "message": {
            "messageId": "unit-test-42",
            "data": base64.b64encode(json.dumps(expense).encode()).decode(),
        },
    }

    with TestClient(app) as client:
        response = client.post("/triggers/pubsub", json=envelope)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["subscription"] == "expense-events"
    assert body["message_id"] == "unit-test-42"
    assert body["session_id"].startswith("pubsub-expense-events-unit-test-42-")
    assert body["final_event"]["output"]["status"] == "approved"
