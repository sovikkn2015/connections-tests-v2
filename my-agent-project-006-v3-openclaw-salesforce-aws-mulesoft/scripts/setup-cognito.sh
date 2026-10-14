#!/usr/bin/env bash
# ============================================================================
# setup-cognito.sh — Create Cognito User Pool + App Client + demo users.
#
# Fully automated — no AWS Console clicks needed. Idempotent: re-running
# skips resources that already exist.
#
# Usage:
#   ./scripts/setup-cognito.sh                    # full setup
#   ./scripts/setup-cognito.sh --pool-only        # just the pool + client
#   ./scripts/setup-cognito.sh --users-only       # just create demo users
#   ./scripts/setup-cognito.sh --destroy          # tear down everything
#
# After this script completes, run:
#   npm --prefix frontend run build
#   bash scripts/deploy-frontend-cloudfront.sh
#   cd aws && sam build && sam deploy ...
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

REGION="${AWS_REGION_BEDROCK:-us-east-1}"
POOL_NAME="fsi-workforce-360"
CLIENT_NAME="fsi-workforce-360-spa"
DOMAIN_PREFIX="fsi-workforce-360-$(aws sts get-caller-identity --query Account --output text 2>/dev/null | tail -c 5)"
CF_DOMAIN="${CLOUDFRONT_DOMAIN:-d2zs9nk4uc2dbx.cloudfront.net}"
CALLBACK_URL="https://${CF_DOMAIN}/auth/callback"
SIGNOUT_URL="https://${CF_DOMAIN}/"

POOL_ONLY=false
USERS_ONLY=false
DESTROY=false
for arg in "$@"; do
  case "$arg" in
    --pool-only)  POOL_ONLY=true ;;
    --users-only) USERS_ONLY=true ;;
    --destroy)    DESTROY=true ;;
    -h|--help)    sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf "\033[1;34m[cognito]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[cognito WARN]\033[0m %s\n" "$*" >&2; }
fatal(){ printf "\033[1;31m[cognito FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Destroy path
# ---------------------------------------------------------------------------
if $DESTROY; then
  POOL_ID=$(aws cognito-idp list-user-pools --region "$REGION" --max-results 60 \
    --query "UserPools[?Name=='${POOL_NAME}'].Id" --output text 2>/dev/null || echo "")
  if [[ -n "$POOL_ID" && "$POOL_ID" != "None" ]]; then
    # Must delete domain before pool
    DOMAIN=$(aws cognito-idp describe-user-pool --region "$REGION" \
      --user-pool-id "$POOL_ID" --query 'UserPool.Domain' --output text 2>/dev/null || echo "")
    if [[ -n "$DOMAIN" && "$DOMAIN" != "None" ]]; then
      log "Deleting domain $DOMAIN..."
      aws cognito-idp delete-user-pool-domain --region "$REGION" \
        --user-pool-id "$POOL_ID" --domain "$DOMAIN" 2>/dev/null || true
    fi
    log "Deleting pool $POOL_ID..."
    aws cognito-idp delete-user-pool --region "$REGION" --user-pool-id "$POOL_ID"
    log "Pool deleted."
  else
    log "No pool named '${POOL_NAME}' found."
  fi
  # Clear frontend env
  if [[ -f frontend/.env.production ]]; then
    sed -i.bak '/^VITE_COGNITO_/d' frontend/.env.production
    rm -f frontend/.env.production.bak
    log "Cleared VITE_COGNITO_* from frontend/.env.production"
  fi
  log "Cognito teardown complete."
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Create or find the User Pool
# ---------------------------------------------------------------------------
create_pool() {
  POOL_ID=$(aws cognito-idp list-user-pools --region "$REGION" --max-results 60 \
    --query "UserPools[?Name=='${POOL_NAME}'].Id" --output text 2>/dev/null || echo "")

  if [[ -n "$POOL_ID" && "$POOL_ID" != "None" ]]; then
    log "Pool '${POOL_NAME}' already exists: ${POOL_ID}"
  else
    log "Creating User Pool '${POOL_NAME}'..."
    POOL_ID=$(aws cognito-idp create-user-pool --region "$REGION" \
      --pool-name "$POOL_NAME" \
      --auto-verified-attributes email \
      --username-attributes email \
      --admin-create-user-config AllowAdminCreateUserOnly=true \
      --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=false,TemporaryPasswordValidityDays=7}" \
      --schema '[{"Name":"email","Required":true,"Mutable":true,"AttributeDataType":"String"},{"Name":"name","Required":true,"Mutable":true,"AttributeDataType":"String"}]' \
      --query 'UserPool.Id' --output text)
    log "Pool created: ${POOL_ID}"
  fi

  # Ensure domain exists
  EXISTING_DOMAIN=$(aws cognito-idp describe-user-pool --region "$REGION" \
    --user-pool-id "$POOL_ID" --query 'UserPool.Domain' --output text 2>/dev/null || echo "")
  if [[ -z "$EXISTING_DOMAIN" || "$EXISTING_DOMAIN" == "None" ]]; then
    log "Creating Cognito domain prefix: ${DOMAIN_PREFIX}"
    aws cognito-idp create-user-pool-domain --region "$REGION" \
      --user-pool-id "$POOL_ID" --domain "$DOMAIN_PREFIX" 2>/dev/null || {
      # Domain prefix taken — try with a random suffix
      DOMAIN_PREFIX="${DOMAIN_PREFIX}-$(openssl rand -hex 2)"
      aws cognito-idp create-user-pool-domain --region "$REGION" \
        --user-pool-id "$POOL_ID" --domain "$DOMAIN_PREFIX"
    }
    log "Domain: https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com"
  else
    DOMAIN_PREFIX="$EXISTING_DOMAIN"
    log "Domain already set: https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com"
  fi
}

# ---------------------------------------------------------------------------
# Step 2: Create or find the App Client
# ---------------------------------------------------------------------------
create_client() {
  CLIENT_ID=$(aws cognito-idp list-user-pool-clients --region "$REGION" \
    --user-pool-id "$POOL_ID" --max-results 60 \
    --query "UserPoolClients[?ClientName=='${CLIENT_NAME}'].ClientId" --output text 2>/dev/null || echo "")

  if [[ -n "$CLIENT_ID" && "$CLIENT_ID" != "None" ]]; then
    log "App Client '${CLIENT_NAME}' already exists: ${CLIENT_ID}"
  else
    log "Creating App Client '${CLIENT_NAME}'..."
    CLIENT_ID=$(aws cognito-idp create-user-pool-client --region "$REGION" \
      --user-pool-id "$POOL_ID" \
      --client-name "$CLIENT_NAME" \
      --generate-secret false \
      --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_REFRESH_TOKEN_AUTH \
      --supported-identity-providers COGNITO \
      --allowed-o-auth-flows code \
      --allowed-o-auth-scopes openid profile email \
      --allowed-o-auth-flows-user-pool-client true \
      --callback-urls "$CALLBACK_URL" \
      --logout-urls "$SIGNOUT_URL" \
      --access-token-validity 1 \
      --id-token-validity 1 \
      --refresh-token-validity 30 \
      --token-validity-units "AccessToken=hours,IdToken=hours,RefreshToken=days" \
      --query 'UserPoolClient.ClientId' --output text)
    log "App Client created: ${CLIENT_ID}"
  fi
}

# ---------------------------------------------------------------------------
# Step 3: Create demo users
# ---------------------------------------------------------------------------
create_users() {
  USERS=(
    "sarah.chen@fsi-demo.com:Sarah Chen"
    "marcus.kerrigan@fsi-demo.com:Marcus Kerrigan"
    "eleanor.vance@fsi-demo.com:Eleanor Vance"
  )

  for entry in "${USERS[@]}"; do
    EMAIL="${entry%%:*}"
    NAME="${entry##*:}"
    EXISTS=$(aws cognito-idp admin-get-user --region "$REGION" \
      --user-pool-id "$POOL_ID" --username "$EMAIL" \
      --query 'Username' --output text 2>/dev/null || echo "")
    if [[ -n "$EXISTS" && "$EXISTS" != "None" ]]; then
      log "User $EMAIL already exists"
      continue
    fi
    TEMP_PASS="Demo-$(openssl rand -hex 4)!"
    aws cognito-idp admin-create-user --region "$REGION" \
      --user-pool-id "$POOL_ID" \
      --username "$EMAIL" \
      --user-attributes "Name=email,Value=$EMAIL" "Name=email_verified,Value=true" "Name=name,Value=$NAME" \
      --temporary-password "$TEMP_PASS" \
      --message-action SUPPRESS >/dev/null
    # Force-set a permanent password so demo users don't hit the change-password flow
    PERM_PASS="Fsi360-$(openssl rand -hex 4)!"
    aws cognito-idp admin-set-user-password --region "$REGION" \
      --user-pool-id "$POOL_ID" \
      --username "$EMAIL" \
      --password "$PERM_PASS" \
      --permanent >/dev/null
    log "Created user: $EMAIL / $PERM_PASS"
  done
}

# ---------------------------------------------------------------------------
# Step 4: Write frontend env vars
# ---------------------------------------------------------------------------
write_frontend_env() {
  COGNITO_DOMAIN="https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com"
  ENV_FILE="frontend/.env.production"

  # Remove any existing VITE_COGNITO_ lines
  if [[ -f "$ENV_FILE" ]]; then
    sed -i.bak '/^VITE_COGNITO_/d' "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
  fi

  cat >> "$ENV_FILE" <<EOF
VITE_COGNITO_DOMAIN=${COGNITO_DOMAIN}
VITE_COGNITO_CLIENT_ID=${CLIENT_ID}
VITE_COGNITO_REDIRECT_URI=${CALLBACK_URL}
VITE_COGNITO_SCOPE=openid profile email
VITE_COGNITO_REGION=${REGION}
VITE_COGNITO_USER_POOL_ID=${POOL_ID}
EOF

  log "Frontend env written to ${ENV_FILE}"
  log "  VITE_COGNITO_DOMAIN=${COGNITO_DOMAIN}"
  log "  VITE_COGNITO_CLIENT_ID=${CLIENT_ID}"
  log "  VITE_COGNITO_USER_POOL_ID=${POOL_ID}"
}

# ---------------------------------------------------------------------------
# Step 5: Store pool ID + client ID in SSM for agent-proxy Lambda
# ---------------------------------------------------------------------------
store_ssm() {
  aws ssm put-parameter --region "$REGION" \
    --name /006-v3/cognito/user-pool-id --value "$POOL_ID" \
    --type String --overwrite >/dev/null
  aws ssm put-parameter --region "$REGION" \
    --name /006-v3/cognito/app-client-id --value "$CLIENT_ID" \
    --type String --overwrite >/dev/null
  log "SSM params stored: /006-v3/cognito/user-pool-id, /006-v3/cognito/app-client-id"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if ! $USERS_ONLY; then
  create_pool
  create_client
  write_frontend_env
  store_ssm
fi

if ! $POOL_ONLY; then
  if $USERS_ONLY; then
    # Need pool ID for user creation
    POOL_ID=$(aws cognito-idp list-user-pools --region "$REGION" --max-results 60 \
      --query "UserPools[?Name=='${POOL_NAME}'].Id" --output text 2>/dev/null || echo "")
    [[ -n "$POOL_ID" && "$POOL_ID" != "None" ]] || fatal "Pool not found — run without --users-only first"
  fi
  create_users
fi

log ""
log "=== Cognito setup complete ==="
log "Pool ID:    ${POOL_ID}"
log "Client ID:  ${CLIENT_ID:-<see SSM>}"
log "Domain:     https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com"
log ""
log "Next steps:"
log "  1. npm --prefix frontend run build"
log "  2. bash scripts/deploy-frontend-cloudfront.sh"
log "  3. Add JWKS verification to agent-proxy (see below)"
log "  4. cd aws && sam build && sam deploy"
