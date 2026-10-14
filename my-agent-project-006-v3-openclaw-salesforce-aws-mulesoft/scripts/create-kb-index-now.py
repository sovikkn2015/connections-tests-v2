#!/usr/bin/env python3
"""Out-of-band index creation for a LIVE CDK-created collection.

The CDK KbIndexCreatorFn Lambda is in a 90s sleep + retry loop. If we
create the index ourselves here, the Lambda's first PUT on wake will
return `resource_already_exists_exception` and idempotent-succeed.

Run this while the CDK stack is at CreateKbIndex/Resource/Default.
"""

from __future__ import annotations

import json
import sys
import time

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection  # type: ignore[import-untyped]


REGION = "us-east-1"
COLLECTION = "openclaw-v3-kb"
INDEX = f"{COLLECTION}-index"


def main():
    aoss = boto3.client("opensearchserverless", region_name=REGION)
    colls = aoss.list_collections(collectionFilters={"name": COLLECTION})["collectionSummaries"]
    if not colls:
        print("no collection found")
        sys.exit(1)
    coll_id = colls[0]["id"]
    details = aoss.batch_get_collection(ids=[coll_id])["collectionDetails"][0]
    endpoint = details["collectionEndpoint"]
    print(f"collection id={coll_id} endpoint={endpoint}")

    # Ensure the current caller is in the data access policy (CDK made the
    # policy for the two Lambda roles only; I need to be in it too)
    caller_arn = boto3.client("sts").get_caller_identity()["Arn"]
    if ":user/" in caller_arn:
        principal = caller_arn
    elif ":assumed-role/" in caller_arn:
        parts = caller_arn.split("/")
        principal = f"arn:aws:iam::875460787302:role/{parts[-2]}"
    else:
        principal = caller_arn
    print(f"caller principal to add: {principal}")

    pol = aoss.get_access_policy(name=f"{COLLECTION}-data", type="data")
    policy_ver = pol["accessPolicyDetail"]["policyVersion"]
    policy_doc_raw = pol["accessPolicyDetail"]["policy"]
    doc = policy_doc_raw if isinstance(policy_doc_raw, list) else json.loads(policy_doc_raw)
    # doc is a list with one rule block
    rule = doc[0]
    if principal not in rule.get("Principal", []):
        rule["Principal"].append(principal)
        aoss.update_access_policy(
            name=f"{COLLECTION}-data",
            type="data",
            policy=json.dumps(doc),
            policyVersion=policy_ver,
        )
        print(f"added caller to access policy. Sleeping 60s for propagation.")
        time.sleep(60)
    else:
        print("caller already in access policy")

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
            print(f"CREATED: {r}")
            return
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "resource_already_exists_exception" in msg:
                print("already exists (idempotent ok)")
                return
            print(f"attempt {attempt}: {type(e).__name__}: {msg[:200]}")
            time.sleep(10)
    raise RuntimeError("index create failed")


if __name__ == "__main__":
    main()
