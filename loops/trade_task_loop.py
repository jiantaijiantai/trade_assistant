\
\
\
\
\
\
\
\
\


from __future__ import annotations

from typing import Any

from graph.production_graph import run_production_multi_agent
from rag.access_control import BUSINESS_DEPARTMENT_ID, DEFAULT_TENANT_ID
from loops.llm_loop import llm_critique, llm_finalize, llm_plan
from loops.schemas import LoopStep, TradeTaskLoopResult


def run_trade_task_loop(
    goal: str,
    user_input: str,
    tenant_id: str = DEFAULT_TENANT_ID,
    user_id: str = "user_demo",
    roles: list[str] | None = None,
    department_ids: list[str] | None = None,
    groups: list[str] | None = None,
    clearance_level: str = "internal",
    max_cost_units: int = 10,
) -> TradeTaskLoopResult:


    steps: list[LoopStep] = []

    plan = llm_plan(
        goal=goal,
        available_actions=[
            "run_production_multi_agent",
            "rerun_agent_with_explicit_tool",
            "ask_for_more_business_docs",
        ],
        context={
            "user_input": user_input,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "roles": roles or ["operator", "analyst"],
            "department_ids": department_ids or [BUSINESS_DEPARTMENT_ID],
            "groups": groups or [],
            "clearance_level": clearance_level,
            "max_cost_units": max_cost_units,
        },
    )
    steps.append(
        LoopStep(
            name="llm_planner",
            status="planned",
            detail=plan.task_understanding,
            data=plan.model_dump(),
        )
    )

    execution = _execute_trade_agent(
        user_input=user_input,
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        department_ids=department_ids,
        groups=groups,
        clearance_level=clearance_level,
        max_cost_units=max_cost_units,
    )
    steps.append(
        LoopStep(
            name="executor",
            status="executed",
            detail="已按 Planner 目标调用 LangGraph 多 Agent 业务流程。",
            data=_response_summary(execution),
        )
    )

    critique = llm_critique(goal=goal, plan=plan, execution_result=execution)
    steps.append(
        LoopStep(
            name="llm_critic",
            status="critiqued",
            detail=critique.rationale,
            data=critique.model_dump(),
        )
    )

    revision_result: dict[str, Any] = {}
    if not critique.passed:
        revision_result = _revise_trade_result(
            actions=critique.revision_actions,
            user_input=user_input,
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles,
            department_ids=department_ids,
            groups=groups,
            clearance_level=clearance_level,
            max_cost_units=max_cost_units,
        )
        if revision_result:
            execution = revision_result
        steps.append(
            LoopStep(
                name="reviser",
                status="revised",
                detail="已根据 LLM Critic 的修正动作重新执行或补充业务流程。",
                data={"revision_actions": critique.revision_actions, "revision_result": _response_summary(revision_result)},
            )
        )
        critique = llm_critique(goal=goal, plan=plan, execution_result=execution)
        steps.append(
            LoopStep(
                name="llm_critic_after_revise",
                status="critiqued",
                detail=critique.rationale,
                data=critique.model_dump(),
            )
        )
    else:
        steps.append(
            LoopStep(
                name="reviser",
                status="revised",
                detail="LLM Critic 判断已达标，Reviser 不再额外调用业务函数。",
                data={"revision_actions": ["no_revision_needed"]},
            )
        )

    finalizer = llm_finalize(
        goal=goal,
        plan=plan,
        execution_result=execution,
        critique=critique,
        revision_result=revision_result,
    )
    steps.append(
        LoopStep(
            name="llm_finalizer",
            status="finalized",
            detail="已由 LLM Finalizer 生成最终内部业务 Agent 报告。",
            data={"user_next_steps": finalizer.user_next_steps},
        )
    )

    return TradeTaskLoopResult(
        goal=goal,
        complete=critique.passed,
        loop_steps=steps,
        plan=plan,
        agent_response=execution,
        critique=critique,
        finalizer=finalizer,
        final_task_report=finalizer.final_report,
    )


def _execute_trade_agent(
    user_input: str,
    tenant_id: str,
    user_id: str,
    roles: list[str] | None,
    department_ids: list[str] | None,
    groups: list[str] | None,
    clearance_level: str,
    max_cost_units: int,
    tool_name: str | None = None,
) -> dict[str, Any]:


    state = run_production_multi_agent(
        user_input=user_input,
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        department_ids=department_ids,
        groups=groups,
        clearance_level=clearance_level,
        max_cost_units=max_cost_units,
        tool_name=tool_name,
    )
    return _state_to_response_dict(state)


def _revise_trade_result(
    actions: list[str],
    user_input: str,
    tenant_id: str,
    user_id: str,
    roles: list[str] | None,
    department_ids: list[str] | None,
    groups: list[str] | None,
    clearance_level: str,
    max_cost_units: int,
) -> dict[str, Any]:


    if "rerun_agent_with_explicit_tool" in actions:
        return _execute_trade_agent(
            user_input=user_input,
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles,
            department_ids=department_ids,
            groups=groups,
            clearance_level=clearance_level,
            max_cost_units=max_cost_units,
            tool_name=_select_tool_name(user_input),
        )

    return {}


def _state_to_response_dict(state: dict[str, Any]) -> dict[str, Any]:


    context = state.get("context", {})
    agent_output = state.get("agent_output", {})
    return {
        "request_id": context.get("request_id", ""),
        "tenant_id": context.get("tenant_id", ""),
        "user_id": context.get("user_id", ""),
        "task_type": state.get("task_type"),
        "route_reason": state.get("route_reason"),
        "route_confidence": state.get("route_confidence"),
        "current_cost_units": state.get("current_cost_units"),
        "final_answer": state.get("final_answer", ""),
        "evidence": agent_output.get("evidence", []),
        "sources": agent_output.get("sources", []),
        "next_steps": agent_output.get("next_steps", []),
        "tool_plan": agent_output.get("tool_plan"),
        "tool_execution": agent_output.get("tool_execution"),
        "error": state.get("error"),
    }


def _select_tool_name(user_input: str) -> str:


    text = user_input.strip()
    if "待办" in text or "跟进" in text:
        return "create_followup_task"
    if "检查" in text or "清单" in text or "核对" in text or "准入" in text:
        return "generate_business_checklist"
    if "报告" in text or "总结" in text or "说明" in text or "复盘" in text:
        return "draft_business_report"
    return "draft_business_document"


def _response_summary(response: dict[str, Any]) -> dict[str, Any]:


    tool_plan = response.get("tool_plan") or {}
    return {
        "task_type": response.get("task_type"),
        "route_reason": response.get("route_reason"),
        "current_cost_units": response.get("current_cost_units"),
        "has_sources": bool(response.get("sources")),
        "has_tool_plan": bool(tool_plan),
        "tool_name": tool_plan.get("tool_name"),
        "output_path": tool_plan.get("output_path"),
        "error": response.get("error"),
    }
