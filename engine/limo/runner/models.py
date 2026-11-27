from typing import Literal

from pydantic import BaseModel

from limo.agents.models import Run


class StepResult(BaseModel):
    run: Run | None
    reason: Literal[
        "started",
        "run_active",
        "no_ready_ticket",
        "shipped",
        "stage_failed",
        "resolving",
        "resolved",
        "needs_human",
    ]


class PollResult(BaseModel):
    merged: list[str]
    changes_requested: list[str]
