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

import contextlib
import json
import logging
import os
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.genai import types
from pydantic import BaseModel, Field

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
setup_telemetry()
logger = logging.getLogger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PubSubMessage(BaseModel):
    data: str | None = None
    message_id: str | None = Field(default=None, alias="messageId")
    messageId: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    publish_time: str | None = Field(default=None, alias="publishTime")


class PubSubPushEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str


def normalize_subscription_name(subscription: str) -> str:
    """Collapse a fully-qualified Pub/Sub subscription path to its short name."""
    cleaned = subscription.strip().rstrip("/")
    return cleaned.rsplit("/", 1)[-1] if "/" in cleaned else cleaned


def _safe_record_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned or uuid.uuid4().hex


def _event_to_jsonable(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json", exclude_none=True)
    return {"repr": repr(event)}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "ambient-expense-agent"
app.description = "API for interacting with the Agent ambient-expense-agent"


@app.post("/triggers/pubsub")
async def trigger_pubsub(envelope: PubSubPushEnvelope) -> dict[str, Any]:
    """Accept a Pub/Sub push message and run it through the expense workflow."""
    runner: Runner = app.state.runner
    subscription_name = normalize_subscription_name(envelope.subscription)
    message_id = (
        envelope.message.message_id
        or envelope.message.messageId
        or uuid.uuid4().hex
    )
    safe_subscription = _safe_record_id(subscription_name)
    safe_message_id = _safe_record_id(message_id)
    session_id = f"pubsub-{safe_subscription}-{safe_message_id}-{uuid.uuid4().hex[:8]}"
    user_id = f"pubsub-{safe_subscription}"

    message_payload = envelope.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    session = await runner.session_service.create_session(
        app_name=app.state.agent_app_name,
        user_id=user_id,
        session_id=session_id,
        state={
            "trigger_source": "pubsub",
            "subscription": subscription_name,
            "message_id": message_id,
        },
    )
    logger.info(
        "Processing Pub/Sub trigger subscription=%s message_id=%s session_id=%s",
        subscription_name,
        message_id,
        session.id,
    )

    events: list[dict[str, Any]] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(message_payload))],
        ),
    ):
        events.append(_event_to_jsonable(event))

    logger.info(
        "Finished Pub/Sub trigger subscription=%s message_id=%s events=%s",
        subscription_name,
        message_id,
        len(events),
    )
    return {
        "status": "processed",
        "subscription": subscription_name,
        "message_id": message_id,
        "session_id": session.id,
        "event_count": len(events),
        "final_event": events[-1] if events else None,
    }


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.info("Feedback received: %s", feedback.model_dump())
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
