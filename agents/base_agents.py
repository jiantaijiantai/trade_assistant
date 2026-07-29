"""
阶段 4：多 Agent 学习版。

这个文件先把所有 Agent 放在一起，方便完整闭环。
后续生产版可以再拆成：
- supervisor.py
- knowledge_agent.py
- data_agent.py
- tool_agent.py
- report_agent.py

核心思想：
Supervisor 不直接回答问题，而是判断任务应该交给哪个 Agent。
每个 Agent 只负责一种类型的任务，最后由图流程统一汇总结果。
"""

from typing import Literal

from pydantic import BaseModel, Field

from config import DEFAULT_ROUTE, ROUTE_KEYWORDS


TaskType = Literal["knowledge", "data", "tool", "report"]


class RouteDecision(BaseModel):
    """Supervisor 的路由决策结果。"""

    task_type: TaskType = Field(description="被路由到的 Agent 类型")
    reason: str = Field(description="为什么这样路由")


class AgentOutput(BaseModel):
    """每个 Agent 的统一输出格式。"""

    agent_name: str
    task_type: TaskType
    answer: str
    evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class Supervisor:
    """
    Supervisor 负责意图识别和任务路由。

    版使用关键词规则，优点：
    1. 不需要 API Key；
    2. 结果稳定，方便验证；
    3. 你能清楚看到路由规则如何影响 Agent 选择。

    生产版可以替换成 LLM 分类器：
    用户输入 -> LLM 输出结构化 RouteDecision -> LangGraph 路由。
    """

    def route(self, user_input: str) -> RouteDecision:
        text = user_input.strip()

        for task_type, keywords in ROUTE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return RouteDecision(
                        task_type=task_type,
                        reason=f"命中关键词：{keyword}",
                    )

        return RouteDecision(
            task_type=DEFAULT_ROUTE,
            reason="未命中明确关键词，默认进入知识问答 Agent",
        )


class KnowledgeAgent:
    """知识问答 Agent：负责业务知识、规则、流程解释。"""

    name = "KnowledgeAgent"

    def run(self, user_input: str) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            task_type="knowledge",
            answer=(
                "这是知识问答类任务。当前学习版会返回模拟知识答案；"
                "生产版应接入 RAG 检索，从业务知识库中召回依据后再回答。"
            ),
            evidence=[
                "可接入制度文档、FAQ、SOP、业务知识库",
                "适合回答：规则是什么、流程怎么走、概念如何理解",
            ],
            next_steps=[
                "阶段 5 可把这里替换成 Hybrid Search + Rerank",
                "增加引用来源，避免无依据回答",
            ],
        )


class DataAgent:
    """数据分析 Agent：负责统计、趋势、指标解释。"""

    name = "DataAgent"

    def run(self, user_input: str) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            task_type="data",
            answer=(
                "这是数据分析类任务。当前学习版会返回模拟分析结果；"
                "生产版应连接数据库、CSV、Excel 或 BI 接口进行真实统计。"
            ),
            evidence=[
                "适合处理：销售额、订单数、转化率、同比环比、Top N",
                "需要保证数据口径、时间范围和权限控制",
            ],
            next_steps=[
                "增加结构化查询参数",
                "把自然语言问题转换成 SQL 或 DataFrame 操作",
            ],
        )


class ToolAgent:
    """工具执行 Agent：负责调用外部工具或执行业务流程。"""

    name = "ToolAgent"

    def run(self, user_input: str) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            task_type="tool",
            answer=(
                "这是工具执行类任务。当前学习版不会真实执行外部动作；"
                "生产版必须增加权限校验、参数校验、审计日志和失败回滚。"
            ),
            evidence=[
                "适合处理：发送通知、创建任务、更新状态、触发流程",
                "高风险操作不能只靠 Agent 自己决定",
            ],
            next_steps=[
                "为每个工具定义输入输出 schema",
                "区分只读工具和写入工具",
                "重要操作增加人工确认",
            ],
        )


class ReportAgent:
    """报告生成 Agent：负责周报、复盘、分析报告。"""

    name = "ReportAgent"

    def run(self, user_input: str) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            task_type="report",
            answer=(
                "这是报告生成类任务。当前学习版返回固定报告框架；"
                "生产版应汇总知识检索、数据分析和业务动作结果后生成报告。"
            ),
            evidence=[
                "适合处理：周报、经营分析、项目复盘、客户跟进总结",
                "报告类任务通常需要多个 Agent 的中间结果",
            ],
            next_steps=[
                "设计固定报告模板",
                "增加事实引用和数据来源",
                "输出 Markdown / DOCX / PDF",
            ],
        )