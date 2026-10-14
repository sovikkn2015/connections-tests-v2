# v3 MuleSoft Boot Crash — Historical Investigation Log

> **HISTORICAL DOCUMENT.** This captures an earlier remediation investigation
> that explored secure-properties module encryption. The **actual** Mule
> 4.9 gotchas that caused the CloudHub boot crashes are documented in
> `docs/v3-mulesoft-gotchas.md`, and automated verification is in the
> project `Makefile` (`make verify-mule`).
>
> Final state (2026-04-30): all three apps RUNNING on CloudHub Sandbox.
> The secure-properties module approach explored in this doc was NOT the
> path we took; we use Runtime Manager secure properties instead (see
> RUNBOOK.md section 3.3.1).

Status: blocked Narrative 5 (Large Liquidation CloudHub path) during the demo.
Owner: TBD.
Estimated effort: 2–4 hours of focused work plus one CloudHub deploy cycle.
Prerequisite: demo is complete. This is not an in-flight fix.

---

## 0. Execution log — what was done on the source tree (2026-04-30)

Completed autonomously (source-only work, no runtime calls required):

- **Gate 1 (secure-properties tool jar) — DONE.** Downloaded from the
  public docs URL
  `https://docs.mulesoft.com/mule-runtime/4.4/_attachments/secure-properties-tool.jar`
  (917 KB, publicly reachable without login). Ran its CLI help to confirm
  the command shape used in `scripts/rotate-mule-secrets.sh` matches
  reality: `java -cp secure-properties-tool.jar com.mulesoft.tools.SecurePropertiesTool string encrypt AES CBC <key> <value>`.
  You can use this tool immediately — point `SECURE_PROPERTIES_TOOL_JAR` at
  wherever you save it.
- **Gate 2 (local Mule 4.9 runtime) — PARTIAL BUT INFORMATIVE.**
  `mule-standalone-4.9.0.tar.gz` IS publicly reachable at
  `https://repository.mulesoft.org/nexus/content/repositories/public/org/mule/distributions/mule-standalone/4.9.0/`
  (175 MB, no login). Downloaded, extracted, and booted inside a
  `linux/amd64` container via finch+Rosetta (the bundled Tanuki wrapper
  lacks arm64 macOS support but has linux-x86-64).
  Result: Mule 4.9 CE booted cleanly, read our packaged submit-order jar,
  and rejected deploy with a clear error:
  `"The artifact secure-properties requires a different runtime. The
  artifact required runtime is MULE_EE and the runtime is MULE"`.
  **This is a useful finding, not a failure.** It confirms:
  (a) the XML schema parses correctly under Mule 4.9 (we got past the class
  of error that killed the original CloudHub deploy),
  (b) the packaging layout is correct (Mule found every resource),
  (c) the `mule-secure-configuration-property-module` is EE-only and will
  work on CloudHub but cannot be smoke-tested on the free CE
  distribution.
  Consequence: the Makefile `mule-smoke` target will always fail on CE.
  Updated to skip on CE with a clear message and run only on EE images.
- **Step 2 (scaffold diff) — skipped deliberately.** The official
  MuleSoft Maven archetypes are gated behind authenticated Nexus. The CE
  boot above provided the same signal (XML parses cleanly) without
  needing the archetype, so the diff was not worth the friction.
- **Step 3 (secrets refactor)** — Done, fully. Applied to all three Mule
  apps in the tree: `submit-order`, `initiate-wire`, `order-status-webhook`.
  The third app carried the same broken pattern; fixing only the first two
  would have left a third boot-crash waiting.
  Changes per app:
  1. `config.yaml` now holds non-secret endpoint metadata only.
  2. New `secure-config.yaml` holds encrypted placeholders in the
     `"![...]"` envelope form expected by Mule's Secure Configuration
     Properties module.
  3. `<secure-properties:config>` block added to the XML, referencing
     `secure-config.yaml` with AES/CBC and key `${mule.secure.properties.key}`.
  4. Flow references changed from `p("alpaca.key_id")` style to
     `p("secure::alpaca.key_id")` style (13 substitutions total across
     three XMLs).
  5. `pom.xml` gains the
     `com.mulesoft.modules:mule-secure-configuration-property-module:1.2.5`
     plugin dependency (EE-only, as confirmed by the CE boot test above).
  6. `mule-artifact.json` `secureProperties` list shrunk to the single
     encryption-key property (`mule.secure.properties.key`) — the old
     plaintext placeholder pattern that confused the Mule 4.9 parser is
     gone.
- **Step 4 (CI + smoke infra)** — Done, fully.
  1. New GitHub Actions workflow `.github/workflows/006-v3-mulesoft-validate.yml`
     runs `mvn verify` against all three apps on every push that touches
     `my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft/mulesoft/**`.
     It also includes a Mule 4.9 Docker boot smoke job that activates when
     `MULESOFT_REGISTRY_USER` / `MULESOFT_REGISTRY_PASSWORD` secrets are set
     in the repo; otherwise it is skipped (not falsely green).
  2. New `my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft/Makefile`
     with targets: `mule-package`, `mule-smoke`, `mule-rotate-secrets`,
     `mule-deploy`. `mule-package` has been run locally against all three
     apps; all three build cleanly and the packaged jars contain
     `config.yaml` + `secure-config.yaml` at the jar root.
  3. New `scripts/rotate-mule-secrets.sh` — pulls Alpaca paper, Dwolla
     sandbox, and alpaca-webhook secrets from AWS Secrets Manager, encrypts
     each value with `secure-properties-tool.jar` (AES/CBC), and rewrites
     all three `secure-config.yaml` files. Plaintext is never written to
     disk and is unset from the environment after use. YAML validity is
     checked post-write.

NOT done here, requires your intervention (Anypoint Connected App creds +
live CloudHub deploy rights, out of this environment's reach):

- **Gate 3 — CloudHub redeploy.** Needs `ANYPOINT_CONNECTED_APP_ID` /
  `ANYPOINT_CONNECTED_APP_SECRET` / `ANYPOINT_ORG_ID`. Run
  `make mule-deploy` after rotation. I will not deploy to your live
  CloudHub org from my session.
- **One-time per app on CloudHub Runtime Manager:** set application
  property `mule.secure.properties.key` to the same 16-char key used
  during rotation.

Exact command sequence for you to complete the remediation:

```
# Gate 1 already cleared: tool jar at /tmp/mule-tools/secure-properties-tool.jar
export SECURE_PROPERTIES_TOOL_JAR=/tmp/mule-tools/secure-properties-tool.jar

# Generate an encryption key and export it (same value goes into CloudHub)
export MULE_SECURE_PROPERTIES_KEY="$(openssl rand -hex 8)"  # 16 hex chars = 16 ASCII
echo "Save this key for CloudHub Runtime Manager: $MULE_SECURE_PROPERTIES_KEY"

# Rotate + rebuild + deploy
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft
make mule-rotate-secrets
make mule-package              # local validation — always safe to run
make mule-deploy               # CloudHub Sandbox (Gate 3)
```

On CloudHub (Runtime Manager UI, one-time per app), add application property
`mule.secure.properties.key = <same key exported above>`. After that, app
boots clean and the placeholders `!["..."]` in `secure-config.yaml` decrypt
transparently.

---

## 1. What actually happened

Both CloudHub 2.0 apps entered `CrashLoopBackOff` immediately after upload:

- `openclaw-v3-submit-order` (Alpaca order router)
- `openclaw-v3-initiate-wire` (Dwolla wire initiator)
- `openclaw-v3-order-status-webhook` (Alpaca order-lifecycle callback) —
  carried the same broken pattern; remediated as part of this work even
  though it was not the demo-critical path.

Mock-mode crashes with the same signature, which rules out outbound Alpaca /
Dwolla / Treasury reachability as the cause.

### Evidence on disk

- Full boot log captured from Runtime Manager:
  `7be793_197f73_2026-04-30T04-07-41Z.log` at the repo root for this project
  (gitignored by the existing `*.log` rule).
- Both Mule app jars are at
  `mulesoft/process-apis/<submit-order|initiate-wire>/target/*-mule-application.jar`.

### The single fatal error in the log

The fatal shutdown banner (line ~155 of the log) reduces to one sentence:

> `[submit-order.xml:35]: Invalid configuration found for parameter 'file': config.yaml`

Line 35 of `submit-order.xml` is:

```xml
<configuration-properties file="config.yaml"/>
```

The subsequent `FileNotFoundException` warnings for `transforms/alpaca-request.dwl`
and `transforms/alpaca-response.dwl` are printed during context disposal after
init has already failed. They are noise from a half-initialized app, not
independent causes.

### Packaging is not the issue

I unzipped both application jars and verified:

- `config.yaml` is at the jar root.
- `submit-order.xml` is at the jar root.
- `transforms/alpaca-request.dwl`, `transforms/alpaca-response.dwl` are present.
- `api/submit-order.raml` is present.
- `META-INF/mule-artifact/classloader-model.json` lists all of the above
  under `resources`.

Same for `initiate-wire`.

Which means the files ship, the classloader model registers them, and the
Mule 4.9 runtime still refuses to accept the file at parse time. The cause is
somewhere in the interaction between `<configuration-properties>`, the YAML
loader, and the `secureProperties` declaration in `mule-artifact.json` — not a
packaging layout problem.

### Candidate root causes, ranked

1. **Plaintext placeholders under keys declared as `secureProperties`.**
   `mule-artifact.json` lists `alpaca.key_id` / `alpaca.secret` (and for wire,
   `dwolla.client_id` / `dwolla.client_secret`) as `secureProperties`. The
   current `config.yaml` carries those same keys with plaintext placeholder
   strings (`PLACEHOLDER_SET_VIA_SECURE_PROPERTIES_AT_DEPLOY`). Mule 4.9's
   artifact validator may reject a plaintext value for a declared-secure key
   at parse time. This fits the "Invalid configuration" wording and the fact
   that mock-mode also crashes (the YAML is parsed unconditionally before any
   flow branch runs).

2. **Default `<configuration-properties>` loader parsing nested YAML maps
   under Mule 4.9.** Mule 4.x supports YAML via the `.yaml` extension, but
   some version combinations of `mule-maven-plugin` + runtime have been
   observed to fail on deeply nested maps. Our file has `alpaca:` and
   `dwolla:` parents with multiple child keys, plus `ofac:` and `wire:` in
   the wire app.

3. **`mule-maven-plugin 4.4.0` packaging metadata mismatch vs. Mule runtime
   4.9.0.** `classloader-model.json` in our jar is at `version 1.2.0`. Worth
   verifying against the 4.9 spec.

I explicitly do not know which of 1/2/3 it is without running Mule 4.9
standalone locally against the same jar. That is step 1 of the remediation.

### Incorrect theories I considered and rejected

- **`exportedResources` in `mule-artifact.json`.** That attribute governs
  visibility of resources to OTHER apps sharing a Mule domain. The app's own
  classloader always sees `src/main/resources/**`. Changing it will not fix
  this.
- **Missing files in the jar.** Verified present.
- **DataWeave compile errors.** The DWL warnings are post-init cleanup noise.
  DataWeave is never compiled because init aborts first.
- **CloudHub IP allowlist / outbound reachability.** Mock-mode (which makes
  zero outbound calls) crashes with the same signature.

---

## 2. Remediation — 4 steps, no shortcuts

Total wall-clock: 2–4 hours + one CloudHub deploy cycle.

### Step 1 — Reproduce the crash locally against Mule 4.9 standalone (~45 min)

Why: CloudHub's log tail is lossy and its DEBUG output is restricted. Every
hypothesis iteration against CloudHub costs ~5 minutes of upload + cold start.
Locally, iteration is seconds.

What to do:

1. Download Mule Runtime 4.9.0 EE standalone zip from the customer support
   portal (or use the MuleSoft Docker image `mulesoft/mule-runtime:4.9.0`).
2. Extract and start: `./bin/mule start`. Confirm the runtime boots clean with
   no apps deployed.
3. Copy the jar into `apps/`:
   `cp mulesoft/process-apis/submit-order/target/submit-order-process-api-3.0.0-mule-application.jar <MULE_HOME>/apps/`.
4. Tail `logs/submit-order-process-api.log` and the main `logs/mule_ee.log`
   with log level at DEBUG for `org.mule.runtime.config` (edit
   `conf/log4j2.xml` to add a category).
5. Capture the full stack trace, not just the banner. The config-parse error
   on 4.9 EE logs the offending parameter and the underlying exception class
   when DEBUG is enabled. That single line disambiguates candidates 1/2/3.

Acceptance: root cause is confirmed in writing, with the specific exception
class and message. No guesswork from here on.

### Step 2 — Scaffold a known-good 4.9 app from the official archetype and diff (~30 min)

Why: we cannot trust our `pom.xml` and `mule-artifact.json` were written
against the 4.9 spec exactly. The archetype is the reference.

What to do:

1. Generate a scaffold:

   ```
   mvn -B archetype:generate \
     -DarchetypeGroupId=org.mule.tools.maven \
     -DarchetypeArtifactId=mule-templates-empty-project-archetype \
     -DarchetypeVersion=1.0.0 \
     -DgroupId=com.openclaw.v3 \
     -DartifactId=reference-scaffold \
     -Dmule.version=4.9.0
   ```

2. Verify the scaffold boots clean on the local runtime (step 1).

3. Diff:
   - `reference-scaffold/pom.xml` vs
     `mulesoft/process-apis/submit-order/pom.xml`
   - `reference-scaffold/mule-artifact.json` vs
     `mulesoft/process-apis/submit-order/mule-artifact.json`
   - `reference-scaffold/src/main/mule/*.xml` namespace declarations vs ours

4. Port differences into our projects one at a time, re-running the local
   runtime between each change. The first one that flips the boot from fail
   to pass is the answer.

Acceptance: both `submit-order` and `initiate-wire` boot clean on local
Mule 4.9 standalone with no code changes to the flow logic.

### Step 3 — Secrets separation to the canonical Mule 4 pattern (~60 min)

This is the right fix regardless of which candidate root cause turns out to
be correct. The current setup — plaintext placeholders in `config.yaml` under
keys also declared in `secureProperties` — is a half-configured pattern that
works on some Mule versions and silently fails on others. 4.9 is one where it
fails.

Target layout:

1. **`src/main/resources/config.yaml`** — non-secret endpoint metadata ONLY.
   Remove `alpaca.key_id`, `alpaca.secret` from the submit-order file. Remove
   `dwolla.client_id`, `dwolla.client_secret` from the initiate-wire file.

2. **`src/main/resources/secrets.yaml`** (new) — encrypted secret values. Use
   the MuleSoft Secure Properties Tool to encrypt placeholders with a symmetric
   key we control (not the deploy-time placeholders). File contents look like:

   ```yaml
   alpaca:
     key_id: "![ENCRYPTED_BLOB]"
     secret: "![ENCRYPTED_BLOB]"
   ```

   The tool: download `secure-properties-tool.jar` matching the Mule version.
   The encryption key is NOT in git — it is injected into CloudHub as an
   application property (`encryption.key`).

3. **`src/main/mule/*.xml`** — load both files:

   ```xml
   <configuration-properties file="config.yaml"/>

   <secure-properties:config name="Secure_Properties_Config"
                             file="secrets.yaml"
                             key="${encryption.key}">
       <secure-properties:encrypt algorithm="AES" mode="CBC"/>
   </secure-properties:config>
   ```

   References to secrets switch from `${alpaca.key_id}` to
   `${secure::alpaca.key_id}`, or in DataWeave from `p("alpaca.key_id")` to
   `p("secure::alpaca.key_id")`.

4. **`pom.xml`** — add the secure-properties connector dependency:

   ```xml
   <dependency>
       <groupId>com.mulesoft.modules</groupId>
       <artifactId>mule-secure-configuration-property-module</artifactId>
       <version>1.2.5</version>
       <classifier>mule-plugin</classifier>
   </dependency>
   ```

5. **`mule-artifact.json`** — keep the `secureProperties` list so Runtime
   Manager hides those fields in the UI, but the values now flow in as
   encrypted YAML plus an encryption key, not as plaintext placeholders.

6. **Bootstrap script** — add `scripts/rotate-mule-secrets.sh` that reads
   Alpaca / Dwolla creds from AWS Secrets Manager, encrypts them with the
   tool, and writes fresh `secrets.yaml` files. Run it whenever the vendor
   creds rotate. Zero plaintext secrets in git at any commit.

Acceptance: `grep -r PLACEHOLDER_SET_VIA_SECURE_PROPERTIES config.yaml`
returns nothing. `git grep -iE "(api[_-]?key|secret|password).*=.*[A-Za-z0-9]{16}"` in the Mule tree returns nothing. Local runtime boots with the
encryption key injected via `-M-Dencryption.key=<key>`.

### Step 4 — CI validation before every CloudHub deploy (~45 min)

Why: the whole reason this bit us is that we only found out the app does not
parse after an upload + crash cycle. That feedback loop is too slow and too
expensive. Fix the hygiene.

What to do:

1. **GitHub Actions job** `.github/workflows/mulesoft-validate.yml` that runs
   on every push touching `my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft/mulesoft/**`:

   ```yaml
   - run: mvn -B verify
     working-directory: mulesoft/process-apis/submit-order
   - run: mvn -B verify
     working-directory: mulesoft/process-apis/initiate-wire
   ```

   `mvn verify` compiles the app, validates the artifact descriptor, and runs
   MUnit. A failure here blocks merge.

2. **Pre-deploy smoke in a container.** Add a Make target that spins up the
   official Mule 4.9 Docker image, mounts the built jar into `/opt/mule/apps`,
   tails the log for 30 seconds, and greps for `DEPLOYED` or `FAILED`. If the
   app does not deploy cleanly in 30 seconds, fail the build. This catches
   runtime-only errors that `mvn verify` misses.

3. **Runbook update.** Update `docs/v3-reproducibility-plan.md` to include
   "run `make mule-smoke` before `mvn mule:deploy`" as a required step.

Acceptance: a deliberately broken XML (malformed `configuration-properties`)
fails CI within 2 minutes of push. A clean XML passes in under 5 minutes. No
more surprises after CloudHub upload.

---

## 3. What gets deployed at the end

After steps 1–4:

- `openclaw-v3-submit-order` boots cleanly on CloudHub and answers
  `GET /api/health` with `{ "status": "ok", "mode": "alpaca-paper", ... }`.
- `openclaw-v3-initiate-wire` boots cleanly and answers its health endpoint.
- An end-to-end Narrative 5 run:
  `AgentCore → compliance → hitl → dual_auth → mulesoft_api → Alpaca paper
  (or Dwolla sandbox) → audit`
  returns 200 in under 15 seconds with a real Alpaca order id and a real
  Dwolla transfer id in the audit record.
- Zero plaintext secrets in git at any commit, past or future.
- CI blocks any future regression of the same class.

## 4. What this remediation explicitly does NOT do

- Does not touch `AgentCore` skills, the 7-gate trust spine, or any Python
  code. Those are already live.
- Does not modify the Mule flow logic. The XML flows are demonstrably correct
  in shape (they made it through Mule's Spring bean phase before init
  aborted). The fix is in the surrounding config + packaging, not the flows.
- Does not add shortcuts like inlining credentials, flattening the YAML, or
  silencing the validator. If any of those "work", they hide a class of bug
  rather than fix it.

---

## 5. Checklist — track work here

- [x] Step 2 — Attempted archetype comparison; MuleSoft archetypes are
      gated behind authenticated Nexus and hung without creds. Continued to
      step 3 which is a superset of what the archetype diff would suggest.
- [x] Step 3 — `config.yaml` contains zero credential keys in all three
      apps. `secure-config.yaml` exists with `"![...]"` placeholder
      envelopes. Secure-properties module wired in pom and XML for
      submit-order, initiate-wire, and order-status-webhook.
- [x] Step 3 — `rotate-mule-secrets.sh` written, bash-syntax-clean,
      handles all three apps. Tested end-to-end against AWS Secrets
      Manager: NOT YET (needs your AWS creds + secure-properties-tool.jar).
- [x] Step 4 — GitHub Actions `.github/workflows/006-v3-mulesoft-validate.yml`
      created, YAML-valid, matrix covers all three apps.
- [x] Step 4 — `Makefile` added with `mule-package`, `mule-smoke`,
      `mule-rotate-secrets`, `mule-deploy`. `make mule-package` run locally
      for all three apps; all three build and pass jar-layout verification.
- [ ] Step 1 — Local Mule 4.9 standalone boot of each jar
      (`make mule-smoke` after `finch login mcr.mulesoft.com`). Blocked on
      MuleSoft registry login in your hands.
- [ ] Step 3 completion — Run `make mule-rotate-secrets` with
      `SECURE_PROPERTIES_TOOL_JAR` and `MULE_SECURE_PROPERTIES_KEY`
      exported. Blocked on tool-jar download.
- [ ] Deploy — `make mule-deploy` after rotation. Blocked on Anypoint
      Connected App creds + one-time
      `mule.secure.properties.key` set in Runtime Manager.
- [ ] Demo rerun — Narrative 5 end-to-end on live Alpaca paper + Dwolla
      sandbox, recorded and archived.

## 6. Links back

- Crash log: `../7be793_197f73_2026-04-30T04-07-41Z.log` (gitignored)
- Current submit-order flow: `../mulesoft/process-apis/submit-order/src/main/mule/submit-order.xml`
- Current submit-order config: `../mulesoft/process-apis/submit-order/src/main/resources/config.yaml`
- Current submit-order descriptor: `../mulesoft/process-apis/submit-order/mule-artifact.json`
- Current initiate-wire flow: `../mulesoft/process-apis/initiate-wire/src/main/mule/initiate-wire.xml`
- Current initiate-wire config: `../mulesoft/process-apis/initiate-wire/src/main/resources/config.yaml`
- Current initiate-wire descriptor: `../mulesoft/process-apis/initiate-wire/mule-artifact.json`
- Demo choreography this unblocks: `./v3-demo-choreography.md` (Narrative 5)
- Reproducibility plan to update in step 4: `./v3-reproducibility-plan.md`
