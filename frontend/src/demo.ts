import type { TradeChatResult } from "./api";

export const sampleQuestion =
  "请基于内部业务资料，生成一份合同检查待办，并说明哪些字段必须人工复核。";

export const demoResult: TradeChatResult = {
  request_id: "trade-demo-001",
  final_answer:
    "已生成合同检查待办草稿。建议人工复核供应商主体、合同金额、付款节点、发票信息、验收材料和结算附件一致性。外部发送、审批状态更新等高风险动作保持 dry-run。",
  evidence: [
    "命中合同检查流程样例",
    "工具计划 generate_contract_checklist",
    "operator 与 analyst 可生成本地草稿"
  ],
  sources: [
    { file: "sample_business_docs/contract_checklist.md", chunk_id: "contract-002", score: 0.84 },
    { file: "sample_business_docs/settlement_rules.md", chunk_id: "settlement-004", score: 0.78 }
  ],
  next_steps: ["人工复核金额和主体信息", "补充缺失附件", "确认是否需要负责人审批"]
};
