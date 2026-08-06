from __future__ import annotations

import os
from enum import Enum
from typing import Any

from core.schemas import RiskLevel, ToolSpec


class CapabilityStage(str, Enum):
    READONLY = "readonly"
    LOCAL_DRAFT = "local_draft"
    CONTROLLED_WRITE = "controlled_write"
    APPROVAL_WRITE = "approval_write"
    CORE_SYSTEM_WRITE = "core_system_write"


def allow_write_tools() -> bool:
    return _env_bool("ALLOW_WRITE_TOOLS", default=False)


def allow_high_risk_tools() -> bool:
    return _env_bool("ALLOW_HIGH_RISK_TOOLS", default=False)


def current_capability_policy() -> dict[str, Any]:
    return {
        "stage": os.getenv("BUSINESS_CAPABILITY_STAGE", CapabilityStage.READONLY.value),
        "allow_write_tools": allow_write_tools(),
        "allow_high_risk_tools": allow_high_risk_tools(),
        "write_boundary": "readonly_first",
    }


def is_tool_enabled(tool: ToolSpec) -> tuple[bool, str]:
    if tool.risk_level == RiskLevel.READONLY:
        return True, "readonly tool allowed"

    if tool.risk_level == RiskLevel.LOW_RISK_WRITE:
        if allow_write_tools():
            return True, "low risk write tool allowed by configuration"
        return False, "low risk write tools are disabled; enable ALLOW_WRITE_TOOLS=true after approval controls are ready"

    if tool.risk_level == RiskLevel.HIGH_RISK_WRITE:
        if allow_high_risk_tools():
            return True, "high risk write tool allowed by configuration"
        return False, "high risk write tools are disabled"

    return False, f"unsupported tool risk level: {tool.risk_level}"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
