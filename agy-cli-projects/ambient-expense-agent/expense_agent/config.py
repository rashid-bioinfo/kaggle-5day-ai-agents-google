"""Configuration for the ambient expense approval workflow."""

APP_NAME = "app"
AUTO_APPROVE_THRESHOLD_USD = 100.0
MODEL_NAME = "gemini-3.1-flash-lite"
HUMAN_REVIEW_INTERRUPT_ID = "expense_human_review"
PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "bypass",
    "override",
    "force auto-approval",
    "force approval",
    "auto approve no matter what",
    "do not send to human",
    "do not ask for human review",
    "approve this expense",
)
