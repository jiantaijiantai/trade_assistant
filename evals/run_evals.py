from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = PROJECT_ROOT / "evals" / "datasets"
RESULTS_ROOT = PROJECT_ROOT / "evals" / "results"

sys.path.insert(0, str(PROJECT_ROOT))

from agents import Supervisor
from core import build_idempotency_key
from core.schemas import RequestContext
from graph.production_graph import run_production_multi_agent
from rag.access_control import can_access_metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-version", default="v0.1")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    dataset_dir = DATASET_ROOT / args.dataset_version
    result = {
        "dataset_version": args.dataset_version,
        "runner_version": "v0.1",
        "code_version": _git_commit(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "suites": {},
    }

    result["suites"]["routing"] = run_routing_eval(dataset_dir / "routing_cases.json")
    result["suites"]["acl"] = run_acl_eval(dataset_dir / "acl_cases.json")
    result["suites"]["security"] = run_security_eval(dataset_dir / "security_cases.json")
    result["suites"]["tooling"] = run_tooling_eval(dataset_dir / "tooling_cases.json")
    result["summary"] = summarize(result["suites"])

    output_path = Path(args.output) if args.output else RESULTS_ROOT / f"{args.dataset_version}_{result['code_version']}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output_path}")
    return 0 if result["summary"]["failed"] == 0 else 1


def run_routing_eval(path: Path) -> dict[str, Any]:
    cases = _load_cases(path)
    results = []
    for case in cases:
        decision = Supervisor().route(case["input"])
        actual = decision.model_dump()
        checks = [
            actual["task_type"] == case["expected_task_type"],
            actual["needs_clarification"] == case["needs_clarification"],
        ]
        if "expected_source" in case:
            checks.append(actual["source"] == case["expected_source"])
        if "min_confidence" in case:
            checks.append(actual["confidence"] >= case["min_confidence"])
        if "max_confidence" in case:
            checks.append(actual["confidence"] <= case["max_confidence"])
        checks.extend(_contains_all(actual.get("missing_fields", []), case.get("expected_missing_fields", [])))
        checks.extend(_contains_all(actual.get("risk_flags", []), case.get("expected_risk_flags", [])))
        results.append(_case_result(case["id"], all(checks), actual))
    return _suite_result(results)


def run_acl_eval(path: Path) -> dict[str, Any]:
    cases = _load_cases(path)
    results = []
    for case in cases:
        context = RequestContext(**case["context"])
        allowed = can_access_metadata(context, case["metadata"])
        results.append(
            _case_result(
                case["id"],
                allowed == case["expected_allowed"],
                {"allowed": allowed, "expected_allowed": case["expected_allowed"]},
            )
        )
    return _suite_result(results)


def run_security_eval(path: Path) -> dict[str, Any]:
    cases = _load_cases(path)
    results = []
    for case in cases:
        state = run_production_multi_agent(case["input"], max_tool_calls=0)
        actual = {
            "needs_clarification": state.get("needs_clarification"),
            "route_confidence": state.get("route_confidence"),
            "route_risk_flags": state.get("route_risk_flags", []),
            "tool_execution": (state.get("agent_output") or {}).get("tool_execution"),
            "error": state.get("error"),
        }
        checks = [
            bool(actual["needs_clarification"]) == case["expected_needs_clarification"],
            actual["route_confidence"] <= case["max_confidence"],
            actual["tool_execution"] is None,
        ]
        checks.extend(_contains_all(actual["route_risk_flags"], case.get("expected_risk_flags", [])))
        results.append(_case_result(case["id"], all(checks), actual))
    return _suite_result(results)


def run_tooling_eval(path: Path) -> dict[str, Any]:
    cases = _load_cases(path)
    results = []
    for case in cases:
        if case["id"] == "write_tools_disabled_by_default":
            with _temporary_env("ALLOW_WRITE_TOOLS", "false"):
                state = run_production_multi_agent(case["input"])
            actual = {
                "error": state.get("error"),
                "tool_execution": (state.get("agent_output") or {}).get("tool_execution"),
                "usage": state.get("usage", {}).get("summary", {}),
            }
            passed = (
                case["expected_error_contains"] in str(actual["error"])
                and actual["tool_execution"] == case["expected_tool_execution"]
            )
            results.append(_case_result(case["id"], passed, actual))
        elif case["id"] == "tool_budget_blocks_execution_when_writes_enabled":
            env_value = "true" if case.get("allow_write_tools") else "false"
            with _temporary_env("ALLOW_WRITE_TOOLS", env_value):
                state = run_production_multi_agent(case["input"], max_tool_calls=case["max_tool_calls"])
            actual = {
                "error": state.get("error"),
                "tool_execution": (state.get("agent_output") or {}).get("tool_execution"),
                "usage": state.get("usage", {}).get("summary", {}),
            }
            passed = (
                case["expected_error_contains"] in str(actual["error"])
                and actual["tool_execution"] == case["expected_tool_execution"]
                and actual["usage"].get("tool_calls", 0) == 0
            )
            results.append(_case_result(case["id"], passed, actual))
        elif case["id"] == "idempotency_key_stable":
            context = RequestContext(
                request_id="req_eval_tooling",
                tenant_id=case["tenant_id"],
                user_id=case["user_id"],
                roles=["operator"],
                department_ids=["business"],
                groups=[],
                clearance_level="internal",
                user_input="生成清单",
                max_cost_units=10,
            )
            first = build_idempotency_key(context, case["action_type"], case["business_id"])
            second = build_idempotency_key(context, case["action_type"], case["business_id"])
            actual = {"first": first, "second": second}
            results.append(_case_result(case["id"], (first == second) == case["expected_same_key"], actual))
        else:
            results.append(_case_result(case["id"], False, {"error": "unknown tooling case"}))
    return _suite_result(results)


def summarize(suites: dict[str, dict[str, Any]]) -> dict[str, int]:
    total = sum(suite["total"] for suite in suites.values())
    failed = sum(suite["failed"] for suite in suites.values())
    return {"total": total, "passed": total - failed, "failed": failed}


def _suite_result(results: list[dict[str, Any]]) -> dict[str, Any]:
    failed = sum(1 for item in results if not item["passed"])
    return {"total": len(results), "passed": len(results) - failed, "failed": failed, "cases": results}


def _case_result(case_id: str, passed: bool, actual: dict[str, Any]) -> dict[str, Any]:
    return {"id": case_id, "passed": passed, "actual": actual}


def _contains_all(actual: list[str], expected: list[str]) -> list[bool]:
    return [item in actual for item in expected]


def _load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


class _temporary_env:
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value
        self.previous = None

    def __enter__(self):
        self.previous = os.environ.get(self.name)
        os.environ[self.name] = self.value

    def __exit__(self, exc_type, exc, tb):
        if self.previous is None:
            os.environ.pop(self.name, None)
        else:
            os.environ[self.name] = self.previous


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
