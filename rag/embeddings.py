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
\
\


import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_NATIVE_BASE_URL,
    EMBEDDING_MODEL,
)


@dataclass
class EmbeddingConfig:
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


    provider: str
    model: str
    dim: int
    api_key: str
    base_url: str


def load_embedding_config() -> EmbeddingConfig:
\
\
\
\
\
\
\


    api_key = (os.getenv("EMBEDDING_API_KEY") or DASHSCOPE_API_KEY or "").strip()
    base_url = (os.getenv("EMBEDDING_BASE_URL") or DASHSCOPE_BASE_URL or "").strip()
    model = (os.getenv("EMBEDDING_MODEL") or EMBEDDING_MODEL or "").strip()

    default_provider = "openai_compatible" if api_key else "local_hash"

    return EmbeddingConfig(
        provider=os.getenv("EMBEDDING_PROVIDER", default_provider).strip(),
        model=model or "local-hash-512",
        dim=int(os.getenv("EMBEDDING_DIM", "512")),
        api_key=api_key,
        base_url=base_url,
    )


def embed_texts(
    texts: list[str],
    config: EmbeddingConfig | None = None,
    batch_size: int = 16,
) -> list[list[float]]:
\
\
\
\
\


    config = config or load_embedding_config()

    if not texts:
        return []

    if config.provider == "local_hash":
        return [local_hash_embedding(text, dim=config.dim) for text in texts]

    if config.provider == "openai_compatible":
        if config.model == "qwen2.5-vl-embedding":
            return dashscope_multimodal_embeddings(texts, config, batch_size=batch_size)

        vectors: list[list[float]] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(openai_compatible_embeddings(batch, config))

        return vectors

    raise ValueError(f"不支持的 EMBEDDING_PROVIDER：{config.provider}")


def openai_compatible_embeddings(
    texts: list[str],
    config: EmbeddingConfig,
) -> list[list[float]]:
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


    if not config.api_key:
        raise ValueError("Embedding API key 未配置")

    if not config.base_url:
        raise ValueError("Embedding base_url 未配置")

    url = config.base_url.rstrip("/") + "/embeddings"

    body = json.dumps(
        {
            "model": config.model,
            "input": texts,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))

    data = sorted(payload["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def dashscope_multimodal_embeddings(
    texts: list[str],
    config: EmbeddingConfig,
    batch_size: int = 1,
) -> list[list[float]]:
\
\
\
\
\
\


    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(_dashscope_multimodal_embedding_batch(batch, config))
    return vectors


def _dashscope_multimodal_embedding_batch(
    texts: list[str],
    config: EmbeddingConfig,
) -> list[list[float]]:


    if not config.api_key:
        raise ValueError("Embedding API key 未配置")

    base_url = (os.getenv("DASHSCOPE_NATIVE_BASE_URL") or DASHSCOPE_NATIVE_BASE_URL).rstrip("/")
    url = base_url + "/services/embeddings/multimodal-embedding/multimodal-embedding"

    body = json.dumps(
        {
            "model": config.model,
            "input": {
                "contents": [{"text": text} for text in texts],
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope 多模态 embedding 请求失败：{exc.code} {error_body}") from exc

    embeddings = payload.get("output", {}).get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"DashScope 多模态 embedding 返回为空：{payload}")

    ordered = sorted(embeddings, key=lambda item: int(item.get("index", 0)))
    return [item["embedding"] for item in ordered]


def local_hash_embedding(text: str, dim: int = 512) -> list[float]:
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


    text = text.strip().lower()
    vector = [0.0] * dim

    if not text:
        return vector

    features: list[str] = []

    for n in (2, 3):
        features.extend(text[i : i + n] for i in range(max(len(text) - n + 1, 0)))

    if not features:
        features = [text]

    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dim
        vector[index] += 1.0

    return l2_normalize(vector)


def l2_normalize(vector: list[float]) -> list[float]:


    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector

    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
\
\
\
\
\


    if not left or not right or len(left) != len(right):
        return 0.0

    return sum(a * b for a, b in zip(left, right))
