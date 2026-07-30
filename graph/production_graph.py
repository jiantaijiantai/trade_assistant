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


from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents import DataAgent, KnowledgeAgent, ReportAgent, Supervisor, ToolAgent
from core import (
    RequestContext,
    TraceRecorder,
    build_idempotency_key,
    check_cost_budget,
    check_tool_permission,
    new_request_id,
)
from tools import execute_tool, get_tool


class ProductionState(TypedDict, total=False):
    context: dict
    task_type: str
    route_reason: str
    route_confidence: float
    current_cost_units: int
    agent_output: dict
    trace: dict
    final_answer: str
    error: str
    tool_name: str
    business_id: str


def create_context(
    user_input: str,
    tenant_id: str = "tenant_demo",
    user_id: str = "user_demo",
    roles: list[str] | None = None,
    max_cost_units: int = 10,
) -> RequestContext:
    return RequestContext(
        request_id=new_request_id(),
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles or ["operator"],
        user_input=user_input,
        max_cost_units=max_cost_units,
    )


def supervisor_node(state: ProductionState) -> ProductionState:
    context = RequestContext(**state["context"])
    trace = TraceRecorder(context)

    decision = Supervisor().route(context.user_input)

    trace.record(
        "route_decision",
        "Supervisor 完成路由",
        task_type=decision.task_type,
        reason=decision.reason,
    )

    return {
        **state,
        "task_type": decision.task_type,
        "route_reason": decision.reason,
        "route_confidence": 0.8,
        "current_cost_units": 0,
        "trace": trace.to_dict(),
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

    execution = execute_tool(
        context=context,
        tool=tool,
        user_input=context.user_input,
        idempotency_key=idempotency_key,
        business_id=business_id,
    )

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
        f"tenant_id：{state['context']['tenant_id']}",
        f"user_id：{state['context']['user_id']}",
        f"路由结果：{state['task_type']}",
        f"路由原因：{state['route_reason']}",
        f"执行 Agent：{output['agent_name']}",
        f"成本消耗：{state['current_cost_units']}/{state['context']['max_cost_units']}",
        "",
        "回答：",
        output["answer"],
    ]

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
            "- 已执行角色权限检查",
            "- 已执行成本预算检查",
            "- 已生成幂等 key，避免重复请求反复生成文件",
        ]
    )

    return {**state, "final_answer": "\n".join(lines)}


def route_by_task_type(state: ProductionState) -> str:
    if state.get("error"):
        return "final"
    return state["task_type"]


def _run_agent(state: ProductionState, agent) -> ProductionState:
    context = RequestContext(**state["context"])
    output = agent.run(context.user_input)

    cost_check = check_cost_budget(
        context=context,
        current_cost_units=state.get("current_cost_units", 0),
        next_cost_units=getattr(output, "cost_units", 1),
    )

    if not cost_check.allowed:
        return {**state, "error": cost_check.reason}

    return {
        **state,
        "current_cost_units": state.get("current_cost_units", 0) + getattr(output, "cost_units", 1),
        "agent_output": output.model_dump(),
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
            "knowledge": "knowledge",
            "data": "data",
            "tool": "tool",
            "report": "report",
            "final": "final",
        },
    )

    graph.add_edge("knowledge", "final")
    graph.add_edge("data", "final")
    graph.add_edge("tool", "final")
    graph.add_edge("report", "final")
    graph.add_edge("final", END)

    return graph.compile()


def run_production_multi_agent(
    user_input: str,
    tenant_id: str = "tenant_demo",
    user_id: str = "user_demo",
    roles: list[str] | None = None,
    max_cost_units: int = 10,
    tool_name: str | None = None,
    business_id: str | None = None,
) -> ProductionState:
    context = create_context(
        user_input=user_input,
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        max_cost_units=max_cost_units,
    )

    app = build_production_graph()
    initial_state: ProductionState = {"context": context.model_dump()}

    if tool_name:
        initial_state["tool_name"] = tool_name
    if business_id:
        initial_state["business_id"] = business_id

    return app.invoke(initial_state)
