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


import os

from rag.schemas import SearchHit


def rerank_hits(
    query: str,
    hits: list[SearchHit],
    top_k: int = 5,
) -> tuple[list[SearchHit], list[str]]:
\
\
\
\
\
\


    provider = os.getenv("RERANKER_PROVIDER", "none").strip().lower()
    warnings: list[str] = []

    if not hits:
        return [], warnings

    if provider in {"", "none", "local"}:
        return hits[:top_k], warnings

    if provider == "model":
        warnings.append(
            "RERANKER_PROVIDER=model 已配置，但阶段 3 当前版本尚未接入外部 rerank API，已返回混合检索排序。"
        )
        return hits[:top_k], warnings

    warnings.append(f"未知 RERANKER_PROVIDER={provider}，已返回混合检索排序。")
    return hits[:top_k], warnings
