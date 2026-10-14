"""Shim that re-exports the Titan v2 embedder from filings-corpus.

Kept separate so each Lambda package deploys cleanly in CDK without cross
referencing. If CDK decides to share a Lambda layer, this file is replaced
by a layer import. For now, we duplicate to keep deploy units simple.
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

_brt = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _invoke_one(text: str, *, dimensions: int = DEFAULT_DIM, normalize: bool = True) -> list[float]:
    body = json.dumps({"inputText": text, "dimensions": dimensions, "normalize": normalize})
    try:
        resp = _brt.invoke_model(
            modelId=os.environ.get("EMBED_MODEL_ID", DEFAULT_MODEL),
            body=body,
            contentType="application/json",
            accept="application/json",
        )
    except ClientError as exc:
        raise RuntimeError(f"Titan v2 invoke failed: {exc.response.get('Error', {}).get('Code')}") from exc
    return json.loads(resp["body"].read())["embedding"]


def embed_batch(texts: list[str], *, dimensions: int = DEFAULT_DIM) -> list[list[float]]:
    if not texts:
        return []
    out: list[list[float]] = []
    for t in texts:
        if not t or not t.strip():
            out.append([0.0] * dimensions)
            continue
        out.append(_invoke_one(t, dimensions=dimensions))
    return out
