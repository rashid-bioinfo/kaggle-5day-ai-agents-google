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

from google.adk.agents import LlmAgent
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.workflow import Workflow
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from pydantic import BaseModel, Field


class Classification(BaseModel):
    category: str = Field(description="Must be either 'shipping' or 'unrelated'")


# Classifier Agent to determine if the query is related to shipping
classifier = LlmAgent(
    name="classifier",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "Classify if the user query is related to shipping (rates, tracking, delivery, returns) "
        "or unrelated. Respond with 'shipping' or 'unrelated' in the category field."
    ),
    output_schema=Classification,
)


# Router node based on classification category
def route_by_category(node_input: dict) -> Event:
    category = node_input.get("category", "unrelated").strip().lower()
    if category == "shipping":
        return Event(output=None, route="shipping")
    return Event(output=None, route="unrelated")


# Shipping FAQ Agent to handle shipping queries
shipping_faq_agent = LlmAgent(
    name="shipping_faq_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a helpful customer support representative for a shipping company. "
        "Answer the user's shipping-related questions (rates, tracking, delivery, returns) "
        "politely and accurately."
    ),
)


# Decline node for unrelated queries
def decline_node(ctx: Context) -> Event:
    response = (
        "I apologize, but I can only assist with shipping-related inquiries "
        "(rates, tracking, delivery, returns). How can I help you today?"
    )
    return Event(
        output=response,
        content=types.Content(role='model', parts=[types.Part.from_text(text=response)])
    )


# Define the Workflow graph using the RoutingMap dict pattern for conditional routing
root_agent = Workflow(
    name="customer_support_workflow",
    edges=[
        ('START', classifier),
        (classifier, route_by_category),
        (route_by_category, {
            "shipping": shipping_faq_agent,
            "unrelated": decline_node
        }),
    ],
)

app = App(
root_agent=root_agent,
name='app',
)
