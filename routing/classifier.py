from __future__ import annotations

from collections import Counter

from routing.schemas import RouteDecision, TaskType


CLASSIFIER_SIGNALS: dict[TaskType, list[str]] = {
    "knowledge": [
        "请问",
        "为什么",
        "依据",
        "口径",
        "规则",
        "流程",
        "注意事项",
        "材料要求",
        "需要哪些",
    ],
    "data": [
        "列表",
        "明细",
        "金额",
        "吨数",
        "客户数量",
        "同比",
        "环比",
        "排名",
        "筛选",
        "查询",
    ],
    "tool": [
        "帮我",
        "办理",
        "创建",
        "草稿",
        "模板",
        "核对",
        "整理",
        "补全",
        "提交",
        "更新",
    ],
    "report": [
        "写一份",
        "形成",
        "汇报",
        "纪要",
        "异常说明",
        "经营分析",
        "项目复盘",
        "交接说明",
    ],
}

HIGH_RISK_WRITE_SIGNALS = ["付款", "打款", "合同生效", "正式提交", "审批通过", "开具发票", "变更客户"]
MISSING_BUSINESS_OBJECT_SIGNALS = ["这个", "那个", "上述", "前面", "相关材料"]
PROMPT_INJECTION_SIGNALS = ["忽略", "绕过", "无视", "不要检查权限", "其他租户", "泄露", "直接告诉我"]
CONFLICT_SIGNALS = ["冲突", "不一致", "错误编号", "金额高的", "直接按"]


def classify_security_risk(user_input: str) -> RouteDecision | None:
    text = user_input.strip()
    risk_flags: list[str] = []

    if any(signal in text for signal in PROMPT_INJECTION_SIGNALS):
        risk_flags.append("possible_prompt_injection")

    if any(signal in text for signal in CONFLICT_SIGNALS):
        risk_flags.append("conflicting_or_unverified_business_data")

    if any(signal in text for signal in HIGH_RISK_WRITE_SIGNALS):
        risk_flags.append("possible_high_risk_write")

    if not risk_flags:
        return None

    return RouteDecision(
        task_type="tool" if "possible_high_risk_write" in risk_flags else "knowledge",
        confidence=0.5,
        reason="检测到安全或业务风险信号，需要澄清和人工确认后再继续",
        source="classifier",
        risk_flags=risk_flags,
        needs_clarification=True,
    )


def classify_with_heuristics(user_input: str) -> RouteDecision:
    text = user_input.strip()
    scores: Counter[TaskType] = Counter()

    for task_type, signals in CLASSIFIER_SIGNALS.items():
        for signal in signals:
            if signal in text:
                scores[task_type] += 1

    if not scores:
        return RouteDecision(
            task_type="knowledge",
            confidence=0.42,
            reason="未命中高确定性规则，分类信号不足，需要澄清用户意图",
            source="classifier",
            missing_fields=["task_intent"],
            needs_clarification=True,
        )

    ranked = scores.most_common()
    best_task, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    margin = best_score - second_score

    confidence = min(0.74, 0.52 + best_score * 0.08 + margin * 0.06)
    missing_fields: list[str] = []
    risk_flags: list[str] = []

    if margin == 0 and len(ranked) > 1:
        confidence = min(confidence, 0.54)
        missing_fields.append("route_intent")

    if any(signal in text for signal in MISSING_BUSINESS_OBJECT_SIGNALS):
        confidence = min(confidence, 0.56)
        missing_fields.append("business_object")

    if any(signal in text for signal in HIGH_RISK_WRITE_SIGNALS):
        risk_flags.append("possible_high_risk_write")
        confidence = min(confidence, 0.58)

    needs_clarification = confidence < 0.6

    return RouteDecision(
        task_type=best_task,
        confidence=round(confidence, 2),
        reason=f"未命中高确定性规则，按结构化分类信号判断为 {best_task}",
        source="classifier",
        missing_fields=missing_fields,
        risk_flags=risk_flags,
        needs_clarification=needs_clarification,
    )
