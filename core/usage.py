from __future__ import annotations

import math
from copy import deepcopy
from time import perf_counter
from typing import Any

from core.schemas import PolicyDecision, RequestContext


DEFAULT_ESTIMATED_PRICE_PER_1K_TOKENS = 0.002


def new_usage_ledger() -> dict[str, Any]:
    return {
        "summary": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "tool_calls": 0,
            "agent_calls": 0,
            "duration_ms": 0,
        },
        "events": [],
    }


def start_timer() -> float:
    return perf_counter()


def elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def record_agent_usage(
    ledger: dict[str, Any] | None,
    *,
    node_name: str,
    input_text: str,
    output_text: str,
    duration_ms: int,
    cost_units: int,
) -> dict[str, Any]:
    next_ledger = _copy_or_new(ledger)
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    total_tokens = input_tokens + output_tokens
    estimated_cost = estimate_cost(total_tokens)

    event = {
        "event_type": "agent_call",
        "node_name": node_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": estimated_cost,
        "tool_calls": 0,
        "duration_ms": duration_ms,
        "cost_units": cost_units,
    }
    return _append_event(next_ledger, event)


def record_tool_usage(
    ledger: dict[str, Any] | None,
    *,
    tool_name: str,
    duration_ms: int,
    executed: bool,
) -> dict[str, Any]:
    next_ledger = _copy_or_new(ledger)
    event = {
        "event_type": "tool_call",
        "tool_name": tool_name,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
        "tool_calls": 1 if executed else 0,
        "duration_ms": duration_ms,
        "executed": executed,
    }
    return _append_event(next_ledger, event)


def check_usage_budget(context: RequestContext, ledger: dict[str, Any]) -> PolicyDecision:
    summary = ledger.get("summary", {})
    violations = []

    if context.max_input_tokens is not None and summary.get("input_tokens", 0) > context.max_input_tokens:
        violations.append(f"input_tokens {summary.get('input_tokens', 0)}/{context.max_input_tokens}")

    if context.max_output_tokens is not None and summary.get("output_tokens", 0) > context.max_output_tokens:
        violations.append(f"output_tokens {summary.get('output_tokens', 0)}/{context.max_output_tokens}")

    if context.max_total_tokens is not None and summary.get("total_tokens", 0) > context.max_total_tokens:
        violations.append(f"total_tokens {summary.get('total_tokens', 0)}/{context.max_total_tokens}")

    if context.max_tool_calls is not None and summary.get("tool_calls", 0) > context.max_tool_calls:
        violations.append(f"tool_calls {summary.get('tool_calls', 0)}/{context.max_tool_calls}")

    if context.max_duration_ms is not None and summary.get("duration_ms", 0) > context.max_duration_ms:
        violations.append(f"duration_ms {summary.get('duration_ms', 0)}/{context.max_duration_ms}")

    if context.max_estimated_cost is not None and summary.get("estimated_cost", 0.0) > context.max_estimated_cost:
        violations.append(f"estimated_cost {summary.get('estimated_cost', 0.0):.6f}/{context.max_estimated_cost:.6f}")

    if violations:
        return PolicyDecision(allowed=False, reason="真实资源预算不足：" + "; ".join(violations))

    return PolicyDecision(allowed=True, reason="真实资源预算通过")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 2.5))


def estimate_cost(total_tokens: int) -> float:
    return round((total_tokens / 1000) * DEFAULT_ESTIMATED_PRICE_PER_1K_TOKENS, 8)


def _copy_or_new(ledger: dict[str, Any] | None) -> dict[str, Any]:
    return deepcopy(ledger) if ledger else new_usage_ledger()


def _append_event(ledger: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    ledger.setdefault("events", []).append(event)
    summary = ledger.setdefault("summary", {})
    summary["input_tokens"] = summary.get("input_tokens", 0) + event.get("input_tokens", 0)
    summary["output_tokens"] = summary.get("output_tokens", 0) + event.get("output_tokens", 0)
    summary["total_tokens"] = summary.get("total_tokens", 0) + event.get("total_tokens", 0)
    summary["estimated_cost"] = round(summary.get("estimated_cost", 0.0) + event.get("estimated_cost", 0.0), 8)
    summary["tool_calls"] = summary.get("tool_calls", 0) + event.get("tool_calls", 0)
    summary["duration_ms"] = summary.get("duration_ms", 0) + event.get("duration_ms", 0)
    if event.get("event_type") == "agent_call":
        summary["agent_calls"] = summary.get("agent_calls", 0) + 1
    return ledger
