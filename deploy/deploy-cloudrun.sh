#!/usr/bin/env bash
set -euo pipefail

# Deploys inventory-services to Cloud Run in the TravelHub GCP project.
# Requires gcloud CLI authenticated and project set.
#
# Usage:
#   bash deploy/deploy-cloudrun.sh dev    # deploys to gen-lang-client-0930444414
#   bash deploy/deploy-cloudrun.sh prod   # deploys to travelhub-prod-492116
#
# Prerequisites per environment:
#   DEV:  Secret INVENTORY_DATABASE_URL exists in gen-lang-client-0930444414
#   PROD: Secret INVENTORY_DATABASE_URL exists in travelhub-prod-492116
#         Service account Compute Engine default SA has secretAccessor on that secret.

ENV="${1:-dev}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="inventory-services"
ARTIFACT_REPO="${ARTIFACT_REPO:-inventory-services}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%s)}"

if [[ "${ENV}" == "prod" ]]; then
  PROJECT_ID="${PROD_PROJECT_ID:-travelhub-prod-492116}"
  NETWORK="prod-travelhub-vpc"
  SUBNET="prod-travelhub-subnet-services"
else
  PROJECT_ID="${DEV_PROJECT_ID:-gen-lang-client-0930444414}"
  NETWORK="travelhub-vpc"
  SUBNET="subnet-services"
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo ">> Building image ${IMAGE} (env=${ENV})"
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

echo ">> Deploying to Cloud Run (${ENV})"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --clear-vpc-connector \
  --network="${NETWORK}" \
  --subnet="${SUBNET}" \
  --vpc-egress=private-ranges-only \
  --set-env-vars "JWT_ISSUER=https://auth.travelhub.app,JWT_AUDIENCE=travelhub-api,SERVICE_NAME=${SERVICE_NAME},KAFKA_ENABLED=true,KAFKA_TOPIC_INVENTORY_RATES=inventory-rate-events" \
  --set-secrets "DATABASE_URL=INVENTORY_DATABASE_URL:latest,KAFKA_BOOTSTRAP_SERVERS=KAFKA_BOOTSTRAP_SERVERS:latest" \
  --allow-unauthenticated \
  --port 8000 \
  --region "${REGION}" \
  --project "${PROJECT_ID}"

URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')

echo ""
echo ">> Deployed: ${URL}"
echo ">> Update uniandes-pf-infra-gcp/gateway/openapi-spec-prod.yaml:"
echo ">>   Replace 'inventory-services-PLACEHOLDER.a.run.app' with: $(echo "${URL}" | sed 's|https://||')"
echo ">> Then redeploy gateway config."
