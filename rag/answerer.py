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
\


from rag.reranker import rerank_hits
from rag.retriever import HybridSearchConfig, hybrid_search
from rag.schemas import RagAnswer, SearchHit


def compact_text(text: str, max_chars: int = 260) -> str:
\
\
\
\
\


    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text

    return text[:max_chars].rstrip() + "..."


def source_to_dict(hit: SearchHit) -> dict:
\
\
\
\
\


    return {
        "chunk_id": hit.chunk_id,
        "file_id": hit.file_id,
        "file_name": hit.file_name,
        "file_type": hit.file_type,
        "source_path": hit.source_path,
        "chunk_index": hit.chunk_index,
        "score": hit.score,
        "text": hit.text,
        "metadata": hit.metadata,
        "warnings": hit.warnings,
    }


def build_answer_text(query: str, hits: list[SearchHit], warnings: list[str]) -> str:
\
\
\
\
\
\
\
\
\


    if not hits:
        return (
            "未在业务资料索引中检索到足够相关的依据。"
            "请确认资料是否已入库，或换成更具体的问题，例如合同字段、结算单、货转文件、发票、化验单等。"
        )

    lines = [
        f"问题：{query}",
        "",
        "基于当前业务资料，检索到以下依据：",
    ]

    for index, hit in enumerate(hits, start=1):
        lines.extend(
            [
                "",
                f"{index}. 来源文件：{hit.file_name}",
                f"   chunk_id：{hit.chunk_id}",
                f"   匹配分：{hit.score:.4f}",
                f"   证据片段：{compact_text(hit.text)}",
            ]
        )

    if warnings:
        lines.extend(["", "检索警告："])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "回答说明：以上为阶段 3 MVP 的证据化回答，结论必须回到来源片段核对；后续可接入 LLM synthesis 做更自然的总结。",
        ]
    )

    return "\n".join(lines)


def answer_with_rag(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
) -> RagAnswer:
\
\
\
\
\
\
\
\
\


    config = HybridSearchConfig(top_k=top_k, candidate_k=candidate_k)
    candidates = hybrid_search(query=query, config=config)

    reranked_hits, rerank_warnings = rerank_hits(
        query=query,
        hits=candidates,
        top_k=top_k,
    )

    warnings: list[str] = []
    warnings.extend(rerank_warnings)

    for hit in reranked_hits:
        retrieval_warning = hit.metadata.get("retrieval_warning")
        if retrieval_warning and str(retrieval_warning) not in warnings:
            warnings.append(str(retrieval_warning))

    answer = build_answer_text(
        query=query,
        hits=reranked_hits,
        warnings=warnings,
    )

    return RagAnswer(
        answer=answer,
        sources=reranked_hits,
        warnings=warnings,
    )
