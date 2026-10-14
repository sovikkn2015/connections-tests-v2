#!/bin/bash
# ============================================================
# COMPLETE SETUP SCRIPT — FSI Wealth Advisor Agent (Phase 1-5)
# ============================================================
#
# This script deploys the entire project to a fresh Salesforce org.
# Run from the project root: my-agent-project-004-fsi-wealth_advisor_agent-phase1to5/
#
# Prerequisites:
#   - Salesforce CLI (sf) installed
#   - Authenticated to an Agentforce-enabled org with Data Cloud
#   - Run: sf org login web --alias my-org --set-default
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# What this script does (in order):
#   1. Deploys custom objects (8 objects, 44+ fields)
#   2. Deploys Apex classes (11 classes)
#   3. Deploys permission sets (3: Advisor, Compliance, Admin)
#   4. Deploys remote site settings (Alpha Vantage, NewsAPI)
#   5. Grants field-level security
#   6. Seeds demo data (90+ records)
#   7. Grants Apex class access to Einstein Agent User
#   8. Assigns permission sets to current user
#   9. Creates Knowledge articles (5) and publishes them
#  10. Deploys agent script (12 topics)
#  11. Creates Data Cloud CRM data streams (7 objects)
#  12. Waits for Data Cloud sync
#  13. Verifies Data Cloud data
#
# After this script completes, you need to do ONE manual step:
#   - Go to Setup → Agents → WA P1to5 Advisor
#   - Click "New Version" → Commit → Activate
#   - Then deploy test definitions:
#     sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions
#   - Then run tests:
#     sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --verbose
#
# ============================================================

set -e  # Exit on any error

echo "============================================================"
echo "  FSI Wealth Advisor Agent — Complete Setup"
echo "============================================================"
echo ""

# Step 1: Deploy objects
echo "[1/13] Deploying custom objects..."
sf project deploy start --source-dir force-app/main/default/objects --wait 5

# Step 2: Deploy Apex classes
echo "[2/13] Deploying Apex classes (11)..."
sf project deploy start --source-dir force-app/main/default/classes --wait 5

# Step 3: Deploy permission sets
echo "[3/13] Deploying permission sets (3)..."
sf project deploy start --source-dir force-app/main/default/permissionsets --wait 5

# Step 4: Deploy remote site settings
echo "[4/13] Deploying remote site settings..."
sf project deploy start --source-dir force-app/main/default/remoteSiteSettings --wait 5

# Step 5: Grant FLS
echo "[5/13] Granting field-level security..."
sf apex run --file scripts/apex/grant-fls.apex

# Step 6: Seed data
echo "[6/13] Seeding demo data (90+ records)..."
sf apex run --file scripts/apex/seed-data.apex

# Step 7: Grant agent permissions
echo "[7/13] Granting Apex class access to Einstein Agent User..."
sf apex run --file scripts/apex/grant-permissions.apex

# Step 8: Assign permission sets
echo "[8/13] Assigning permission sets to current user..."
sf apex run --file scripts/apex/assign-permission-sets.apex

# Step 9: Knowledge articles
echo "[9/13] Creating and publishing Knowledge articles..."
sf apex run --file scripts/apex/seed-knowledge-articles.apex
sf apex run --file scripts/apex/publish-knowledge-articles.apex

# Step 10: Deploy agent
echo "[10/13] Deploying agent script (12 topics)..."
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 5

# Step 11: Create Data Cloud streams
echo "[11/13] Creating Data Cloud CRM data streams (7 objects)..."
sf apex run --file scripts/apex/create-data-cloud-streams.apex

# Step 12: Wait for sync
echo "[12/13] Waiting 60 seconds for Data Cloud initial sync..."
sleep 60

# Step 13: Verify
echo "[13/13] Verifying Data Cloud data..."
sf apex run --file scripts/apex/verify-data.apex

echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "  MANUAL STEP REQUIRED:"
echo "    1. sf org open"
echo "    2. Setup → Agents → WA P1to5 Advisor"
echo "    3. New Version → Commit → Activate"
echo ""
echo "  THEN DEPLOY TESTS AND RUN:"
echo "    sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions"
echo "    sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --verbose"
echo ""
echo "  API KEYS (optional, for market data + news topics):"
echo "    - Register at https://www.alphavantage.co/support/#api-key"
echo "    - Register at https://newsapi.org/register"
echo "    - Set keys in Setup → Named Credentials → External Credentials"
echo ""
echo "============================================================"
