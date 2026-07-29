"""
FastAPI service interface.

负责把多 Agent 能力包装成 HTTP API。
核心原则：
1. API 层不写业务逻辑；
2. 业务逻辑继续放在 graph.production_graph；
3. 普通接口返回完整结果；
4. streaming 接口返回进度事件，改善长任务体验。
"""

import json
from typing import Generator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from graph.production_graph import run_production_multi_agent


app = FastAPI(
    title="trade_assistant API",
    version="1.0.0",
    description="Production API for the trade assistant.",
)


class ChatRequest(BaseModel):
    user_input: str = Field(..., description="用户输入的问题或任务")
    tenant_id: str = Field(default="tenant_demo", description="租户 ID")
    user_id: str = Field(default="user_demo", description="用户 ID")
    roles: list[str] = Field(
        default_factory=lambda: ["operator", "analyst"],
        description="用户角色，用于权限校验",
    )
    max_cost_units: int = Field(default=10, ge=0, description="最大成本预算")


class ChatResponse(BaseModel):
    request_id: str
    tenant_id: str
    user_id: str
    task_type: str | None = None
    route_reason: str | None = None
    route_confidence: float | None = None
    current_cost_units: int | None = None
    final_answer: str
    error: str | None = None


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "trade_assistant",
        "version": "1.0.0",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    state = run_production_multi_agent(
        user_input=request.user_input,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        roles=request.roles,
        max_cost_units=request.max_cost_units,
    )

    return ChatResponse(
        request_id=state["context"]["request_id"],
        tenant_id=state["context"]["tenant_id"],
        user_id=state["context"]["user_id"],
        task_type=state.get("task_type"),
        route_reason=state.get("route_reason"),
        route_confidence=state.get("route_confidence"),
        current_cost_units=state.get("current_cost_units"),
        final_answer=state.get("final_answer", ""),
        error=state.get("error"),
    )


def sse_event(event: str, data: dict) -> str:
    """
    Server-Sent Events 格式：
    event: xxx
    data: {...}

    前端或 curl 可以边接收边展示。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def event_generator() -> Generator[str, None, None]:
        yield sse_event("start", {"message": "请求已接收"})

        yield sse_event("progress", {"message": "正在进入 Supervisor 路由"})

        state = run_production_multi_agent(
            user_input=request.user_input,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            roles=request.roles,
            max_cost_units=request.max_cost_units,
        )

        yield sse_event(
            "progress",
            {
                "message": "Agent 执行完成",
                "task_type": state.get("task_type"),
                "route_reason": state.get("route_reason"),
            },
        )

        yield sse_event(
            "done",
            {
                "request_id": state["context"]["request_id"],
                "final_answer": state.get("final_answer", ""),
                "error": state.get("error"),
            },
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
