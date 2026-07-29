"""
阶段 4 生产骨架：工具注册表。

生产版不能让 Agent 随便调用任何函数。
每个工具都要先注册，并声明：
- 工具名；
- 风险等级；
- 是否幂等；
- 需要什么角色；
- 适合什么场景。

当前只注册模拟工具，不执行真实外部动作。
"""

from core.schemas import RiskLevel, ToolSpec


TOOLS = {
    "create_followup_task": ToolSpec(
        name="create_followup_task",
        description="创建客户跟进任务",
        risk_level=RiskLevel.LOW_RISK_WRITE,
        required_roles=["operator"],
        idempotent=True,
    ),
    "send_external_message": ToolSpec(
        name="send_external_message",
        description="发送外部消息",
        risk_level=RiskLevel.HIGH_RISK_WRITE,
        required_roles=["manager"],
        idempotent=False,
    ),
    "query_sales_metrics": ToolSpec(
        name="query_sales_metrics",
        description="查询销售指标",
        risk_level=RiskLevel.READONLY,
        required_roles=["analyst"],
        idempotent=True,
    ),
}


def get_tool(name: str) -> ToolSpec | None:
    return TOOLS.get(name)


def list_tools() -> list[ToolSpec]:
    return list(TOOLS.values())