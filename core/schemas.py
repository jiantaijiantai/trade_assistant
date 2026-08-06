\
\
\
\
\
\
\
\
\
\
\
\


from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    KNOWLEDGE = "knowledge"
    DATA = "data"
    TOOL = "tool"
    REPORT = "report"


class RiskLevel(str, Enum):
    READONLY = "readonly"
    LOW_RISK_WRITE = "low_risk_write"
    HIGH_RISK_WRITE = "high_risk_write"


class RequestContext(BaseModel):
    request_id: str
    tenant_id: str
    user_id: str
    roles: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=lambda: ["business"])
    groups: list[str] = Field(default_factory=list)
    clearance_level: str = "internal"
    user_input: str
    max_cost_units: int = 10
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_tool_calls: int | None = None
    max_duration_ms: int | None = None
    max_estimated_cost: float | None = None


class RouteDecision(BaseModel):
    task_type: TaskType
    confidence: float = Field(ge=0, le=1)
    reason: str


class AgentOutput(BaseModel):
    agent_name: str
    task_type: TaskType
    answer: str
    evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    cost_units: int = 1


class ToolSpec(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel
    required_roles: list[str] = Field(default_factory=list)
    idempotent: bool = True


class ToolCallPlan(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class AuditEvent(BaseModel):
    request_id: str
    event_type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str
