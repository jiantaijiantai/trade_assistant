# 阶段5 Loop Engineering 说明

本项目中的 Loop Engineering 是 LLM 驱动的业务任务闭环。

```text
用户目标
-> LLM Planner：理解任务，拆步骤，定义完成标准
-> Executor：调用 LangGraph 多 Agent
-> LLM Critic：检查结果是否达标，指出缺口
-> Reviser：根据 Critic 意见补调用或重试
-> LLM Critic After Revise：修正后复检
-> LLM Finalizer：整理最终答案
```

## 文件

| 文件 | 作用 |
|---|---|
| `loops/llm_loop.py` | 调用 `qwen3.6-plus` 完成 Planner、Critic、Finalizer |
| `loops/trade_task_loop.py` | 内部业务 Agent 闭环编排 |
| `loops/schemas.py` | LoopPlan、LoopCritique、LoopFinal、LoopStep 结构 |
| `api.py` | 新增 `POST /loop/chat` |

## 边界

- 大模型负责理解目标、评估结果和整理报告；
- LangGraph 负责实际路由和 Agent 执行；
- Reviser 只能执行白名单内的重试动作；
- 高风险外部业务动作仍不执行；
- 工具输出仍受权限、成本和幂等 key 控制。
