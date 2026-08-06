# 优化与微调必要性证据

## 结论

在 12 组真实煤炭贸易跨文档样本上，历史严格评估中最佳 Prompt 组合为 25.0%；补充 5 条高质量 few-shot 示例并使用 Schema/Retry 后，本次实测结构化三组均达到 100.0%。因此，在当前样本和当前评估器下，未观察到必须进行 QLoRA 微调的必要性。

## 数据对比

| Prompt 组 | 历史结果 | 5-shot 结果 |
|---|---:|---:|
| raw_quality_prompt | 0.0% | 0.0% |
| schema_quality_prompt | 0.0% | 100.0% |
| few_shot_quality_prompt | 16.7% | 100.0% |
| few_shot_schema_retry_prompt | 25.0% | 100.0% |

## 证据截图

![前后对比](C:\Users\86182\Desktop\分阶段双项目\project1\outputs\phase6_qwen_plus_prompt_need_evidence\prompt_before_after_summary.png)

![实验上下文](C:\Users\86182\Desktop\分阶段双项目\project1\outputs\phase6_qwen_plus_prompt_need_evidence\experiment_context_evidence.png)

![5-shot 明细](C:\Users\86182\Desktop\分阶段双项目\project1\outputs\phase6_qwen_plus_prompt_need_evidence\five_shot_metric_detail.png)

![5-shot 标准指标汇总](C:\Users\86182\Desktop\分阶段双项目\project1\outputs\phase6_qwen_plus_2025_07_14_5shot\quality_03_metric_summary.png)

## 使用限制

历史 25% 结果的原始 JSON 已被后续运行覆盖，本文件中的历史值来自当时运行输出记录和对话标注；5-shot 结果来自当前目录中的真实 `quality_summary.json`、`quality_results.json`、`quality_case_results.csv`。
