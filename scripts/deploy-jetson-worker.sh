#!/usr/bin/env bash
# Sync pick-a-print to the Jetson and restart the CUDA scan worker.
#
# App code is volume-mounted — routine deploys do NOT rebuild COLMAP.
#
# Usage:
#   ./scripts/deploy-jetson-worker.sh              # rsync + restart (fast)
#   ./scripts/deploy-jetson-worker.sh verbose      # rsync with progress + restart
#   ./scripts/deploy-jetson-worker.sh build        # full image rebuild (slow; COLMAP compile)
#   ./scripts/deploy-jetson-worker.sh build verbose
set -euo pipefail

DO_BUILD=0
VERBOSE=0
for arg in "$@"; do
  case "${arg}" in
    build) DO_BUILD=1 ;;
    verbose) VERBOSE=1 ;;
    *) echo "Unknown argument: ${arg}" >&2; echo "Usage: $0 [build] [verbose]" >&2; exit 1 ;;
  esac
done
if [[ "${VERBOSE:-}" == "1" ]]; then
  VERBOSE=1
fi

SRV2_IP="${SRV2_IP:-192.168.127.252}"
JETSON_HOST="${JETSON_HOST:-jetson}"
JETSON_DIR="${JETSON_DIR:-/home/pickeld/pick-a-print}"
JETSON_HEALTH_TOKEN="${JETSON_HEALTH_TOKEN:-}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_NAME="pick-a-print-worker-jetson"

if [[ "${VERBOSE}" -eq 1 ]]; then
  set -x
  RSYNC_FLAGS=(-avz --delete --progress)
  DOCKER_BUILD_PROGRESS=(--progress=plain)
else
  RSYNC_FLAGS=(-az --delete)
  DOCKER_BUILD_PROGRESS=()
fi

echo "==> Syncing repo to ${JETSON_HOST}:${JETSON_DIR}"
rsync "${RSYNC_FLAGS[@]}" \
  --exclude '.git' \
  --exclude 'data/jobs' \
  --exclude 'media' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'node_modules' \
  "${REPO_ROOT}/" "${JETSON_HOST}:${JETSON_DIR}/"

echo "==> Updating Jetson CUDA worker"
ssh "${JETSON_HOST}" bash -s <<EOF
set -euo pipefail
$([[ "${VERBOSE}" -eq 1 ]] && echo "set -x")
cd "${JETSON_DIR}"
export SRV2_REDIS_URL="redis://${SRV2_IP}:6379/1"
export SRV2_MINIO_URL="http://${SRV2_IP}:9002"
export JETSON_HEALTH_TOKEN="${JETSON_HEALTH_TOKEN}"
export DOCKER_BUILDKIT=1

if [[ "${DO_BUILD}" -eq 1 ]]; then
  echo "==> Full image rebuild (COLMAP compile — can take 30+ minutes)"
  docker compose -f docker-compose.jetson.yml build ${DOCKER_BUILD_PROGRESS[*]:-} worker
elif ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "==> Worker image not found — one-time build required"
  docker compose -f docker-compose.jetson.yml build ${DOCKER_BUILD_PROGRESS[*]:-} worker
else
  echo "==> Skipping image build (app code is volume-mounted; use 'build' to rebuild COLMAP image)"
fi

docker compose -f docker-compose.jetson.yml up -d worker
docker compose -f docker-compose.jetson.yml restart worker
docker compose -f docker-compose.jetson.yml ps
echo "==> CUDA / COLMAP check"
docker compose -f docker-compose.jetson.yml exec -T worker sh -c 'nvidia-smi -L; colmap patch_match_stereo -h 2>&1 | head -3'
EOF

echo "==> Jetson health endpoint: http://<jetson-host>:\${JETSON_HEALTH_PORT:-8765}/health"
echo "==> Set JETSON_HEALTH_TOKEN to the same value as Settings → Scan worker → Health check token"
echo "==> Rebuild COLMAP image only when Dockerfile.jetson or Python deps change:"
echo "    ./scripts/deploy-jetson-worker.sh build"
echo "==> Done. Stop srv2 CPU worker with:"
echo "    docker compose stop worker"
