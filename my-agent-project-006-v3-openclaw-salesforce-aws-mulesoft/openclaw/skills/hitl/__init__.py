"""hitl skill — HMAC-SHA256 approval tokens, 5-min TTL, plan-bound, single-use."""

from .actions import (
    ApprovalMintInput,
    ApprovalMintOutput,
    ApprovalVerifyInput,
    ApprovalVerifyOutput,
    HITLError,
    mint,
    verify,
    run,
)
from ._tokens import TokenStore, get_default_store, compute_plan_hash

__all__ = [
    "ApprovalMintInput",
    "ApprovalMintOutput",
    "ApprovalVerifyInput",
    "ApprovalVerifyOutput",
    "HITLError",
    "TokenStore",
    "get_default_store",
    "compute_plan_hash",
    "mint",
    "verify",
    "run",
]
