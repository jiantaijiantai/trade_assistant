\
\
\
\
\
\
\
\
\


import os
import sys

from dotenv import load_dotenv

load_dotenv()



if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")



DASHSCOPE_API_KEY = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://ws-ecos2rc1xkdccowk.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_NATIVE_BASE_URL = os.getenv(
    "DASHSCOPE_NATIVE_BASE_URL",
    "https://dashscope.aliyuncs.com/api/v1",
).strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen2.5-vl-embedding").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-plus").strip()




ROUTE_KEYWORDS = {
    "knowledge": ["是什么", "解释", "知识", "规则", "流程", "怎么理解"],
    "data": ["统计", "数据", "多少", "汇总", "分析", "趋势", "占比", "发运"],
    "tool": ["准入","新客户","新客商","合同出具","出具合同","货转","结算单","开票", "发票申请","待办","检查清单","帮我完成","生成",],
    "report": ["周报", "报告", "总结", "复盘", "说明"],
}

DEFAULT_ROUTE = "knowledge"
