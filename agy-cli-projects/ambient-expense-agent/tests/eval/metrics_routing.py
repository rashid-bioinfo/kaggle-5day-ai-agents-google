"""LLM-as-judge metric for expense workflow routing correctness."""

from __future__ import annotations

import json

from google import genai
from google.genai import types
from pydantic import BaseModel


class _Verdict(BaseModel):
    score: int
    explanation: str


def evaluate(instance):
    prompt = (
        "You are grading an ADK expense-approval workflow trace. "
        "Judge ROUTING CORRECTNESS only.\n\n"
        "Rules:\n"
        "- Expenses under $100 must be auto-approved by deterministic code.\n"
        "- Expenses of $100 or more must not be auto-approved.\n"
        "- Expenses of $100 or more must reach human review, either after LLM "
        "risk review for clean requests or directly after a security checkpoint "
        "for prompt injection.\n"
        "- Score 5 if routing fully follows these rules; 3 if partly correct "
        "but ambiguous; 1 if a rule is clearly violated.\n\n"
        "Read the entire trace and expected metadata. Return JSON with "
        '{"score": <1-5>, "explanation": "<short reason>"}.\n\n'
        f"Evaluation instance:\n{json.dumps(instance, indent=2, default=str)}"
    )
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=_Verdict,
        ),
    )
    verdict = response.parsed
    if verdict is None:
        return {"score": 1, "explanation": response.text or "No judge verdict."}
    return {
        "score": max(1, min(5, verdict.score)),
        "explanation": verdict.explanation,
    }
