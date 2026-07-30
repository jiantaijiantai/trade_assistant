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
\
\
\
\


from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Generator

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config import ROUTE_KEYWORDS
from graph.production_graph import run_production_multi_agent
from ingestion.build_index import DEFAULT_MANIFEST_PATH, SUPPORTED_EXTENSIONS, build_index
from loops.trade_task_loop import run_trade_task_loop
from rag.chroma_store import DEFAULT_CHROMA_DIR
from rag.lexical_index import DEFAULT_LEXICAL_INDEX_PATH
from tools.registry import list_tools


app = FastAPI(
    title="trade_assistant API",
    version="1.0.0",
    description="Internal team trade assistant API with multi-agent routing, RAG sources, and low-risk local tool plans.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5175",
        "http://localhost:5173",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("outputs/uploads/business_docs")
RAG_COLLECTION_NAME = "trade_business_docs_api"


class ChatRequest(BaseModel):
\
\
\
\


    user_input: str = Field(..., min_length=1, description="用户输入的问题或任务")
    tenant_id: str = Field(default="tenant_demo", description="租户 ID")
    user_id: str = Field(default="user_demo", description="用户 ID")
    roles: list[str] = Field(
        default_factory=lambda: ["operator", "analyst"],
        description="用户角色，用于权限校验",
    )
    max_cost_units: int = Field(default=10, ge=0, description="最大成本预算")


class ChatResponse(BaseModel):
\
\
\
\
\
\
\


    request_id: str
    tenant_id: str
    user_id: str
    task_type: str | None = None
    route_reason: str | None = None
    route_confidence: float | None = None
    current_cost_units: int | None = None
    final_answer: str
    evidence: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    tool_plan: dict[str, Any] | None = None
    tool_execution: dict[str, Any] | None = None
    error: str | None = None


class TradeLoopRequest(ChatRequest):
\
\
\
\


    goal: str = Field(default="完成内部业务 Agent 助手闭环", description="用户目标")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:


    return JSONResponse(
        status_code=422,
        content={
            "error": "请求参数校验失败",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
\
\
\
\


    return JSONResponse(
        status_code=500,
        content={
            "error": "服务处理失败",
            "detail": str(exc),
        },
    )


@app.get("/health")
def health_check() -> dict:


    return {
        "status": "ok",
        "service": "trade_assistant",
        "version": "1.0.0",
    }


@app.get("/capabilities")
def capabilities() -> dict:
\
\
\
\
\
\
\
\


    return {
        "service": "trade_assistant",
        "agents": [
            {
                "name": "KnowledgeAgent",
                "task_type": "knowledge",
                "description": "基于业务资料 RAG 回答规则、流程和知识问题",
            },
            {
                "name": "DataAgent",
                "task_type": "data",
                "description": "当前返回数据分析框架，后续可接 CSV、Excel、数据库或 BI",
            },
            {
                "name": "ToolAgent",
                "task_type": "tool",
                "description": "生成本地待办、检查清单、业务文字草稿等低风险文件",
            },
            {
                "name": "ReportAgent",
                "task_type": "report",
                "description": "生成周报、复盘、交接说明等文字报告",
            },
        ],
        "route_keywords": ROUTE_KEYWORDS,
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "required_roles": tool.required_roles,
                "idempotent": tool.idempotent,
            }
            for tool in list_tools()
        ],
        "boundaries": [
            "只处理团队内部文字辅助任务",
            "不连接 ERP、OA、财务、审批或外部消息系统",
            "低风险工具只生成本地文件，必须由业务员人工复核",
            "RAG 回答必须查看 sources 后再用于真实业务判断",
        ],
    }


@app.post("/documents/upload")
def upload_business_document(file: UploadFile = File(...)) -> dict:


    upload_path = _save_upload(file, UPLOAD_DIR, SUPPORTED_EXTENSIONS)
    stats = build_index(
        argparse.Namespace(
            input=str(UPLOAD_DIR),
            mode="append",
            manifest=DEFAULT_MANIFEST_PATH,
            chroma_dir=DEFAULT_CHROMA_DIR,
            collection_name=RAG_COLLECTION_NAME,
            lexical_index=DEFAULT_LEXICAL_INDEX_PATH,
            chunk_size=800,
            overlap=120,
            tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            tessdata_dir=str(Path(__file__).resolve().parent.parent / "ocr_tessdata"),
            ocr_lang="chi_sim+eng",
        )
    )

    return {
        "uploaded": True,
        "file_name": upload_path.name,
        "path": str(upload_path),
        "index_stats": stats,
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

    return _state_to_chat_response(state)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
\
\
\
\
\
\
\
\


    def event_generator() -> Generator[str, None, None]:
        yield _sse_event("start", {"message": "请求已接收"})
        yield _sse_event("progress", {"message": "正在进入 Supervisor 路由"})

        state = run_production_multi_agent(
            user_input=request.user_input,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            roles=request.roles,
            max_cost_units=request.max_cost_units,
        )

        yield _sse_event(
            "progress",
            {
                "message": "Agent 执行完成",
                "task_type": state.get("task_type"),
                "route_reason": state.get("route_reason"),
            },
        )

        response = _state_to_chat_response(state)
        yield _sse_event("done", response.model_dump())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@app.post("/loop/chat")
def trade_loop_chat(request: TradeLoopRequest) -> dict:


    result = run_trade_task_loop(
        goal=request.goal,
        user_input=request.user_input,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        roles=request.roles,
        max_cost_units=request.max_cost_units,
    )
    return result.model_dump()


def _state_to_chat_response(state: dict[str, Any]) -> ChatResponse:


    context = state.get("context", {})
    agent_output = state.get("agent_output", {})

    return ChatResponse(
        request_id=context.get("request_id", ""),
        tenant_id=context.get("tenant_id", ""),
        user_id=context.get("user_id", ""),
        task_type=state.get("task_type"),
        route_reason=state.get("route_reason"),
        route_confidence=state.get("route_confidence"),
        current_cost_units=state.get("current_cost_units"),
        final_answer=state.get("final_answer", ""),
        evidence=agent_output.get("evidence", []),
        sources=agent_output.get("sources", []),
        next_steps=agent_output.get("next_steps", []),
        tool_plan=agent_output.get("tool_plan"),
        tool_execution=agent_output.get("tool_execution"),
        error=state.get("error"),
    )


def _sse_event(event: str, data: dict[str, Any]) -> str:


    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _save_upload(file: UploadFile, upload_dir: Path, supported_extensions: set[str]) -> Path:


    original_name = Path(file.filename or "").name
    if not original_name:
        raise HTTPException(status_code=400, detail="上传文件缺少文件名")

    suffix = Path(original_name).suffix.lower()
    if suffix not in supported_extensions:
        allowed = ", ".join(sorted(supported_extensions))
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{suffix}；支持：{allowed}")

    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / original_name
    counter = 1
    while target.exists():
        target = upload_dir / f"{Path(original_name).stem}_{counter}{suffix}"
        counter += 1

    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    return target
