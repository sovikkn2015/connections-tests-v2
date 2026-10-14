# v3 MuleSoft Deploy — Gotchas & Fixes

This document captures the three non-obvious Mule 4.9 CloudHub 2.0 failure
modes we hit during initial deployment, what caused them, and how to avoid
them. A new engineer following the runbook who runs into "apps won't boot"
should read this first.

All three apps (`submit-order`, `initiate-wire`, `order-status-webhook`)
now deploy cleanly with the fixes in place. These notes exist so that when
you refactor or add a new app, you don't rediscover the same bugs.

## Gotcha 1 — `mule-artifact.json` must be at the project root AND list exported resources

**Symptom:** App deploys to CloudHub, logs show
```
[submit-order.xml:35]: Invalid configuration found for parameter 'file': config.yaml
[submit-order.xml:151]: Error loading referenced file for parameter 'resource':
    transforms/alpaca-request.dwl: java.io.FileNotFoundException (No such file or directory)
```
App enters CrashLoopBackOff. Files are physically in the jar
(verify with `unzip -l target/*.jar`) but Mule can't see them at runtime.

**Cause:** Mule 4.9 uses a pre-serialized Application Syntax Tree (AST) built
at package time. If `mule-artifact.json` has `exportedResources: []`, the
AST has no reference path to `config.yaml` or `transforms/*.dwl` — even
though the files ship in the jar.

**Fix:** In `mule-artifact.json` at the project root, explicitly list every
resource the XML references via `file=` or `resource=` attributes:

```json
{
  "minMuleVersion": "4.9.0",
  "name": "<app>-process-api",
  "configs": ["<app>.xml"],
  "redeploymentEnabled": true,
  "secureProperties": ["list every key set as secure in Runtime Manager"],
  "requiredProduct": "MULE_EE",
  "supportedJavaVersions": ["17"],
  "classLoaderModelLoaderDescriptor": {
    "id": "mule",
    "attributes": {
      "exportedResources": [
        "config.yaml",
        "transforms/alpaca-request.dwl",
        "transforms/alpaca-response.dwl",
        "api/<app>.raml"
      ]
    }
  }
}
```

**How to verify:** After `mvn clean package`, run:

```
unzip -p target/*-mule-application.jar META-INF/mule-artifact/mule-artifact.json | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d['classLoaderModelLoaderDescriptor']['attributes']['exportedResources'])"
```

You should see your full list. If you see `[]`, the descriptor at
project root is missing or malformed.

**Reference:**
- [MuleSoft Package a Mule Application](https://docs.mulesoft.com/mule-runtime/latest/package-a-mule-application)
- [Mule 4.9.0 Release Notes — pre-serialized AST](https://docs.mulesoft.com/release-notes/mule-runtime/mule-4.9.0-release-notes)

## Gotcha 2 — Only strings are valid in `<configuration-properties>` YAML

**Symptom:** App on 3.0.x crashes at boot with no obvious error. Flow never
binds to port 8081. Readiness probe fails.

**Cause:** Mule 4.9's YAML configuration-properties loader accepts **string
values only**. Integer, boolean, or empty-string values cause init failure.

Example of what we had in `initiate-wire/src/main/resources/config.yaml`
that broke:

```yaml
# WRONG — integer value
wire.dual_auth_threshold_usd: 100000

# WRONG — empty string with no quotes (YAML parser treats as null)
dwolla.endpoint_path:
```

**Fix:** Quote every value, even numbers, even paths, even empty strings:

```yaml
# CORRECT
wire.dual_auth_threshold_usd: "100000"
dwolla.endpoint_path: "/"   # use explicit path, not empty
```

**How to verify:** `python3 -c "import yaml; [type(v).__name__ for v in yaml.safe_load(open('src/main/resources/config.yaml')).values() if not isinstance(v, str)]"` — should return `[]`. Any non-empty list means a non-string value.

**Reference:** [MuleSoft Configuring Properties docs](https://docs.mulesoft.com/mule-runtime/latest/configuring-properties) —
"Supported Files: The Configuration Properties support both YAML
configuration files (.yaml) and Properties configuration files
(.properties). String is the only supported type in both file formats."

## Gotcha 3 — Eager `<http:request-config>` host resolution at boot

**Symptom:** App passes XML validation and boots Mule, but replica stays
in STARTING state. Kubernetes readiness probe keeps failing with
`curl exit 7` (connection refused). After ~3 minutes the pod is killed
and restarted. CrashLoopBackOff.

**Cause:** Mule 4.9's `<http:request-config>` resolves `host="${placeholder}"`
at the **Initialise phase** (before any flow runs). If the placeholder
value isn't a valid DNS name, the HTTP client pool builder blocks on
`UnknownHostException`, which delays the `Start` phase completion. Port
8081 never binds. Kubernetes gives up.

This bit us in `order-status-webhook/src/main/resources/config.yaml`:

```yaml
# WRONG — not a valid hostname, DNS resolution hangs
mcp.endpoint_host: "REPLACE_WITH_API_GATEWAY_HOST_AT_DEPLOY"
```

We were relying on the Runtime Manager application property to override
this at deploy time. It does override — but only AFTER Mule has parsed the
config and initialized the HTTP connection pools. By then the boot hang
has already failed the readiness probe.

**Fix:** Default to a resolvable-but-benign hostname in `config.yaml`. The
Runtime Manager override will win at runtime:

```yaml
# CORRECT
mcp.endpoint_host: "localhost"
```

Then set the real host in Runtime Manager properties:
`mcp.endpoint_host = <your-api-gw>.execute-api.us-east-1.amazonaws.com`

**How to verify:** Before deploying, run `dig <host>` on every
`${*.host}` placeholder value in `config.yaml`. Every one must resolve.

## Gotcha 4 — Nonexistent DataWeave functions

**Symptom:** Same as Gotcha 3 — STARTING, readiness probe fails.

**Cause:** `dw::core::Binaries::toHex(...)` does not exist in Mule 4.x
DataWeave. We found this reference in the webhook XML when migrating
from v2 (where it may have been custom). Mule's AST build doesn't fully
resolve DataWeave function references at package time; the failure
only surfaces at `<ee:transform>` evaluation during flow execution — but
it causes a long startup stall (not an immediate crash).

**Fix:** Use the built-in Binary → hex coercion:

```dwl
// WRONG
dw::core::Binaries::toHex(someBinary)

// RIGHT
someBinary as String {base: "16"}
```

For SHA1/HMACBinary output, you can chain directly:

```dwl
lower(
  dw::Crypto::HMACBinary(key, data, "HmacSHA256")
    as String {base: "16"}
)
```

**How to verify:** `grep -rn "Binaries::toHex\|Binaries::toBinary\|Binaries::toBase16" mulesoft/process-apis/*/src/main/mule/` — must return no results. Any match is a bug.

**Reference:** [DataWeave Binaries module](https://docs.mulesoft.com/dataweave/latest/dw-binaries) — only `fromBase64` and `toBase64` exist.

## Prevention — the `make verify-mule` target

To catch all four classes of issues before a deploy cycle burns time on
CloudHub, the project Makefile includes a `verify-mule` target:

```
make verify-mule
```

This runs all four checks:
1. Every `mule-artifact.json` has a non-empty `exportedResources` list.
2. Every `config.yaml` value is a quoted string.
3. Every `${*.host}` placeholder in `config.yaml` resolves via DNS.
4. No DataWeave references the nonexistent `Binaries::toHex` function.

Run this target before every `make mule-package` or `mvn mule:deploy`.

## Summary of what changed to reach the working state

| File | Change |
|---|---|
| `mulesoft/process-apis/*/mule-artifact.json` | Added `exportedResources` list with every referenced resource |
| `mulesoft/process-apis/*/mule-artifact.json` | Added `supportedJavaVersions: ["17"]` |
| `mulesoft/process-apis/*/pom.xml` | Added `<javaVersion>17</javaVersion>` in cloudhub2Deployment |
| `mulesoft/process-apis/initiate-wire/src/main/resources/config.yaml` | Quoted integer value `"100000"` |
| `mulesoft/process-apis/initiate-wire/src/main/resources/config.yaml` | Changed empty `""` path to `"/"` |
| `mulesoft/process-apis/order-status-webhook/src/main/resources/config.yaml` | Changed placeholder host to `"localhost"` |
| `mulesoft/process-apis/order-status-webhook/src/main/mule/order-status-webhook.xml` | Removed `dw::core::Binaries::toHex(...)` wrapper |

## Reference — working state versions

When these gotchas were fixed:
- submit-order 3.0.5 → RUNNING, `/api/health` returns `mode: alpaca-paper`
- initiate-wire 3.0.6 → RUNNING, `/api/health` returns `mode: dwolla-sandbox`
- order-status-webhook 3.0.10 → RUNNING, `/api/health` returns `mode: live`

First real Alpaca paper order submitted end-to-end through Mule:
`ALPACA-c98c9f6a-b807-47b6-b652-8269def870a2` (status `pending_new`).
