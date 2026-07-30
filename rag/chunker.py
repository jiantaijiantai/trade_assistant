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


import hashlib
import re
import uuid
from pathlib import Path

from rag.schemas import DocumentChunk, ParsedDocument




RAG_NAMESPACE = uuid.UUID("7f5d8a5b-5e2d-4d5f-9f2b-6b9c9e5f7d31")


def normalize_text(text: str) -> str:
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


    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_hash(text: str) -> str:


    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_file_id(source_path: str, file_hash: str) -> str:
\
\
\
\
\
\
\


    stable_path = str(Path(source_path).as_posix()).lower()
    return str(uuid.uuid5(RAG_NAMESPACE, f"{stable_path}:{file_hash}"))


def build_chunk_id(file_id: str, chunk_index: int, chunk_text: str) -> str:
\
\
\
\
\


    stable_key = f"{file_id}:{chunk_index}:{text_hash(chunk_text)}"
    return str(uuid.uuid5(RAG_NAMESPACE, stable_key))


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
\
\
\
\
\
\
\
\


    text = normalize_text(text)
    if not text:
        return []

    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def chunk_document(
    document: ParsedDocument,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[DocumentChunk]:
\
\
\
\
\


    file_id = build_file_id(document.source_path, document.file_hash)
    chunks = chunk_text(document.text, chunk_size=chunk_size, overlap=overlap)

    return [
        DocumentChunk(
            chunk_id=build_chunk_id(file_id, index, text),
            file_id=file_id,
            source_path=document.source_path,
            file_name=document.file_name,
            file_type=document.file_type,
            file_hash=document.file_hash,
            chunk_index=index,
            text=text,
            metadata={**document.metadata, "chunk_index": index},
            warnings=document.warnings,
        )
        for index, text in enumerate(chunks)
    ]
