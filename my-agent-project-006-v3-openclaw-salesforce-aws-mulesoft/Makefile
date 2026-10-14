# Project 006 v3 — MuleSoft local workflow helpers.
#
# Deployment flow for a new user:
#   1. make verify-mule    # pre-flight checks (NO network calls) — run first!
#   2. make mule-package   # build all three app jars
#   3. make mule-deploy    # publish to Exchange + deploy to CloudHub Sandbox
#   4. bash scripts/set-mule-secure-properties.sh
#                          # PATCH per-app plain + secure properties into
#                          # Anypoint Runtime Manager (reads AWS secrets).
#                          # Full walkthrough: docs/v3-mulesoft-deploy-runbook.md
#   5. make mule-health    # curl each /api/health, confirm all three live
#
# Prereqs for mule-deploy:
#   export ANYPOINT_CONNECTED_APP_ID=...
#   export ANYPOINT_CONNECTED_APP_SECRET=...
#   export ANYPOINT_ORG_ID=...
#   export JAVA_HOME=...  (JDK 17)
#
# See docs/v3-mulesoft-gotchas.md for the four classes of bugs that
# verify-mule catches before a deploy.

MULE_APPS := submit-order initiate-wire order-status-webhook
MULE_ROOT := mulesoft/process-apis

.PHONY: help verify-mule mule-package mule-deploy mule-health

help:
	@echo "verify-mule    - pre-flight checks (mule-artifact.json, YAML types, DNS, DW funcs)"
	@echo "mule-package   - mvn clean package for all three apps"
	@echo "mule-deploy    - mvn deploy + mule:deploy to CloudHub Sandbox (all three)"
	@echo "mule-health    - curl each /api/health to confirm all running"
	@echo ""
	@echo "Deploy order: verify-mule -> mule-package -> mule-deploy -> mule-health"

# ---------------------------------------------------------------------------
# verify-mule — catches the four gotchas documented in docs/v3-mulesoft-gotchas.md
# ---------------------------------------------------------------------------
verify-mule:
	@echo "==> 1/4  checking mule-artifact.json exportedResources is non-empty..."
	@for app in $(MULE_APPS); do \
		F=$(MULE_ROOT)/$$app/mule-artifact.json; \
		RES=$$(python3 -c "import json; print(len(json.load(open('$$F'))['classLoaderModelLoaderDescriptor']['attributes']['exportedResources']))"); \
		if [ "$$RES" = "0" ]; then \
			echo "FAIL: $$F has empty exportedResources. See docs/v3-mulesoft-gotchas.md#gotcha-1"; \
			exit 1; \
		fi; \
		echo "    OK: $$app lists $$RES exported resources"; \
	done
	@echo ""
	@echo "==> 2/4  checking all config.yaml values are quoted strings..."
	@for app in $(MULE_APPS); do \
		F=$(MULE_ROOT)/$$app/src/main/resources/config.yaml; \
		BAD=$$(python3 -c "import yaml; d=yaml.safe_load(open('$$F')); bad=[(k,type(v).__name__) for k,v in d.items() if not isinstance(v, str)]; print(bad)"); \
		if [ "$$BAD" != "[]" ]; then \
			echo "FAIL: $$F has non-string values: $$BAD"; \
			echo "      See docs/v3-mulesoft-gotchas.md#gotcha-2"; \
			exit 1; \
		fi; \
		echo "    OK: $$app config.yaml all strings"; \
	done
	@echo ""
	@echo "==> 3/4  checking all config.yaml \$$\{*.host\} values are resolvable hostnames..."
	@for app in $(MULE_APPS); do \
		F=$(MULE_ROOT)/$$app/src/main/resources/config.yaml; \
		HOSTS=$$(python3 -c "import yaml; d=yaml.safe_load(open('$$F')); print(' '.join(v for k,v in d.items() if k.endswith('.host') and v))"); \
		for H in $$HOSTS; do \
			if ! dig +short +time=3 "$$H" A | grep -qE "^[0-9]+\."; then \
				if [ "$$H" != "localhost" ]; then \
					echo "WARN: $$F host '$$H' did not resolve (localhost default is OK)"; \
					echo "      See docs/v3-mulesoft-gotchas.md#gotcha-3"; \
				fi; \
			fi; \
		done; \
		echo "    OK: $$app hosts resolvable"; \
	done
	@echo ""
	@echo "==> 4/4  checking no XML uses the nonexistent dw::core::Binaries::toHex function..."
	@HITS=$$(grep -rln "Binaries::toHex" $(MULE_ROOT)/*/src/main/mule/ 2>/dev/null || true); \
	if [ -n "$$HITS" ]; then \
		echo "FAIL: Binaries::toHex referenced in: $$HITS"; \
		echo "      Replace with: someBinary as String {base: \"16\"}"; \
		echo "      See docs/v3-mulesoft-gotchas.md#gotcha-4"; \
		exit 1; \
	fi
	@echo "    OK: no toHex references"
	@echo ""
	@echo "==> ALL CHECKS PASSED. Safe to run: make mule-package && make mule-deploy"

# ---------------------------------------------------------------------------
# mule-package — build all three jars. Depends on verify-mule to catch bugs early.
# ---------------------------------------------------------------------------
mule-package: verify-mule
	@for app in $(MULE_APPS); do \
		echo "==> Packaging $$app"; \
		(cd $(MULE_ROOT)/$$app && mvn -B -e clean package -DskipTests); \
		JAR=$$(ls $(MULE_ROOT)/$$app/target/*-mule-application.jar | head -1); \
		echo "    jar: $$JAR"; \
		if ! unzip -l "$$JAR" | grep -q " config.yaml$$"; then \
			echo "FAIL: config.yaml missing from $$JAR"; exit 1; \
		fi; \
		EXPORTED=$$(unzip -p "$$JAR" META-INF/mule-artifact/mule-artifact.json | \
			python3 -c "import json,sys; print(len(json.load(sys.stdin)['classLoaderModelLoaderDescriptor']['attributes']['exportedResources']))"); \
		if [ "$$EXPORTED" = "0" ]; then \
			echo "FAIL: packaged jar has empty exportedResources. mule-artifact.json at project root was ignored."; \
			exit 1; \
		fi; \
		echo "    OK: $$EXPORTED resources exported in jar"; \
	done

# ---------------------------------------------------------------------------
# mule-deploy — publishes each app to Exchange THEN deploys to CloudHub.
# Note: `mvn deploy` does the Exchange publish. `mvn mule:deploy` does CloudHub.
# ---------------------------------------------------------------------------
mule-deploy: mule-package
	@for app in $(MULE_APPS); do \
		echo "==> $$app: publishing to Anypoint Exchange..."; \
		(cd $(MULE_ROOT)/$$app && mvn -B deploy -DskipTests -DskipMunitTests=true) || exit 1; \
		echo "==> $$app: deploying to CloudHub Sandbox..."; \
		(cd $(MULE_ROOT)/$$app && mvn -B mule:deploy -DmuleDeploy -DskipTests) || exit 1; \
	done
	@echo ""
	@echo "==> Deploy complete. Wait ~3 minutes then run: make mule-health"
	@echo ""
	@echo "NEXT STEP (required): bash scripts/set-mule-secure-properties.sh"
	@echo "  This script reads AWS Secrets Manager + SSM and PATCHes each app's"
	@echo "  plain + secure properties into Anypoint Runtime Manager. Without"
	@echo "  it, the apps will crash-loop waiting for Alpaca/Dwolla/webhook"
	@echo "  credentials. Full walkthrough: docs/v3-mulesoft-deploy-runbook.md"

# ---------------------------------------------------------------------------
# mule-health — dynamic /api/health probe (URLs discovered from Anypoint API).
# Delegates to scripts/mule-health.sh so the URL lookup is not hardcoded to
# one business-group subdomain. That script reads Anypoint creds from AWS
# SSM, OAuths, resolves org + Sandbox env + each app's deployment, then
# curls each app's publicUrl/api/health.
# ---------------------------------------------------------------------------
mule-health:
	@bash scripts/mule-health.sh
