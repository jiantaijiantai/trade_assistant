

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from config import DASHSCOPE_BASE_URL, LLM_MODEL
from loops.schemas import LoopCritique, LoopFinal, LoopPlan


def _require_api_key() -> str:
\
\
\
\


    from config import DASHSCOPE_API_KEY

    if not DASHSCOPE_API_KEY or not DASHSCOPE_API_KEY.startswith("sk-"):
        raise RuntimeError("Loop Engineering 需要在 .env 中配置 DASHSCOPE_API_KEY=sk-...")
    return DASHSCOPE_API_KEY


def llm_plan(goal: str, available_actions: list[str], context: dict[str, Any]) -> LoopPlan:
    payload = {"goal": goal, "available_actions": available_actions, "context": context}
    data = _chat_json(
        system="你是 Loop Engineering Planner。拆解任务并定义完成标准。只输出 JSON。",
        user=(
            "请输出 JSON："
            "{\"task_understanding\":\"...\","
            "\"execution_steps\":[\"...\"],"
            "\"success_criteria\":[\"...\"]}\n"
            f"输入：{json.dumps(payload, ensure_ascii=False)}"
        ),
    )
    return LoopPlan.model_validate(data)


def llm_critique(goal: str, plan: LoopPlan, execution_result: dict[str, Any]) -> LoopCritique:
    payload = {
        "goal": goal,
        "plan": plan.model_dump(),
        "execution_result": _compact(execution_result),
        "allowed_revision_actions": [
            "rerun_agent_with_explicit_tool",
            "ask_for_more_business_docs",
            "no_revision_needed",
        ],
    }
    data = _chat_json(
        system=(
            "你是 Loop Engineering Critic。根据完成标准检查执行结果。"
            "修正动作必须来自 allowed_revision_actions。只输出 JSON。"
        ),
        user=(
            "请输出 JSON："
            "{\"passed\":true,"
            "\"issues\":[\"...\"],"
            "\"revision_actions\":[\"no_revision_needed\"],"
            "\"rationale\":\"...\"}\n"
            f"输入：{json.dumps(payload, ensure_ascii=False)}"
        ),
    )
    return LoopCritique.model_validate(data)


def llm_finalize(
    goal: str,
    plan: LoopPlan,
    execution_result: dict[str, Any],
    critique: LoopCritique,
    revision_result: dict[str, Any] | None,
) -> LoopFinal:
    payload = {
        "goal": goal,
        "plan": plan.model_dump(),
        "execution_result": _compact(execution_result),
        "critique": critique.model_dump(),
        "revision_result": _compact(revision_result or {}),
    }
    data = _chat_json(
        system="你是 Loop Engineering Finalizer。整理中文最终报告。只输出 JSON。",
        user=(
            "请输出 JSON："
            "{\"final_report\":\"使用 Markdown 的中文报告\","
            "\"user_next_steps\":[\"...\"]}\n"
            f"输入：{json.dumps(payload, ensure_ascii=False)}"
        ),
    )
    return LoopFinal.model_validate(data)


def _chat_json(system: str, user: str) -> dict[str, Any]:
    url = DASHSCOPE_BASE_URL.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": LLM_MODEL,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Authorization": f"Bearer {_require_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Loop LLM 请求失败：{exc.code} {error_body}") from exc

    content = payload["choices"][0]["message"]["content"]
    return _parse_json_object(content)


def _parse_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _compact(value: Any, limit: int = 5000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return {"truncated_json": text[:limit], "truncated": True}
