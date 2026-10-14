"""Smoke test: real Bedrock call via Strands SDK.

Proves the agentic core works against real AWS Bedrock before anything else.
No mocks. No fallbacks. Either it prints a haiku, or it fails loud.
"""
from __future__ import annotations

import os
import sys
import time

import boto3
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

REGION = os.environ.get("AWS_REGION", "us-east-1")
# Claude Haiku 4.5 via inference profile (cross-region)
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


@tool
def get_client_name(client_id: str) -> str:
    """Return a fake client name for the given client_id. Proves tool-use works."""
    return f"Client {client_id} = Henderson Family Trust"


def main() -> int:
    print(f"[smoke] region={REGION}")
    print(f"[smoke] model={MODEL_ID}")

    # Quick identity check
    sts = boto3.client("sts", region_name=REGION)
    identity = sts.get_caller_identity()
    print(f"[smoke] aws_account={identity['Account']} arn={identity['Arn']}")

    # Build the Strands agent
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    agent = Agent(
        model=model,
        tools=[get_client_name],
        system_prompt=(
            "You are a smoke test agent. When the user asks about a client by id, "
            "call get_client_name to resolve it, then respond with a single sentence."
        ),
    )

    t0 = time.perf_counter()
    result = agent("Who is client CLT-0042?")
    elapsed = time.perf_counter() - t0

    text = str(result)
    print(f"[smoke] elapsed={elapsed:.2f}s")
    print(f"[smoke] response={text[:400]}")

    # Success criteria: tool was called AND response mentions Henderson
    if "Henderson" not in text:
        print("[smoke] FAIL: expected 'Henderson' in response", file=sys.stderr)
        return 1

    print("[smoke] PASS: real Bedrock call + tool use works")
    return 0


if __name__ == "__main__":
    sys.exit(main())
