#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REGISTRY="${REGISTRY:-localhost:32000}"
NAMESPACE="${NAMESPACE:-quilr-onboard}"
KUBECTL="${KUBECTL:-microk8s kubectl}"

FRONTEND_IMAGE="${FRONTEND_IMAGE:-$REGISTRY/quilr-onboard-frontend:latest}"
BACKEND_IMAGE="${BACKEND_IMAGE:-$REGISTRY/quilr-onboard-backend:latest}"
FRONTEND_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-}"

usage() {
  cat <<'EOF'
Usage: scripts/deploy.sh [all|backend|frontend]

Environment variables:
  REGISTRY                 Local registry (default: localhost:32000)
  NAMESPACE                Kubernetes namespace (default: quilr-onboard)
  KUBECTL                  Kubectl command (default: "microk8s kubectl")
  BACKEND_IMAGE            Backend image tag
  FRONTEND_IMAGE           Frontend image tag
  NEXT_PUBLIC_API_BASE_URL Optional build arg for frontend

Examples:
  scripts/deploy.sh all
  NEXT_PUBLIC_API_BASE_URL=http://quilr.local scripts/deploy.sh frontend
  KUBECTL="sudo microk8s kubectl" scripts/deploy.sh backend
EOF
}

build_backend() {
  echo "Building backend image: ${BACKEND_IMAGE}"
  docker build -t "${BACKEND_IMAGE}" -f "${ROOT_DIR}/backend/Dockerfile" "${ROOT_DIR}"
  echo "Pushing backend image..."
  docker push "${BACKEND_IMAGE}"
}

build_frontend() {
  echo "Building frontend image: ${FRONTEND_IMAGE}"
  if [[ -n "${FRONTEND_BASE_URL}" ]]; then
    docker build \
      --build-arg NEXT_PUBLIC_API_BASE_URL="${FRONTEND_BASE_URL}" \
      -t "${FRONTEND_IMAGE}" \
      -f "${ROOT_DIR}/frontend/Dockerfile" \
      "${ROOT_DIR}"
  else
    docker build -t "${FRONTEND_IMAGE}" -f "${ROOT_DIR}/frontend/Dockerfile" "${ROOT_DIR}"
  fi
  echo "Pushing frontend image..."
  docker push "${FRONTEND_IMAGE}"
}

apply_config() {
  if [[ -f "${ROOT_DIR}/k8s/configmap.yaml" ]]; then
    echo "Applying configmap..."
    ${KUBECTL} apply -f "${ROOT_DIR}/k8s/configmap.yaml"
  fi
}

rollout_backend() {
  echo "Restarting backend deployment..."
  ${KUBECTL} rollout restart deployment/quilr-backend -n "${NAMESPACE}"
  ${KUBECTL} rollout status deployment/quilr-backend -n "${NAMESPACE}"
}

rollout_frontend() {
  echo "Restarting frontend deployment..."
  ${KUBECTL} rollout restart deployment/quilr-frontend -n "${NAMESPACE}"
  ${KUBECTL} rollout status deployment/quilr-frontend -n "${NAMESPACE}"
}

target="${1:-all}"
case "${target}" in
  all)
    build_backend
    build_frontend
    apply_config
    rollout_backend
    rollout_frontend
    ;;
  backend)
    build_backend
    apply_config
    rollout_backend
    ;;
  frontend)
    build_frontend
    rollout_frontend
    ;;
  -h|--help)
    usage
    ;;
  *)
    echo "Unknown target: ${target}" >&2
    usage
    exit 1
    ;;
esac
