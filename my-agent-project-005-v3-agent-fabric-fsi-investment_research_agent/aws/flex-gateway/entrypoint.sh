#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# entrypoint.sh — container PID 1 wrapper
# ──────────────────────────────────────────────────────────────────────────
# 1. Runs registration.sh (pulls Anypoint creds from Secrets Manager
#    and invokes flexctl register in CONNECTED mode).
# 2. Execs the stock Flex Gateway binary, handing it the config we baked
#    into /usr/local/share/mulesoft/flex-gateway/conf.d/.
#
# All env var requirements are documented in registration.sh. This wrapper
# only needs to know where the config lives.
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

log() { echo "[entrypoint] $(date -u +%FT%TZ) $*"; }

CONF_DIR="/usr/local/share/mulesoft/flex-gateway/conf.d"
REG_SCRIPT="/opt/flex-gateway/bin/registration.sh"

# ---- Trap SIGTERM so ECS can drain gracefully -------------------------
term_handler() {
  log "SIGTERM received — forwarding to flex-gateway PID ${GW_PID:-?}"
  if [[ -n "${GW_PID:-}" ]] && kill -0 "${GW_PID}" 2>/dev/null; then
    kill -TERM "${GW_PID}"
    wait "${GW_PID}" || true
  fi
  exit 0
}
trap term_handler SIGTERM SIGINT

# ---- Step 1: register with Anypoint -----------------------------------
log "Running registration script"
"${REG_SCRIPT}"

# ---- Step 2: start Flex Gateway ---------------------------------------
log "Starting Flex Gateway with config dir ${CONF_DIR}"
# The stock image's default command is `flex-gateway start`. We exec it
# with our mounted config so `kind: Configuration` is picked up.
flex-gateway start --config-dir "${CONF_DIR}" &
GW_PID=$!
log "flex-gateway PID=${GW_PID}"

# ---- Step 3: wait, forwarding signals ---------------------------------
wait "${GW_PID}"
exit $?
