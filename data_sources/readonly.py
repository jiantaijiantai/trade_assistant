from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "outputs" / "rag" / "business_index_manifest.json"
DEFAULT_LEXICAL_INDEX_PATH = PROJECT_ROOT / "outputs" / "rag" / "business_lexical_index.json"


def list_readonly_sources() -> dict[str, Any]:
    manifest = _read_json(DEFAULT_MANIFEST_PATH)
    lexical_index = _read_json(DEFAULT_LEXICAL_INDEX_PATH)
    return {
        "mode": "readonly",
        "sources": _manifest_sources(manifest),
        "lexical_index_available": bool(lexical_index),
        "boundaries": [
            "Only reads local indexed business metadata and lexical snippets.",
            "Does not write ERP, OA, finance, approval, invoice, or external systems.",
            "Does not bypass RAG ACL checks used by chat retrieval.",
        ],
    }


def search_readonly_sources(query: str, limit: int = 5) -> dict[str, Any]:
    index = _read_json(DEFAULT_LEXICAL_INDEX_PATH)
    documents = _extract_documents(index)
    query_text = query.strip().lower()
    matches = []

    for document in documents:
        haystack = json.dumps(document, ensure_ascii=False).lower()
        if not query_text or query_text in haystack:
            matches.append(document)
        if len(matches) >= limit:
            break

    return {
        "mode": "readonly",
        "query": query,
        "limit": limit,
        "matches": matches,
        "count": len(matches),
    }


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_sources(manifest: Any) -> list[dict[str, Any]]:
    if not manifest:
        return []
    if isinstance(manifest, dict):
        items = manifest.get("documents") or manifest.get("files") or manifest.get("sources") or []
    elif isinstance(manifest, list):
        items = manifest
    else:
        items = []

    sources = []
    for item in items:
        if isinstance(item, dict):
            sources.append(
                {
                    "source_path": item.get("source_path") or item.get("path") or item.get("file_path"),
                    "file_name": item.get("file_name") or item.get("name"),
                    "tenant_id": item.get("tenant_id"),
                    "department_id": item.get("department_id"),
                    "sensitivity_level": item.get("sensitivity_level"),
                }
            )
    return sources


def _extract_documents(index: Any) -> list[dict[str, Any]]:
    if not index:
        return []
    if isinstance(index, list):
        return [item for item in index if isinstance(item, dict)]
    if isinstance(index, dict):
        for key in ("documents", "chunks", "items"):
            value = index.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []
