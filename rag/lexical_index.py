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


import json
import math
import re
from collections import Counter
from pathlib import Path

from rag.schemas import DocumentChunk, MetadataValue, SearchHit


DEFAULT_LEXICAL_INDEX_PATH = "outputs/rag/business_lexical_index.json"


def tokenize(text: str) -> list[str]:
\
\
\
\
\
\
\
\


    text = text.lower()

    tokens: list[str] = []


    tokens.extend(re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text))

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.extend(chinese_chars)

    for index in range(len(chinese_chars) - 1):
        tokens.append(chinese_chars[index] + chinese_chars[index + 1])

    return tokens


def chunk_to_record(chunk: DocumentChunk) -> dict:
\
\
\
\


    return {
        "chunk_id": chunk.chunk_id,
        "file_id": chunk.file_id,
        "source_path": chunk.source_path,
        "file_name": chunk.file_name,
        "file_type": chunk.file_type,
        "file_hash": chunk.file_hash,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "metadata": chunk.metadata,
        "warnings": chunk.warnings,
    }


def load_lexical_records(index_path: str = DEFAULT_LEXICAL_INDEX_PATH) -> dict[str, dict]:
\
\
\
\
\
\
\


    path = Path(index_path)
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("chunks", {})


def save_lexical_records(
    records: dict[str, dict],
    index_path: str = DEFAULT_LEXICAL_INDEX_PATH,
) -> None:
\
\
\
\


    path = Path(index_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "index_version": 1,
        "chunk_count": len(records),
        "chunks": records,
    }

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def upsert_lexical_chunks(
    chunks: list[DocumentChunk],
    index_path: str = DEFAULT_LEXICAL_INDEX_PATH,
) -> None:
\
\
\
\
\


    records = load_lexical_records(index_path)

    for chunk in chunks:
        records[chunk.chunk_id] = chunk_to_record(chunk)

    save_lexical_records(records, index_path)


def delete_lexical_chunks(
    chunk_ids: list[str],
    index_path: str = DEFAULT_LEXICAL_INDEX_PATH,
) -> None:
\
\
\
\


    if not chunk_ids:
        return

    records = load_lexical_records(index_path)

    for chunk_id in chunk_ids:
        records.pop(chunk_id, None)

    save_lexical_records(records, index_path)


def bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    doc_freq: dict[str, int],
    total_docs: int,
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
\
\
\
\
\
\
\
\


    if not query_tokens or not doc_tokens:
        return 0.0

    doc_counter = Counter(doc_tokens)
    doc_len = len(doc_tokens)
    score = 0.0

    for token in query_tokens:
        tf = doc_counter.get(token, 0)
        if tf <= 0:
            continue

        df = doc_freq.get(token, 0)
        idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))

        denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += idf * (tf * (k1 + 1)) / denominator

    return score


def search_lexical(
    query: str,
    top_k: int = 20,
    index_path: str = DEFAULT_LEXICAL_INDEX_PATH,
) -> list[SearchHit]:
\
\
\
\


    records = load_lexical_records(index_path)
    if not records:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    tokenized_docs: dict[str, list[str]] = {
        chunk_id: tokenize(record.get("text", ""))
        for chunk_id, record in records.items()
    }

    total_docs = len(tokenized_docs)
    avg_doc_len = sum(len(tokens) for tokens in tokenized_docs.values()) / max(total_docs, 1)

    doc_freq: dict[str, int] = {}
    for tokens in tokenized_docs.values():
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1

    raw_hits: list[tuple[str, float]] = []

    for chunk_id, doc_tokens in tokenized_docs.items():
        score = bm25_score(
            query_tokens=query_tokens,
            doc_tokens=doc_tokens,
            doc_freq=doc_freq,
            total_docs=total_docs,
            avg_doc_len=avg_doc_len,
        )
        if score > 0:
            raw_hits.append((chunk_id, score))

    if not raw_hits:
        return []

    max_score = max(score for _, score in raw_hits)
    raw_hits.sort(key=lambda item: item[1], reverse=True)

    hits: list[SearchHit] = []

    for chunk_id, score in raw_hits[:top_k]:
        record = records[chunk_id]
        normalized_score = score / max_score if max_score > 0 else 0.0

        metadata = record.get("metadata", {}) or {}
        safe_metadata: dict[str, MetadataValue] = {
            key: value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool))
        }

        hits.append(
            SearchHit(
                chunk_id=record["chunk_id"],
                file_id=record["file_id"],
                source_path=record["source_path"],
                file_name=record["file_name"],
                file_type=record["file_type"],
                file_hash=record["file_hash"],
                chunk_index=int(record["chunk_index"]),
                score=normalized_score,
                text=record["text"],
                metadata=safe_metadata,
                warnings=record.get("warnings", []),
            )
        )

    return hits
