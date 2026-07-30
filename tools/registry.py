\
\
\
\
\
\
\
\


from core.schemas import RiskLevel, ToolSpec


TOOLS = {
    "create_followup_task": ToolSpec(
        name="create_followup_task",
        description="创建本地业务跟进待办，记录后续需要业务员人工处理的事项",
        risk_level=RiskLevel.LOW_RISK_WRITE,
        required_roles=["operator"],
        idempotent=True,
    ),
    "generate_business_checklist": ToolSpec(
        name="generate_business_checklist",
        description="生成客户准入、合同、货转、结算单、开票申请检查清单",
        risk_level=RiskLevel.LOW_RISK_WRITE,
        required_roles=["operator"],
        idempotent=True,
    ),
    "draft_business_document": ToolSpec(
        name="draft_business_document",
        description="生成合同出具、货转出具、结算单出具、开票申请等内部文字草稿",
        risk_level=RiskLevel.LOW_RISK_WRITE,
        required_roles=["operator"],
        idempotent=True,
    ),
    "draft_business_report": ToolSpec(
        name="draft_business_report",
        description="生成内部业务说明、异常说明、交接说明或复盘报告草稿",
        risk_level=RiskLevel.LOW_RISK_WRITE,
        required_roles=["operator"],
        idempotent=True,
    ),
}


def get_tool(name: str) -> ToolSpec | None:

    return TOOLS.get(name)


def list_tools() -> list[ToolSpec]:

    return list(TOOLS.values())
