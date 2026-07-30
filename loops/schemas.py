\
\
\
\


from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LoopStepStatus = Literal["planned", "executed", "critiqued", "revised", "finalized", "failed"]


class LoopStep(BaseModel):


    name: str
    status: LoopStepStatus
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)


class LoopPlan(BaseModel):


    task_understanding: str
    execution_steps: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class LoopCritique(BaseModel):


    passed: bool
    issues: list[str] = Field(default_factory=list)
    revision_actions: list[str] = Field(default_factory=list)
    rationale: str = ""


class LoopFinal(BaseModel):


    final_report: str
    user_next_steps: list[str] = Field(default_factory=list)


class TradeTaskLoopResult(BaseModel):


    goal: str
    complete: bool
    loop_steps: list[LoopStep]
    plan: LoopPlan
    agent_response: dict[str, Any]
    critique: LoopCritique
    finalizer: LoopFinal
    final_task_report: str
