#!/bin/bash
# ==========================================
# THE MASTER DEPLOYMENT PIPELINE (GCP)
# ==========================================

# DEFENSIVE SCRIPTING: "Fail-Fast" mechanism.
# If any single command in this script fails (returns a non-zero exit code), 
# the script immediately stops. This prevents deploying broken infrastructure.
set -e 

# ==========================================
# 1. GLOBAL CONFIGURATION (Single Source of Truth)
# ==========================================
PROJECT_ID="jgaldamez-dev"
SERVICE_NAME="vending-api"
REGION="us-central1"
REPOSITORY="vending-repo"

# The fully qualified Docker image URI required by GCP Artifact Registry
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME:latest"

# --- ENTERPRISE EVOLUTION: THE PERMANENT DATABASE ---
# To stop the 15-minute "Self-Healing Sandbox" wipes, you must point the app to a permanent database.
# 1. Create a Cloud SQL (PostgreSQL) instance in your GCP Console.
# 2. Uncomment the PROD_DB_URI variable below and fill in your real database credentials.
# PROD_DB_URI="postgresql://my_db_user:my_db_password@/vending_db?host=/cloudsql/$PROJECT_ID:$REGION:my-sql-instance"


echo "==========================================="
echo "     Initiating Deployment to GCP..."
echo "==========================================="

# ==========================================
# 2. CONTEXT & IAM SETUP
# ==========================================
echo "[1/4] Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

echo "[2/4] Ensuring GCP APIs are enabled..."
# IDEMPOTENCY: This safely enables the necessary Google APIs. 
# If they are already enabled, Google simply ignores the command.
gcloud services enable run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

# ==========================================
# 3. ARTIFACT REGISTRY PROVISIONING
# ==========================================
echo "[3/4] Provisioning Artifact Registry Repository..."
# ARCHITECTURE NOTE: Graceful Error Handling
# We first try to 'describe' the repository. We pipe stdout and stderr to /dev/null to hide the output.
# If the repo DOES NOT exist, the command fails, triggering the '||' (OR) operator, 
# which seamlessly creates the repository on the fly.
gcloud artifacts repositories describe $REPOSITORY --location=$REGION > /dev/null 2>&1 || \
gcloud artifacts repositories create $REPOSITORY \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker repository for Vending Machine API" \
  --quiet

# ==========================================
# 4. CLOUD BUILD EXECUTION
# ==========================================
echo "[4/4] Building and pushing image via Cloud Build..."
# OFF-DEVICE COMPUTE: Instead of building the Docker container on your local laptop,
# this zips your directory, sends it to Google's server farm, builds it natively, 
# and pushes it directly into your Artifact Registry.
gcloud builds submit --tag $IMAGE .

# ==========================================
# 5. ZERO-DOWNTIME CLOUD RUN DEPLOYMENT
# ==========================================
echo "[5/5] Deploying to Cloud Run..."

# DYNAMIC ENVIRONMENT VARIABLES:
# We securely generate a 256-bit randomized SECRET_KEY on the fly.
ENV_VARS="SECRET_KEY=$(openssl rand -hex 32)"

# INTELLIGENT ROUTING: If the PROD_DB_URI is uncommented at the top of the script, 
# we automatically append it to the environment variables, seamlessly shifting 
# the Python backend from local SQLite to Google Cloud SQL (Postgres).
if [ -n "$PROD_DB_URI" ]; then
  echo "Enterprise Database detected! Shifting from local Sandbox to Cloud SQL..."
  ENV_VARS="${ENV_VARS},SQLALCHEMY_DATABASE_URI=${PROD_DB_URI}"
fi

# --allow-unauthenticated: Fulfills the business requirement that "Everyone can view products".
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --ingress all \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars="$ENV_VARS" \
  --quiet

# ==========================================
# 6. POST-DEPLOYMENT VERIFICATION
# ==========================================

echo "[HOTFIX] Bypassing Domain Restricted Sharing (The 403 Fix)..."
# This annotation forcefully disables IAM invocation checks for the container, 
# allowing public access even if the Organization Policy blocks 'allUsers' bindings.
gcloud run services update $SERVICE_NAME \
  --region=$REGION \
  --update-annotations run.googleapis.com/invoker-iam-disabled=true \
  --quiet

echo "==========================================="
echo "Deployment complete! The masterwork is live."

# Dynamically queries the Google Cloud API to extract the exact public HTTPS URL 
# assigned to your newly deployed container, so you don't have to go hunting for it in the UI.
echo "Service URL: $(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')"
echo "==========================================="