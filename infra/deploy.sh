#!/usr/bin/env bash
# deploy.sh — Build, push, and deploy both containers to AWS ECS.
# Usage:
#   ./infra/deploy.sh                      # deploy latest (git SHA tag)
#   IMAGE_TAG=v1.2.3 ./infra/deploy.sh     # deploy a specific tag
#   DRY_RUN=1 ./infra/deploy.sh            # print commands without running them
set -euo pipefail

# ── Config (override via environment variables) ───────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
ECS_CLUSTER="${ECS_CLUSTER:-ai-stock-report}"
API_SERVICE="${API_SERVICE:-ai-stock-report-api}"
STREAMLIT_SERVICE="${STREAMLIT_SERVICE:-ai-stock-report-streamlit}"
ECR_API_REPO="${ECR_API_REPO:-ai-stock-report-api}"
ECR_STREAMLIT_REPO="${ECR_STREAMLIT_REPO:-ai-stock-report-streamlit}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
DRY_RUN="${DRY_RUN:-0}"

run() {
  echo "  $ $*"
  [[ "$DRY_RUN" == "1" ]] || "$@"
}

# ── Resolve account & registry ────────────────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "========================================"
echo " AI Stock Report — ECS Deployment"
echo "========================================"
echo "  Region   : $AWS_REGION"
echo "  Account  : $ACCOUNT_ID"
echo "  Cluster  : $ECS_CLUSTER"
echo "  Image tag: $IMAGE_TAG"
[[ "$DRY_RUN" == "1" ]] && echo "  [DRY RUN — commands will not execute]"
echo "----------------------------------------"

# ── ECR login ─────────────────────────────────────────────────────────────────
echo ""
echo "==> Logging in to ECR..."
run aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# ── Build & push API ──────────────────────────────────────────────────────────
API_IMAGE="${ECR_REGISTRY}/${ECR_API_REPO}:${IMAGE_TAG}"
echo ""
echo "==> Building API image..."
run docker build -t "$API_IMAGE" -t "${ECR_REGISTRY}/${ECR_API_REPO}:latest" \
  -f Dockerfile .

echo "==> Pushing API image..."
run docker push "$API_IMAGE"
run docker push "${ECR_REGISTRY}/${ECR_API_REPO}:latest"

# ── Build & push Streamlit ────────────────────────────────────────────────────
STREAMLIT_IMAGE="${ECR_REGISTRY}/${ECR_STREAMLIT_REPO}:${IMAGE_TAG}"
echo ""
echo "==> Building Streamlit image..."
run docker build -t "$STREAMLIT_IMAGE" -t "${ECR_REGISTRY}/${ECR_STREAMLIT_REPO}:latest" \
  -f Dockerfile.streamlit .

echo "==> Pushing Streamlit image..."
run docker push "$STREAMLIT_IMAGE"
run docker push "${ECR_REGISTRY}/${ECR_STREAMLIT_REPO}:latest"

# ── ECS deployments ───────────────────────────────────────────────────────────
echo ""
echo "==> Triggering ECS deployment for API service..."
run aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service "$API_SERVICE" \
  --force-new-deployment \
  --region "$AWS_REGION" \
  --output table

echo ""
echo "==> Triggering ECS deployment for Streamlit service..."
run aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service "$STREAMLIT_SERVICE" \
  --force-new-deployment \
  --region "$AWS_REGION" \
  --output table

# ── Wait for rollout ──────────────────────────────────────────────────────────
echo ""
echo "==> Waiting for services to stabilise (this may take a few minutes)..."
run aws ecs wait services-stable \
  --cluster "$ECS_CLUSTER" \
  --services "$API_SERVICE" "$STREAMLIT_SERVICE" \
  --region "$AWS_REGION"

echo ""
echo "========================================"
echo " Deployment complete! ✓"
echo "========================================"
