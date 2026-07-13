#!/usr/bin/env bash
# Sync pick-a-print to the Jetson and start the CUDA scan worker.
set -euo pipefail

SRV2_IP="${SRV2_IP:-192.168.127.252}"
JETSON_HOST="${JETSON_HOST:-jetson}"
JETSON_DIR="${JETSON_DIR:-/home/pickeld/pick-a-print}"
JETSON_HEALTH_TOKEN="${JETSON_HEALTH_TOKEN:-}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Syncing repo to ${JETSON_HOST}:${JETSON_DIR}"
rsync -az --delete \
  --exclude '.git' \
  --exclude 'data/jobs' \
  --exclude 'media' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'node_modules' \
  "${REPO_ROOT}/" "${JETSON_HOST}:${JETSON_DIR}/"

echo "==> Building and starting Jetson CUDA worker"
ssh "${JETSON_HOST}" bash -s <<EOF
set -euo pipefail
cd "${JETSON_DIR}"
export SRV2_REDIS_URL="redis://${SRV2_IP}:6379/1"
export SRV2_MINIO_URL="http://${SRV2_IP}:9002"
export JETSON_HEALTH_TOKEN="${JETSON_HEALTH_TOKEN}"
docker compose -f docker-compose.jetson.yml up -d --build
docker compose -f docker-compose.jetson.yml ps
echo "==> CUDA / COLMAP check"
docker compose -f docker-compose.jetson.yml exec -T worker sh -c 'nvidia-smi -L; colmap patch_match_stereo -h 2>&1 | head -3'
EOF

echo "==> Jetson health endpoint: http://<jetson-host>:\${JETSON_HEALTH_PORT:-8765}/health"
echo "==> Set JETSON_HEALTH_TOKEN to the same value as Settings → Scan worker → Health check token"
echo "==> Point SRV2 Redis/MinIO at your public srv2 address if Jetson is off-LAN:"
echo "    SRV2_IP=your.srv2.domain ./scripts/deploy-jetson-worker.sh"
echo "==> Done. Stop srv2 CPU worker with:"
echo "    docker compose stop worker"
