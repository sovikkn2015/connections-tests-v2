#!/usr/bin/env python3
"""Out-of-band bootstrap for the Bedrock KB OpenSearch Serverless collection + index.

The CDK stack has an inherent race: the DataAccessPolicy needs 3-5 min to
propagate after CREATE_COMPLETE, which exceeds CloudFormation custom
resource tolerance. Solution: create the OSS collection and index here,
idempotently, before the CDK stack runs.

Reads AWS creds from the current shell session (boto3 default chain).
Zero secrets printed or written to disk.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import boto3
import requests  # type: ignore[import-untyped]
from botocore.exceptions import ClientError
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection  # type: ignore[import-untyped]


REGION = "us-east-1"
COLLECTION = "openclaw-v3-kb"
INDEX = f"{COLLECTION}-index"
KB_ROLE_NAME = "openclaw-v3-kb-service-role"  # will be created by CDK, referenced here
ACCOUNT_ID = "875460787302"


def ensure_security_policies(aoss: Any) -> None:
    print("==> Ensuring encryption + network security policies")
    try:
        aoss.create_security_policy(
            name=f"{COLLECTION}-enc",
            type="encryption",
            policy=json.dumps({
                "Rules": [{"Resource": [f"collection/{COLLECTION}"], "ResourceType": "collection"}],
                "AWSOwnedKey": True,
            }),
        )
        print("    encryption policy created")
    except ClientError as e:
        if "ConflictException" in str(e):
            print("    encryption policy already exists")
        else:
            raise

    try:
        aoss.create_security_policy(
            name=f"{COLLECTION}-net",
            type="network",
            policy=json.dumps([{
                "Rules": [
                    {"Resource": [f"collection/{COLLECTION}"], "ResourceType": "collection"},
                    {"Resource": [f"collection/{COLLECTION}"], "ResourceType": "dashboard"},
                ],
                "AllowFromPublic": True,
            }]),
        )
        print("    network policy created")
    except ClientError as e:
        if "ConflictException" in str(e):
            print("    network policy already exists")
        else:
            raise


def ensure_collection(aoss: Any) -> str:
    print("==> Ensuring collection")
    try:
        r = aoss.create_collection(name=COLLECTION, type="VECTORSEARCH")
        coll_id = r["createCollectionDetail"]["id"]
        print(f"    create initiated, id={coll_id}")
    except ClientError as e:
        if "ConflictException" in str(e):
            colls = aoss.list_collections(collectionFilters={"name": COLLECTION})["collectionSummaries"]
            if not colls:
                raise RuntimeError("ConflictException but list returned empty")
            coll_id = colls[0]["id"]
            print(f"    already exists, id={coll_id}")
        else:
            raise

    # Wait for ACTIVE
    for attempt in range(60):
        details = aoss.batch_get_collection(ids=[coll_id])["collectionDetails"][0]
        status = details["status"]
        if status == "ACTIVE":
            endpoint = details["collectionEndpoint"]
            print(f"    ACTIVE endpoint={endpoint}")
            return endpoint
        if status == "FAILED":
            raise RuntimeError(f"collection {coll_id} FAILED")
        print(f"    attempt {attempt}: {status}")
        time.sleep(10)
    raise RuntimeError("collection did not become ACTIVE in time")


def ensure_data_access_policy(aoss: Any, caller_arn: str, kb_role_arn: str) -> None:
    """Give both the KB service role AND the current caller aoss:* on this collection."""
    print("==> Ensuring data access policy")
    principals = [caller_arn, kb_role_arn]
    policy_doc = json.dumps([{
        "Rules": [
            {
                "Resource": [f"index/{COLLECTION}/*"],
                "Permission": ["aoss:*"],
                "ResourceType": "index",
            },
            {
                "Resource": [f"collection/{COLLECTION}"],
                "Permission": ["aoss:*"],
                "ResourceType": "collection",
            },
        ],
        "Principal": principals,
    }])
    try:
        aoss.create_access_policy(name=f"{COLLECTION}-data", type="data", policy=policy_doc)
        print("    access policy created")
    except ClientError as e:
        if "ConflictException" in str(e):
            try:
                aoss.update_access_policy(
                    name=f"{COLLECTION}-data",
                    type="data",
                    policy=policy_doc,
                    policyVersion=aoss.get_access_policy(name=f"{COLLECTION}-data", type="data")["accessPolicyDetail"]["policyVersion"],
                )
                print("    access policy updated")
            except ClientError as e2:
                if "No changes detected" in str(e2):
                    print("    access policy already matches (no changes)")
                else:
                    raise
        else:
            raise


def ensure_index(endpoint: str) -> None:
    """Create the vector index idempotently via signed HTTPS PUT."""
    print("==> Ensuring index")
    print(f"    sleeping 120s for access-policy propagation")
    time.sleep(120)

    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, "aoss")
    host = endpoint.replace("https://", "")
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )

    mapping = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "engine": "faiss",
                        "name": "hnsw",
                        "space_type": "l2",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                "text": {"type": "text"},
                "metadata": {"type": "text", "index": False},
            }
        },
    }

    for attempt in range(30):
        try:
            r = client.indices.create(index=INDEX, body=mapping)
            print(f"    created: {r}")
            time.sleep(30)  # AOSS index visibility settle
            return
        except Exception as e:  # noqa: BLE001
            if "resource_already_exists_exception" in str(e):
                print("    already exists (idempotent ok)")
                return
            print(f"    attempt {attempt}: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(10)
    raise RuntimeError("index create failed after retries")


def main() -> None:
    session = boto3.Session()
    sts = session.client("sts", region_name=REGION)
    caller_arn = sts.get_caller_identity()["Arn"]
    # Remove /username suffix from assumed-role ARNs to match AOSS principal format
    if ":assumed-role/" in caller_arn:
        role_name = caller_arn.split("/")[-2]
        caller_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"
    print(f"Caller ARN for access policy: {caller_arn}")

    kb_role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{KB_ROLE_NAME}"
    print(f"Expected KB service role: {kb_role_arn}")

    aoss = session.client("opensearchserverless", region_name=REGION)
    ensure_security_policies(aoss)
    endpoint = ensure_collection(aoss)
    ensure_data_access_policy(aoss, caller_arn, kb_role_arn)
    ensure_index(endpoint)

    print("")
    print("==> DONE")
    print(f"    COLLECTION_NAME={COLLECTION}")
    print(f"    COLLECTION_ENDPOINT={endpoint}")
    print(f"    INDEX_NAME={INDEX}")
    print(f"    COLLECTION_ARN=arn:aws:aoss:{REGION}:{ACCOUNT_ID}:collection/{endpoint.split('.')[0].replace('https://','')}")


if __name__ == "__main__":
    main()
