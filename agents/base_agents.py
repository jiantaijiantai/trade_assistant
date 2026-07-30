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


from typing import Any, Literal

from pydantic import BaseModel, Field

from config import DEFAULT_ROUTE, ROUTE_KEYWORDS
from rag.answerer import answer_with_rag


TaskType = Literal["knowledge", "data", "tool", "report"]


class RouteDecision(BaseModel):


    task_type: TaskType = Field(description="被路由到的 Agent 类型")
    reason: str = Field(description="为什么这样路由")


class AgentOutput(BaseModel):


    agent_name: str
    task_type: TaskType
    answer: str
    evidence: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class Supervisor:
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


    name = "KnowledgeAgent"

    def run(self, user_input: str) -> AgentOutput:
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


        rag_answer = answer_with_rag(
            query=user_input,
            top_k=5,
            candidate_k=20,
        )

        return AgentOutput(
            agent_name=self.name,
            task_type="knowledge",
            answer=rag_answer.answer,
            evidence=[
                f"{source.file_name} | chunk_id={source.chunk_id} | score={source.score:.4f}"
                for source in rag_answer.sources
            ],
            sources=[source_to_api_dict(source) for source in rag_answer.sources],
            next_steps=[
                "核对来源片段后再用于真实业务判断",
                "如召回不准确，可调整 chunk_size、overlap、top_k 或补充资料",
            ],
        )


class DataAgent:


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


    name = "ToolAgent"

    def run(self, user_input: str) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            task_type="tool",
            answer=(
                "这是团队内部业务文字辅助任务。系统会根据业务员输入生成本地待办、"
                "检查清单或文字草稿，帮助整理客户准入、合同、货转、结算单、开票申请等日常材料。"
            ),
            evidence=[
                "适合处理：客户准入资料核对、合同字段整理、货转字段核对、结算单字段整理、开票申请资料整理",
                "工具只生成本地文件，供业务员人工复核和继续处理",
            ],
            next_steps=[
                "为每个工具定义输入输出 schema",
                "根据真实业务材料持续补充字段模板",
                "把生成结果用于本地演示、截图和业务交接说明",
            ],
        )


class ReportAgent:


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


def source_to_api_dict(source) -> dict[str, Any]:
\
\
\
\
\


    return {
        "chunk_id": source.chunk_id,
        "file_name": source.file_name,
        "file_type": source.file_type,
        "source_path": source.source_path,
        "chunk_index": source.chunk_index,
        "score": source.score,
        "text": source.text,
        "metadata": source.metadata,
        "warnings": source.warnings,
    }
