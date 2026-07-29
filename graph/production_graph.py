"""
阶段 4：生产落地版 LangGraph 骨架。

这版仍然离线可运行，但开始体现生产系统要素：
- RequestContext：请求、用户、租户、角色、预算；
- TraceRecorder：记录关键事件；
- Policy：权限、成本、幂等；
- Tool Registry：工具风险分级；
- LangGraph：状态流转和条件路由。

真实生产系统中，Agent 内部实现可以继续替换：
KnowledgeAgent -> RAG
DataAgent -> SQL / BI
ToolAgent -> 工作流 / CRM / OA
ReportAgent -> 模板报告 / DOCX / PDF
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents import DataAgent, KnowledgeAgent, ReportAgent, Supervisor, ToolAgent
from core import (
    RequestContext,
    TaskType,
    TraceRecorder,
    build_idempotency_key,
    check_cost_budget,
    check_tool_permission,
    new_request_id,
)
from tools import get_tool


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
        roles=roles or ["operator", "analyst"],
        user_input=user_input,
        max_cost_units=max_cost_units,
    )


def supervisor_node(state: ProductionState) -> ProductionState:
    context = RequestContext(**state["context"])
    trace = TraceRecorder(context)

    supervisor = Supervisor()
    decision = supervisor.route(context.user_input)

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

    tool_name = state.get("tool_name", "create_followup_task")
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
    output_state["agent_output"]["tool_plan"] = {
        "tool_name": tool.name,
        "risk_level": tool.risk_level,
        "idempotency_key": idempotency_key,
        "executed": False,
        "reason": "学习验证环境不执行真实写操作",
    }

    return output_state


def final_node(state: ProductionState) -> ProductionState:
    if state.get("error"):
        return {
            **state,
            "final_answer": f"请求失败：{state['error']}",
        }

    output = state["agent_output"]

    final_answer = "\n".join(
        [
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
            "",
            "生产控制点：",
            "- 已携带 request_id，便于追踪",
            "- 已携带 tenant_id / user_id，便于数据隔离",
            "- 已执行成本预算检查",
            "- ToolAgent 已生成幂等键，不真实执行写操作",
        ]
    )

    return {**state, "final_answer": final_answer}


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
        next_cost_units=output.cost_units if hasattr(output, "cost_units") else 1,
    )

    if not cost_check.allowed:
        return {**state, "error": cost_check.reason}

    return {
        **state,
        "current_cost_units": state.get("current_cost_units", 0)
        + (output.cost_units if hasattr(output, "cost_units") else 1),
        "agent_output": output.model_dump(),
    }


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
