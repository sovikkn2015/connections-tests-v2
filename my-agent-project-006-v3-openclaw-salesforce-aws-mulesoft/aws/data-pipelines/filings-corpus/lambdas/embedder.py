"""Titan v2 embedder.

Thin batched wrapper around bedrock-runtime `InvokeModel` for the
`amazon.titan-embed-text-v2:0` model. The model:
  - embedding dim: 1024 (we default)
  - input token cap: 512
  - supports normalized output (cosine-ready)

This is used by BOTH pipelines (filings and research) so it lives in a
shared path. We keep it inside filings-corpus/ for colocation; the research
pipeline imports it via relative path at deploy time.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

DEFAULT_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_DIM = 1024
BATCH_SIZE = 25  # Titan v2 supports up to 25 inputs per InvokeModel

_brt = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _invoke_one(text: str, *, dimensions: int = DEFAULT_DIM, normalize: bool = True) -> list[float]:
    body = json.dumps(
        {"inputText": text, "dimensions": dimensions, "normalize": normalize}
    )
    try:
        resp = _brt.invoke_model(
            modelId=os.environ.get("EMBED_MODEL_ID", DEFAULT_MODEL),
            body=body,
            contentType="application/json",
            accept="application/json",
        )
    except ClientError as exc:
        raise RuntimeError(f"Titan v2 invoke failed: {exc.response.get('Error', {}).get('Code')}") from exc
    out = json.loads(resp["body"].read())
    return out["embedding"]


def embed_batch(texts: list[str], *, dimensions: int = DEFAULT_DIM) -> list[list[float]]:
    """Embed N strings; returns N vectors in the same order. Degrades to per-item on error."""
    if not texts:
        return []
    out: list[list[float]] = []
    for i, text in enumerate(texts):
        if not text or not text.strip():
            out.append([0.0] * dimensions)
            continue
        out.append(_invoke_one(text, dimensions=dimensions))
        if (i + 1) % BATCH_SIZE == 0:
            logger.info("embedded %d / %d", i + 1, len(texts))
    return out
