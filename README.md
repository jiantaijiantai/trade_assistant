# trade_assistant

`trade_assistant` 是一个面向内部小团队的业务 Agent 助手 MVP。它的目标是演示内部知识问答、业务流程辅助、报告草稿生成和低风险工具调用闭环，而不是面向外部客户的 SaaS 产品。

## 项目定位

- 使用场景：约 20 人以内的内部业务团队。
- 核心价值：把分散的业务资料、流程经验和常见任务收束到一个可审计的 Agent 流程里。
- 展示重点：多 Agent 路由、状态图、白名单输出、工具调用权限元数据和可解释的业务辅助链路。
- 当前边界：真实写操作默认关闭，外部系统工具需要接入后再开放。

## Run

```bash
pip install -r requirements.txt
uvicorn api:app --reload
```

## API

- `GET /health`
- `POST /chat`
- `POST /chat/stream`

The API returns a whitelisted response only. Internal graph state and trace data are kept out of the public response by default.

## Configuration

Copy `.env.example` to `.env` only for local model-backed experiments:

```bash
cp .env.example .env
```

Do not commit `.env` or real service credentials.

## Data Boundary

可以提交到 GitHub：

- 脱敏后的流程样例和演示数据。
- 业务规则、Agent 状态图、测试和文档。
- 不包含真实客户、合同、发票、结算信息的示例材料。

不要提交到 GitHub：

- `业务资料/` 下的真实合同、发票、结算单、货转、化验单、磅单等材料。
- `.env`、真实 API key、私有模型端点。
- 本地缓存、向量库、运行输出和虚拟环境。

## Notes

- Runtime graph entry: `graph.production_graph.run_production_multi_agent`.
- Tool calls are planned with permission and idempotency metadata, but write actions are still disabled until real external tools are connected.
