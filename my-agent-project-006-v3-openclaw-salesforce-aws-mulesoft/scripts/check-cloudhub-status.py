#!/usr/bin/env python3
"""Check CloudHub app status via Anypoint API."""
import json
import subprocess
import urllib.request

def ssm(name):
    r = subprocess.run(
        ["aws", "ssm", "get-parameter", "--region", "us-east-1",
         "--name", name, "--with-decryption",
         "--query", "Parameter.Value", "--output", "text"],
        capture_output=True, text=True
    )
    return r.stdout.strip()

org_id = ssm("/006-v3/mulesoft/org_id")
client_id = ssm("/006-v3/mulesoft/client-id")
client_secret = ssm("/006-v3/mulesoft/client-secret")

# Get token
req = urllib.request.Request(
    "https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token",
    data=json.dumps({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=10) as resp:
    token = json.load(resp)["access_token"]

# Get sandbox env
req2 = urllib.request.Request(
    f"https://anypoint.mulesoft.com/accounts/api/organizations/{org_id}/environments",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req2, timeout=10) as resp:
    envs = json.load(resp).get("data", [])
    env_id = next((e["id"] for e in envs if "sandbox" in e.get("name", "").lower()), None)

if not env_id:
    print("ERROR: No Sandbox environment found")
    exit(1)

print(f"Sandbox ENV_ID: {env_id}")

# List apps
req3 = urllib.request.Request(
    "https://anypoint.mulesoft.com/cloudhub/api/v2/applications",
    headers={
        "Authorization": f"Bearer {token}",
        "X-ANYPNT-ENV-ID": env_id,
    },
)
with urllib.request.urlopen(req3, timeout=15) as resp:
    apps = json.load(resp)

print(f"\nCloudHub apps ({len(apps)} total):")
for a in apps:
    d = a.get("domain", "?")
    s = a.get("status", "?")
    w = a.get("workers", {}).get("amount", "?")
    print(f"  {d}: status={s} workers={w}")

openclaw_apps = [a for a in apps if "openclaw" in a.get("domain", "") or "v3" in a.get("domain", "")]
if not openclaw_apps:
    print("\nNo openclaw/v3 apps found. They may still be provisioning.")
else:
    print(f"\nOpenClaw apps: {len(openclaw_apps)}")
    all_started = all(a.get("status") == "STARTED" for a in openclaw_apps)
    print(f"All STARTED: {'✅ YES' if all_started else '❌ NO'}")
