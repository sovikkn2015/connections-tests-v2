"""Dense retrieval via Bedrock Titan v2 embeddings.

Real deployment calls Titan Embed Text v2 via the bedrock-runtime service.
Tests use `StubEmbedder` (deterministic hash-based embeddings) so no AWS
credentials are needed.

Cosine similarity between query and document embeddings, top-k returned.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import List, Optional, Protocol, Sequence, Tuple


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        ...

    @property
    def dim(self) -> int:
        ...


class StubEmbedder:
    """Deterministic hash-based embeddings. Used in tests + offline dev."""

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> List[float]:
        """Hash-stream derived embedding. Values in [-1, 1]."""
        norm = (text or "").lower()
        ngrams = [norm[i : i + 3] for i in range(max(1, len(norm) - 2))]
        if not ngrams:
            ngrams = [norm]
        buf = bytearray()
        for gram in ngrams:
            buf.extend(hashlib.sha256(gram.encode()).digest())
        while len(buf) < self._dim * 4:
            buf.extend(hashlib.sha256(bytes(buf) or b"seed").digest())

        vec: List[float] = []
        for i in range(self._dim):
            chunk = bytes(buf[i * 4 : i * 4 + 4])
            raw = int.from_bytes(chunk, "big", signed=False)
            vec.append(((raw / 2**32) * 2.0) - 1.0)

        mag = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / mag for v in vec]


class BedrockTitanEmbedder:  # pragma: no cover - real-transport
    """Titan Embed Text v2 via boto3 bedrock-runtime. Loaded lazily."""

    def __init__(
        self,
        *,
        region: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> None:
        self._region = region or os.getenv("AWS_REGION_BEDROCK", "us-east-1")
        self._model_id = model_id or os.getenv(
            "BEDROCK_TITAN_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"
        )
        self._client = None

    @property
    def dim(self) -> int:
        return 1024

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        import asyncio
        import json

        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "boto3 required for BedrockTitanEmbedder; install boto3"
            ) from exc

        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self._region)

        loop = asyncio.get_running_loop()

        def _sync_invoke(body: str) -> dict:
            resp = self._client.invoke_model(  # type: ignore[union-attr]
                modelId=self._model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(resp["body"].read())

        vectors: List[List[float]] = []
        for t in texts:
            body = json.dumps({"inputText": t})
            payload = await loop.run_in_executor(None, _sync_invoke, body)
            vectors.append(list(payload.get("embedding", [])))
        return vectors


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class DenseRetriever:
    """Corpus + embedder + cosine-top-k. Precomputes doc embeddings on build."""

    def __init__(
        self, documents: Sequence[str], embedder: Optional[Embedder] = None
    ) -> None:
        self.documents = list(documents)
        self.embedder: Embedder = embedder or StubEmbedder()
        self._doc_vecs: Optional[List[List[float]]] = None

    async def _ensure_embedded(self) -> None:
        if self._doc_vecs is None:
            self._doc_vecs = await self.embedder.embed(self.documents)

    async def top_k(self, query: str, k: int = 30) -> List[Tuple[int, float]]:
        await self._ensure_embedded()
        assert self._doc_vecs is not None
        q_vecs = await self.embedder.embed([query])
        qv = q_vecs[0] if q_vecs else []
        scored = [(i, _cosine(qv, dv)) for i, dv in enumerate(self._doc_vecs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
