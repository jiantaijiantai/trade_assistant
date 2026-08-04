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


from pathlib import Path
from typing import Any

import chromadb

from rag.access_control import BUSINESS_COLLECTION_NAME
from rag.schemas import DocumentChunk, MetadataValue, SearchHit


DEFAULT_CHROMA_DIR = "outputs/rag/chroma"
DEFAULT_COLLECTION_NAME = BUSINESS_COLLECTION_NAME


def get_chroma_collection(
    persist_dir: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
):
\
\
\
\
\


    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=persist_dir)

    return client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "trade_assistant business document chunks"},
    )


def chunk_to_metadata(chunk: DocumentChunk) -> dict[str, MetadataValue]:
\
\
\
\
\


    metadata: dict[str, MetadataValue] = {
        "file_id": chunk.file_id,
        "source_path": chunk.source_path,
        "file_name": chunk.file_name,
        "file_type": chunk.file_type,
        "file_hash": chunk.file_hash,
        "chunk_index": chunk.chunk_index,
        "warnings": " | ".join(chunk.warnings),
    }

    for key, value in chunk.metadata.items():
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value

    return metadata


def upsert_vectors(
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
    persist_dir: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> None:
\
\
\
\
\
\
\
\


    if not chunks:
        return

    if len(chunks) != len(embeddings):
        raise ValueError("chunks 和 embeddings 数量不一致")

    collection = get_chroma_collection(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    collection.upsert(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=embeddings,
        metadatas=[chunk_to_metadata(chunk) for chunk in chunks],
    )


def delete_vectors(
    chunk_ids: list[str],
    persist_dir: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> None:
\
\
\
\
\
\


    if not chunk_ids:
        return

    collection = get_chroma_collection(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )
    collection.delete(ids=chunk_ids)


def chroma_results_to_hits(results: dict[str, Any]) -> list[SearchHit]:
\
\
\
\
\


    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    hits: list[SearchHit] = []

    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}
        score = 1.0 / (1.0 + float(distance))

        warnings_text = str(metadata.get("warnings", "") or "")
        warnings = [item for item in warnings_text.split(" | ") if item]

        hits.append(
            SearchHit(
                chunk_id=str(chunk_id),
                file_id=str(metadata.get("file_id", "")),
                source_path=str(metadata.get("source_path", "")),
                file_name=str(metadata.get("file_name", "")),
                file_type=str(metadata.get("file_type", "")),
                file_hash=str(metadata.get("file_hash", "")),
                chunk_index=int(metadata.get("chunk_index", 0)),
                score=score,
                text=text or "",
                metadata={
                    key: value
                    for key, value in metadata.items()
                    if key
                    not in {
                        "file_id",
                        "source_path",
                        "file_name",
                        "file_type",
                        "file_hash",
                        "chunk_index",
                        "warnings",
                    }
                },
                warnings=warnings,
            )
        )

    return hits


def query_vectors(
    query_embedding: list[float],
    top_k: int = 20,
    persist_dir: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    where: dict[str, Any] | None = None,
) -> list[SearchHit]:
\
\
\
\
\


    collection = get_chroma_collection(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    query_args: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where is not None:
        query_args["where"] = where

    results = collection.query(**query_args)

    return chroma_results_to_hits(results)
