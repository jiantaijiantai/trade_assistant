\
\
\
\
\
\
\


from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.schemas import RequestContext, ToolSpec


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def execute_tool(
    *,
    context: RequestContext,
    tool: ToolSpec,
    user_input: str,
    idempotency_key: str,
    business_id: str,
) -> dict[str, Any]:
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


    if tool.name == "create_followup_task":
        return _create_followup_task(context, user_input, idempotency_key, business_id)

    if tool.name == "generate_business_checklist":
        return _generate_business_checklist(context, user_input, idempotency_key, business_id)

    if tool.name == "draft_business_document":
        return _draft_business_document(context, user_input, idempotency_key, business_id)

    if tool.name == "draft_business_report":
        return _draft_business_report(context, user_input, idempotency_key, business_id)

    return {
        "executed": False,
        "mode": "unsupported",
        "message": f"工具已注册，但尚未实现执行器：{tool.name}",
    }


def _create_followup_task(
    context: RequestContext,
    user_input: str,
    idempotency_key: str,
    business_id: str,
) -> dict[str, Any]:


    scene = _infer_scene(user_input)
    payload = {
        "task_id": idempotency_key,
        "business_id": business_id,
        "created_at": _now(),
        "created_by": context.user_id,
        "tenant_id": context.tenant_id,
        "source_request": user_input,
        "business_scene": scene,
        "status": "待业务员处理",
        "priority": _infer_priority(user_input),
        "next_action": _next_action_for_scene(scene),
        "check_points": _check_points_for_scene(scene),
        "boundary": "本待办仅用于内部文字性跟进，供业务员人工复核和继续处理。",
    }

    path = OUTPUT_ROOT / "tasks" / f"{idempotency_key}.json"
    return _write_json(path, payload, "已生成本地业务跟进待办")


def _generate_business_checklist(
    context: RequestContext,
    user_input: str,
    idempotency_key: str,
    business_id: str,
) -> dict[str, Any]:


    scene = _infer_scene(user_input)
    check_points = _check_points_for_scene(scene)
    lines = "\n".join(f"- [ ] {item}" for item in check_points)

    content = f"""# {scene}检查清单

## 基本信息

- 生成时间：{_now()}
- 业务员：{context.user_id}
- 业务编号：{business_id}
- 原始需求：{user_input}

## 检查事项

{lines}

## 常见异常提醒

- 新客商准入资料不全时，先补齐资料再进入后续业务。
- 下游客户提货或付款超期时，需要单独记录并人工跟进。
- 质数量存在争议时，先核对合同、货转、结算单、化验单、轨道衡或水尺单据。
- 合同和结算单字段不一致时，先暂停使用该版本作为最终依据，定位差异字段。

## 使用边界

本清单只用于内部业务员日常核对和材料整理。
"""

    path = OUTPUT_ROOT / "checklists" / f"{idempotency_key}.md"
    return _write_text(path, content, "已生成本地业务检查清单")


def _draft_business_document(
    context: RequestContext,
    user_input: str,
    idempotency_key: str,
    business_id: str,
) -> dict[str, Any]:


    scene = _infer_scene(user_input)
    content = f"""# {scene}内部文字草稿

## 基本信息

- 生成时间：{_now()}
- 经办业务员：{context.user_id}
- 业务编号：{business_id}
- 需求描述：{user_input}

## 需整理字段

{_field_template_for_scene(scene)}

## 初步办理说明

{_draft_text_for_scene(scene)}

## 待人工确认

- 相关主体名称是否与合同、货转、结算单、发票资料保持一致。
- 数量、质量、金额、交付节点是否有明确依据。
- 需要引用的资料是否来自同一业务链条。
- 如发现差异，应先记录差异字段，再由业务员人工确认处理口径。

## 使用边界

本文档为内部文字草稿，用于业务员整理字段、核对资料和交接说明。
"""

    path = OUTPUT_ROOT / "reports" / f"{idempotency_key}.md"
    return _write_text(path, content, "已生成内部业务文字草稿")


def _draft_business_report(
    context: RequestContext,
    user_input: str,
    idempotency_key: str,
    business_id: str,
) -> dict[str, Any]:


    scene = _infer_scene(user_input)
    content = f"""# {scene}业务说明草稿

## 事项背景

- 生成时间：{_now()}
- 业务员：{context.user_id}
- 业务编号：{business_id}
- 原始需求：{user_input}

## 当前事项

本说明用于整理当前业务事项的资料完整性、关键核对点和后续人工跟进事项。

## 已识别重点

{_bullet_lines(_check_points_for_scene(scene))}

## 后续建议

1. 先补齐缺失资料，并标注资料来源。
2. 对主体、数量、质量、金额、交付、结算字段逐项核对。
3. 对存在争议或不一致的字段单独记录，避免直接进入后续使用。
4. 需要正式办理的事项，仍按公司既有流程处理。

## 使用边界

本报告仅用于内部文字整理和业务交接，不替代正式业务文件。
"""

    path = OUTPUT_ROOT / "reports" / f"{idempotency_key}.md"
    return _write_text(path, content, "已生成内部业务说明草稿")


def _infer_scene(text: str) -> str:


    if "准入" in text or "新客户" in text or "新客商" in text:
        return "客户准入"
    if "货转" in text:
        return "货转出具"
    if "结算" in text:
        return "结算单出具"
    if "开票" in text or "发票" in text:
        return "开票申请"
    if "报告" in text or "总结" in text or "说明" in text:
        return "业务说明"
    return "合同出具"


def _infer_priority(text: str) -> str:


    urgent_words = ["超期", "争议", "不全", "缺", "暂停", "异常", "不一致"]
    return "高" if any(word in text for word in urgent_words) else "普通"


def _next_action_for_scene(scene: str) -> str:
    mapping = {
        "客户准入": "核对工商资料、贸易材料、税务资料是否齐全并加盖公章。",
        "合同出具": "整理合同主体、货物信息、价格金额、交付条款、结算条款。",
        "货转出具": "核对货转双方名称、关联合同编号、数量和货权转移节点。",
        "结算单出具": "核对结算双方主体、数量、质量、金额及双方确认情况。",
        "开票申请": "根据结算单和开票申请要求整理开票信息。",
        "业务说明": "整理事项背景、已核对资料、异常点和后续建议。",
    }
    return mapping.get(scene, "整理业务资料并完成人工复核。")


def _check_points_for_scene(scene: str) -> list[str]:


    templates = {
        "客户准入": [
            "企业资质、法人身份证、一般纳税人证明或系统截图是否齐全",
            "工商资料和税务资料是否加盖公章",
            "近期上游材料是否包含进项票、付款单据、物流单据",
            "近期下游材料是否包含销项票、合同、回款单据、运输单据",
            "最近连续 3 个月完税材料、进项认证清单、纳税信用级别截图是否齐全",
        ],
        "合同出具": [
            "买方、卖方名称是否准确",
            "品名、规格、数量是否明确",
            "单价、总金额、币种是否明确",
            "金额大小写是否一致",
            "交货地点、交货时间、运输方式是否明确",
            "如涉及货转，货权转移节点是否明确",
            "结算方式、账期、发票要求、保证金约定是否明确",
        ],
        "货转出具": [
            "货转双方名称是否与合同一致",
            "关联合同编号是否正确",
            "货转数量是否与实际业务一致",
            "货转方式和货权转移节点是否明确",
        ],
        "结算单出具": [
            "结算双方主体是否一致",
            "结算数量是否与合同、货转、物流单据一致",
            "结算质量是否与化验单或约定质量指标一致",
            "结算金额是否与单价、数量、扣罚项计算一致",
            "开票前结算单是否已双方确认",
        ],
        "开票申请": [
            "开票主体、购方信息、销方信息是否准确",
            "开票金额是否与结算单一致",
            "开票品名、税率、数量是否与合同和结算资料一致",
            "开票前结算单是否已双方确认",
        ],
    }
    return templates.get(scene, ["整理事项背景", "核对相关资料", "记录异常点", "形成后续跟进建议"])


def _field_template_for_scene(scene: str) -> str:
    fields = {
        "客户准入": "- 客户名称：\n- 工商资料：\n- 贸易材料：\n- 税务资料：\n- 缺失资料：",
        "合同出具": "- 买方：\n- 卖方：\n- 品名规格：\n- 数量：\n- 单价/金额：\n- 交付条款：\n- 结算条款：",
        "货转出具": "- 转出方：\n- 转入方：\n- 关联合同编号：\n- 货转数量：\n- 货权转移节点：",
        "结算单出具": "- 结算双方：\n- 结算数量：\n- 质量指标：\n- 结算单价：\n- 结算金额：\n- 需说明差异：",
        "开票申请": "- 购方信息：\n- 销方信息：\n- 开票品名：\n- 开票金额：\n- 税率：\n- 结算单确认情况：",
    }
    return fields.get(scene, "- 事项：\n- 资料：\n- 异常：\n- 建议：")


def _draft_text_for_scene(scene: str) -> str:
    return f"请业务员根据《{scene}》相关资料补充空缺字段，并结合原始合同、货转、结算单、发票或客户准入资料进行人工确认。"


def _bullet_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _write_json(path: Path, payload: dict[str, Any], message: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "executed": True,
        "mode": "local_file",
        "path": str(path),
        "message": message,
        "data": payload,
    }


def _write_text(path: Path, content: str, message: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return {
        "executed": True,
        "mode": "local_file",
        "path": str(path),
        "message": message,
    }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
