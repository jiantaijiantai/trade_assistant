from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TaskType = Literal["knowledge", "data", "tool", "report"]


class RouteDecision(BaseModel):
    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    source: Literal["rule", "classifier"] = "classifier"
    matched_keyword: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    needs_clarification: bool = False

