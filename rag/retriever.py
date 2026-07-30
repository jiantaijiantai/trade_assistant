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


from dataclasses import dataclass

from rag.chroma_store import query_vectors
from rag.embeddings import embed_texts, load_embedding_config
from rag.lexical_index import search_lexical
from rag.schemas import SearchHit


@dataclass
class HybridSearchConfig:


    top_k: int = 5
    candidate_k: int = 20
    vector_weight: float = 0.65
    lexical_weight: float = 0.35
    chroma_dir: str = "outputs/rag/chroma"
    collection_name: str = "trade_business_docs_api"
    lexical_index_path: str = "outputs/rag/business_lexical_index.json"
    allow_lexical_fallback: bool = True


def merge_hybrid_hits(
    vector_hits: list[SearchHit],
    lexical_hits: list[SearchHit],
    vector_weight: float = 0.65,
    lexical_weight: float = 0.35,
) -> list[SearchHit]:
\
\
\
\
\
\
\
\


    merged: dict[str, SearchHit] = {}

    for hit in vector_hits:
        merged_hit = hit.model_copy(deep=True)
        merged_hit.metadata["vector_score"] = hit.score
        merged_hit.metadata["lexical_score"] = 0.0
        merged_hit.score = vector_weight * hit.score
        merged[hit.chunk_id] = merged_hit

    for hit in lexical_hits:
        if hit.chunk_id in merged:
            existing = merged[hit.chunk_id]
            existing.metadata["lexical_score"] = hit.score
            existing.score += lexical_weight * hit.score
        else:
            merged_hit = hit.model_copy(deep=True)
            merged_hit.metadata["vector_score"] = 0.0
            merged_hit.metadata["lexical_score"] = hit.score
            merged_hit.score = lexical_weight * hit.score
            merged[hit.chunk_id] = merged_hit

    return sorted(merged.values(), key=lambda item: item.score, reverse=True)


def lexical_only_search(
    query: str,
    config: HybridSearchConfig,
    warning: str,
) -> list[SearchHit]:
\
\
\
\
\
\
\
\
\


    hits = search_lexical(
        query=query,
        top_k=config.top_k,
        index_path=config.lexical_index_path,
    )

    for hit in hits:
        hit.metadata["vector_score"] = 0.0
        hit.metadata["lexical_score"] = hit.score
        hit.metadata["retrieval_mode"] = "lexical_only"
        hit.metadata["retrieval_warning"] = warning

    return hits


def hybrid_search(
    query: str,
    config: HybridSearchConfig | None = None,
) -> list[SearchHit]:
\
\
\
\
\
\
\
\


    config = config or HybridSearchConfig()

    lexical_hits = search_lexical(
        query=query,
        top_k=config.candidate_k,
        index_path=config.lexical_index_path,
    )

    try:
        embedding_config = load_embedding_config()
        query_embedding = embed_texts([query], config=embedding_config)[0]

        vector_hits = query_vectors(
            query_embedding=query_embedding,
            top_k=config.candidate_k,
            persist_dir=config.chroma_dir,
            collection_name=config.collection_name,
        )

    except Exception as exc:
        if not config.allow_lexical_fallback:
            raise

        return lexical_only_search(
            query=query,
            config=config,
            warning=f"向量召回失败，已降级为 BM25-only：{exc}",
        )

    merged_hits = merge_hybrid_hits(
        vector_hits=vector_hits,
        lexical_hits=lexical_hits,
        vector_weight=config.vector_weight,
        lexical_weight=config.lexical_weight,
    )

    return merged_hits[: config.top_k]
