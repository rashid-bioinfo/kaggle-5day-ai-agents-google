"""Compatibility import for the generated Agents CLI scaffold.

The codelab agent implementation lives in ``expense_agent``. The scaffolded
FastAPI/A2A runtime imports ``app.agent`` by default, so this module re-exports
the ADK app and root workflow without duplicating the implementation.
"""

from expense_agent.workflow import app
from expense_agent.workflow import root_agent

__all__ = ["app", "root_agent"]
