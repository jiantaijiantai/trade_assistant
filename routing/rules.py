from __future__ import annotations

from routing.schemas import RouteDecision, TaskType


HIGH_CONFIDENCE_RULES: dict[TaskType, list[str]] = {
    "tool": [
        "准入",
        "新客户",
        "合同出具",
        "出具合同",
        "货转",
        "结算单",
        "开票",
        "发票申请",
        "待办",
        "检查清单",
        "生成",
    ],
    "data": [
        "统计",
        "数据",
        "多少",
        "汇总",
        "分析",
        "趋势",
        "占比",
        "发运",
    ],
    "report": [
        "周报",
        "报告",
        "总结",
        "复盘",
        "说明",
        "交接",
    ],
    "knowledge": [
        "是什么",
        "解释",
        "知识",
        "规则",
        "流程",
        "怎么理解",
        "如何理解",
    ],
}


def route_by_rules(user_input: str) -> RouteDecision | None:
    text = user_input.strip()
    if not text:
        return None

    for task_type, keywords in HIGH_CONFIDENCE_RULES.items():
        for keyword in keywords:
            if keyword in text:
                return RouteDecision(
                    task_type=task_type,
                    confidence=0.95,
                    reason=f"命中高确定性业务关键词：{keyword}",
                    source="rule",
                    matched_keyword=keyword,
                )

    return None

