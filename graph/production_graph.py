from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents import DataAgent, KnowledgeAgent, ReportAgent, Supervisor, ToolAgent
from core import (
    RequestContext,
    TaskStatus,
    TraceRecorder,
    build_idempotency_key,
    check_cost_budget,
    check_tool_permission,
    check_usage_budget,
    create_task_record,
    elapsed_ms,
    load_task_record,
    new_task_id,
    new_request_id,
    new_usage_ledger,
    record_agent_usage,
    record_tool_usage,
    save_replay_record,
    save_task_checkpoint,
    start_timer,
)
from tools import execute_tool, get_tool


CLARIFICATION_CONFIDENCE_THRESHOLD = 0.6


class ProductionState(TypedDict, total=False):
    context: dict
    task_type: str
    route_reason: str
    route_confidence: float
    route_source: str
    route_missing_fields: list[str]
    route_risk_flags: list[str]
    needs_clarification: bool
    current_cost_units: int
    usage: dict
    agent_output: dict
    trace: dict
    final_answer: str
    error: str
    tool_name: str
    business_id: str
    task_id: str
    task_status: str
    require_approval: bool
    approval_status: str
    approval_reason: str
    approved_by: str


def create_context(
    user_input: str,
    tenant_id: str = "company_internal",
    user_id: str = "user_demo",
    roles: list[str] | None = None,
    department_ids: list[str] | None = None,
    groups: list[str] | None = None,
    clearance_level: str = "internal",
    max_cost_units: int = 10,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    max_total_tokens: int | None = None,
    max_tool_calls: int | None = None,
    max_duration_ms: int | None = None,
    max_estimated_cost: float | None = None,
) -> RequestContext:
    return RequestContext(
        request_id=new_request_id(),
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles or ["operator"],
        department_ids=department_ids or ["business"],
        groups=groups or [],
        clearance_level=clearance_level,
        user_input=user_input,
        max_cost_units=max_cost_units,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_total_tokens=max_total_tokens,
        max_tool_calls=max_tool_calls,
        max_duration_ms=max_duration_ms,
        max_estimated_cost=max_estimated_cost,
    )


def supervisor_node(state: ProductionState) -> ProductionState:
    context = RequestContext(**state["context"])
    trace = TraceRecorder(context)

    decision = Supervisor().route(context.user_input)
    needs_clarification = (
        decision.needs_clarification
        or decision.confidence < CLARIFICATION_CONFIDENCE_THRESHOLD
        or bool(decision.risk_flags)
    )

    trace.record(
        "route_decision",
        "Supervisor completed routing",
        task_type=decision.task_type,
        confidence=decision.confidence,
        reason=decision.reason,
        source=decision.source,
        missing_fields=decision.missing_fields,
        risk_flags=decision.risk_flags,
        needs_clarification=needs_clarification,
    )

    return {
        **state,
        "task_type": decision.task_type,
        "route_reason": decision.reason,
        "route_confidence": decision.confidence,
        "route_source": decision.source,
        "route_missing_fields": decision.missing_fields,
        "route_risk_flags": decision.risk_flags,
        "needs_clarification": needs_clarification,
        "task_status": TaskStatus.ROUTED.value,
        "current_cost_units": 0,
        "usage": state.get("usage") or new_usage_ledger(),
        "trace": trace.to_dict(),
    }


def approval_node(state: ProductionState) -> ProductionState:
    approval_status = state.get("approval_status", "pending")
    if approval_status == "approved":
        return {**state, "task_status": TaskStatus.RUNNING.value}

    return {
        **state,
        "task_status": TaskStatus.WAITING_APPROVAL.value,
        "agent_output": {
            "agent_name": "ApprovalNode",
            "task_type": "approval",
            "answer": "任务已暂停，等待人工审批后继续执行。",
            "evidence": [
                f"task_id={state.get('task_id')}",
                f"task_type={state.get('task_type')}",
                f"route_confidence={state.get('route_confidence')}",
            ],
            "sources": [],
            "next_steps": [
                "调用审批接口通过任务",
                "审批通过后调用恢复接口继续执行",
            ],
        },
    }


def clarification_node(state: ProductionState) -> ProductionState:
    missing_fields = state.get("route_missing_fields", [])
    risk_flags = state.get("route_risk_flags", [])

    questions = []
    if "task_intent" in missing_fields or "route_intent" in missing_fields:
        questions.append("你希望我做知识问答、数据分析、生成业务文件，还是形成报告？")
    if "business_object" in missing_fields:
        questions.append("请补充具体合同、客户、结算单、货转或发票对象。")
    if "possible_high_risk_write" in risk_flags:
        questions.append("这个请求可能涉及高风险写操作，请确认是否只需要生成草稿或只读查询。")
    if not questions:
        questions.append("请补充任务目标和业务对象，我再继续路由执行。")

    answer = "当前路由置信度不足，暂不执行 Agent 或工具。\n" + "\n".join(
        f"- {question}" for question in questions
    )

    return {
        **state,
        "task_status": TaskStatus.WAITING_APPROVAL.value,
        "agent_output": {
            "agent_name": "ClarificationNode",
            "task_type": "clarify",
            "answer": answer,
            "evidence": [
                f"route_confidence={state.get('route_confidence')}",
                f"route_source={state.get('route_source')}",
            ],
            "sources": [],
            "next_steps": ["用户补充信息后重新提交请求"],
        },
    }


def knowledge_node(state: ProductionState) -> ProductionState:
    return _run_agent(state, KnowledgeAgent())


def data_node(state: ProductionState) -> ProductionState:
    return _run_agent(state, DataAgent())


def report_node(state: ProductionState) -> ProductionState:
    return _run_agent(state, ReportAgent())


def tool_node(state: ProductionState) -> ProductionState:
    context = RequestContext(**state["context"])
    tool_name = state.get("tool_name") or _select_tool_name(context.user_input)
    business_id = state.get("business_id") or context.request_id

    tool = get_tool(tool_name)
    if tool is None:
        return {**state, "error": f"工具不存在：{tool_name}"}

    permission = check_tool_permission(context, tool)
    if not permission.allowed:
        return {**state, "error": permission.reason}

    idempotency_key = build_idempotency_key(
        context=context,
        action_type=tool.name,
        business_id=business_id,
    )

    output_state = _run_agent(state, ToolAgent())
    if output_state.get("error"):
        return output_state

    current_tool_calls = output_state.get("usage", {}).get("summary", {}).get("tool_calls", 0)
    if context.max_tool_calls is not None and current_tool_calls + 1 > context.max_tool_calls:
        return {
            **output_state,
            "error": f"真实资源预算不足：tool_calls {current_tool_calls + 1}/{context.max_tool_calls}",
        }

    tool_started_at = start_timer()
    execution = execute_tool(
        context=context,
        tool=tool,
        user_input=context.user_input,
        idempotency_key=idempotency_key,
        business_id=business_id,
    )
    output_state["usage"] = record_tool_usage(
        output_state.get("usage"),
        tool_name=tool.name,
        duration_ms=elapsed_ms(tool_started_at),
        executed=bool(execution.get("executed", False)),
    )
    usage_check = check_usage_budget(context, output_state["usage"])
    if not usage_check.allowed:
        return {**output_state, "error": usage_check.reason}

    output_state["tool_name"] = tool.name
    output_state["business_id"] = business_id
    output_state["agent_output"]["tool_plan"] = {
        "tool_name": tool.name,
        "description": tool.description,
        "idempotency_key": idempotency_key,
        "business_id": business_id,
        "executed": execution.get("executed", False),
        "mode": execution.get("mode"),
        "output_path": execution.get("path"),
        "message": execution.get("message"),
        "boundary": "仅生成本地业务辅助文件，用于业务员整理、核对和交接日常文字材料。",
    }
    output_state["agent_output"]["tool_execution"] = execution

    return output_state


def final_node(state: ProductionState) -> ProductionState:
    if state.get("error"):
        return {**state, "final_answer": f"请求失败：{state['error']}"}

    output = state["agent_output"]
    tool_plan = output.get("tool_plan")

    lines = [
        f"request_id：{state['context']['request_id']}",
        f"task_id：{state.get('task_id') or '无'}",
        f"任务状态：{state.get('task_status') or '无'}",
        f"tenant_id：{state['context']['tenant_id']}",
        f"user_id：{state['context']['user_id']}",
        f"路由结果：{state['task_type']}",
        f"路由来源：{state.get('route_source')}",
        f"路由置信度：{state.get('route_confidence')}",
        f"路由原因：{state['route_reason']}",
        f"执行节点：{output['agent_name']}",
        f"成本消耗：{state.get('current_cost_units', 0)}/{state['context']['max_cost_units']}",
        "",
        "回答：",
        output["answer"],
    ]

    usage_summary = state.get("usage", {}).get("summary", {})
    if usage_summary:
        lines.extend(
            [
                "",
                "真实资源消耗：",
                f"- input_tokens：{usage_summary.get('input_tokens', 0)}",
                f"- output_tokens：{usage_summary.get('output_tokens', 0)}",
                f"- total_tokens：{usage_summary.get('total_tokens', 0)}",
                f"- estimated_cost：{usage_summary.get('estimated_cost', 0.0)}",
                f"- tool_calls：{usage_summary.get('tool_calls', 0)}",
                f"- agent_calls：{usage_summary.get('agent_calls', 0)}",
                f"- duration_ms：{usage_summary.get('duration_ms', 0)}",
            ]
        )

    if state.get("route_missing_fields"):
        lines.extend(["", f"待澄清字段：{', '.join(state['route_missing_fields'])}"])
    if state.get("route_risk_flags"):
        lines.extend(["", f"风险标记：{', '.join(state['route_risk_flags'])}"])

    if tool_plan:
        lines.extend(
            [
                "",
                "工具执行结果：",
                f"- 工具名称：{tool_plan['tool_name']}",
                f"- 工具说明：{tool_plan['description']}",
                f"- 幂等 key：{tool_plan['idempotency_key']}",
                f"- 是否生成文件：{tool_plan['executed']}",
                f"- 输出路径：{tool_plan.get('output_path') or '无'}",
                f"- 说明：{tool_plan['message']}",
                f"- 边界：{tool_plan['boundary']}",
            ]
        )

    lines.extend(
        [
            "",
            "生产控制点：",
            "- 已携带 request_id，便于追踪",
            "- 已携带 tenant_id / user_id，便于内部隔离",
            "- 已记录真实路由置信度，不再使用固定 0.8",
            "- 低置信度或高风险信号会进入澄清节点",
            "- 工具执行前仍执行角色权限和成本预算检查",
            "- 已记录 token、估算金额、工具调用次数和节点耗时",
            "- 工具执行使用幂等 key，避免重复请求反复生成文件",
        ]
    )

    return {**state, "final_answer": "\n".join(lines)}


def route_by_task_type(state: ProductionState) -> str:
    if state.get("error"):
        return "final"
    if state.get("needs_clarification"):
        return "clarify"
    if _requires_approval(state):
        return "approval"
    return state["task_type"]


def route_after_approval(state: ProductionState) -> str:
    if state.get("approval_status") == "approved":
        return state["task_type"]
    return "final"


def _requires_approval(state: ProductionState) -> bool:
    if not state.get("require_approval"):
        return False
    if state.get("approval_status") == "approved":
        return False
    return state.get("task_type") in {"tool", "report"}


def _run_agent(state: ProductionState, agent: Any) -> ProductionState:
    context = RequestContext(**state["context"])
    started_at = start_timer()
    output = agent.run(context)
    duration_ms = elapsed_ms(started_at)

    cost_check = check_cost_budget(
        context=context,
        current_cost_units=state.get("current_cost_units", 0),
        next_cost_units=getattr(output, "cost_units", 1),
    )

    if not cost_check.allowed:
        return {**state, "error": cost_check.reason}

    usage = record_agent_usage(
        state.get("usage"),
        node_name=getattr(agent, "name", agent.__class__.__name__),
        input_text=context.user_input,
        output_text=output.answer,
        duration_ms=duration_ms,
        cost_units=getattr(output, "cost_units", 1),
    )
    usage_check = check_usage_budget(context, usage)
    if not usage_check.allowed:
        return {**state, "usage": usage, "error": usage_check.reason}

    return {
        **state,
        "task_status": TaskStatus.RUNNING.value,
        "current_cost_units": state.get("current_cost_units", 0) + getattr(output, "cost_units", 1),
        "agent_output": output.model_dump(),
        "usage": usage,
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


def build_production_graph():
    graph = StateGraph(ProductionState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("approval", approval_node)
    graph.add_node("clarify", clarification_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("data", data_node)
    graph.add_node("tool", tool_node)
    graph.add_node("report", report_node)
    graph.add_node("final", final_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_by_task_type,
        {
            "clarify": "clarify",
            "approval": "approval",
            "knowledge": "knowledge",
            "data": "data",
            "tool": "tool",
            "report": "report",
            "final": "final",
        },
    )

    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "knowledge": "knowledge",
            "data": "data",
            "tool": "tool",
            "report": "report",
            "final": "final",
        },
    )

    graph.add_edge("clarify", "final")
    graph.add_edge("knowledge", "final")
    graph.add_edge("data", "final")
    graph.add_edge("tool", "final")
    graph.add_edge("report", "final")
    graph.add_edge("final", END)

    return graph.compile()


def run_production_multi_agent(
    user_input: str,
    tenant_id: str = "company_internal",
    user_id: str = "user_demo",
    roles: list[str] | None = None,
    department_ids: list[str] | None = None,
    groups: list[str] | None = None,
    clearance_level: str = "internal",
    max_cost_units: int = 10,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    max_total_tokens: int | None = None,
    max_tool_calls: int | None = None,
    max_duration_ms: int | None = None,
    max_estimated_cost: float | None = None,
    tool_name: str | None = None,
    business_id: str | None = None,
    task_id: str | None = None,
    require_approval: bool = False,
    approval_status: str = "pending",
    approval_reason: str = "",
    approved_by: str = "",
) -> ProductionState:
    context = create_context(
        user_input=user_input,
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        department_ids=department_ids,
        groups=groups,
        clearance_level=clearance_level,
        max_cost_units=max_cost_units,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_total_tokens=max_total_tokens,
        max_tool_calls=max_tool_calls,
        max_duration_ms=max_duration_ms,
        max_estimated_cost=max_estimated_cost,
    )

    app = build_production_graph()
    initial_state: ProductionState = {"context": context.model_dump()}
    initial_state["task_id"] = task_id or new_task_id(context.request_id)
    initial_state["task_status"] = TaskStatus.CREATED.value
    initial_state["require_approval"] = require_approval
    initial_state["approval_status"] = approval_status
    initial_state["approval_reason"] = approval_reason
    initial_state["approved_by"] = approved_by
    initial_state["usage"] = new_usage_ledger()

    if tool_name:
        initial_state["tool_name"] = tool_name
    if business_id:
        initial_state["business_id"] = business_id

    return app.invoke(initial_state)


def create_persisted_task(
    user_input: str,
    tenant_id: str = "company_internal",
    user_id: str = "user_demo",
    roles: list[str] | None = None,
    department_ids: list[str] | None = None,
    groups: list[str] | None = None,
    clearance_level: str = "internal",
    max_cost_units: int = 10,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    max_total_tokens: int | None = None,
    max_tool_calls: int | None = None,
    max_duration_ms: int | None = None,
    max_estimated_cost: float | None = None,
    tool_name: str | None = None,
    business_id: str | None = None,
    require_approval: bool = True,
) -> dict[str, Any]:
    context = create_context(
        user_input=user_input,
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        department_ids=department_ids,
        groups=groups,
        clearance_level=clearance_level,
        max_cost_units=max_cost_units,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_total_tokens=max_total_tokens,
        max_tool_calls=max_tool_calls,
        max_duration_ms=max_duration_ms,
        max_estimated_cost=max_estimated_cost,
    )
    task_id = new_task_id(context.request_id)
    initial_state: ProductionState = {
        "context": context.model_dump(),
        "task_id": task_id,
        "task_status": TaskStatus.CREATED.value,
        "require_approval": require_approval,
        "approval_status": "pending",
        "approval_reason": "",
        "approved_by": "",
        "usage": new_usage_ledger(),
    }
    if tool_name:
        initial_state["tool_name"] = tool_name
    if business_id:
        initial_state["business_id"] = business_id

    create_task_record(
        task_id=task_id,
        initial_state=initial_state,
        require_approval=require_approval,
    )
    state = build_production_graph().invoke(initial_state)
    status = _status_from_state(state)
    save_task_checkpoint(task_id=task_id, status=status, state=state)
    return load_task_record(task_id)


def approve_persisted_task(task_id: str, approved_by: str, reason: str = "") -> dict[str, Any]:
    record = load_task_record(task_id)
    state = record["latest_state"]
    approval = {
        "status": "approved",
        "approved_by": approved_by,
        "reason": reason,
    }
    state["approval_status"] = "approved"
    state["approved_by"] = approved_by
    state["approval_reason"] = reason
    save_task_checkpoint(
        task_id=task_id,
        status=TaskStatus.RUNNING,
        state=state,
        approval=approval,
    )
    return load_task_record(task_id)


def resume_persisted_task(task_id: str) -> dict[str, Any]:
    record = load_task_record(task_id)
    state = record["latest_state"]
    if state.get("approval_status") != "approved" and state.get("task_status") == TaskStatus.WAITING_APPROVAL.value:
        return record

    resumed_state = build_production_graph().invoke(state)
    status = _status_from_state(resumed_state)
    save_task_checkpoint(task_id=task_id, status=status, state=resumed_state)
    return load_task_record(task_id)


def replay_persisted_task(task_id: str) -> dict[str, Any]:
    record = load_task_record(task_id)
    initial_state = record["initial_state"]
    source_context = initial_state["context"]
    replay_context = {
        **source_context,
        "request_id": new_request_id(),
    }
    replay_task_id = new_task_id(replay_context["request_id"])
    replay_initial_state = {
        **initial_state,
        "context": replay_context,
        "task_id": replay_task_id,
        "task_status": TaskStatus.CREATED.value,
        "approval_status": "pending",
        "approval_reason": "",
        "approved_by": "",
        "usage": new_usage_ledger(),
    }
    save_replay_record(
        source_task_id=task_id,
        replay_task_id=replay_task_id,
        initial_state=replay_initial_state,
        require_approval=bool(record.get("require_approval", True)),
    )
    replay_state = build_production_graph().invoke(replay_initial_state)
    status = _status_from_state(replay_state)
    save_task_checkpoint(task_id=replay_task_id, status=status, state=replay_state)
    return load_task_record(replay_task_id)


def _status_from_state(state: ProductionState) -> TaskStatus:
    if state.get("error"):
        return TaskStatus.FAILED
    if state.get("task_status") == TaskStatus.WAITING_APPROVAL.value:
        return TaskStatus.WAITING_APPROVAL
    return TaskStatus.SUCCEEDED
