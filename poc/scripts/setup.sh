#!/usr/bin/env bash
# Memory App POC — one-shot setup for track A.
# Builds the Animated Drawings docker image and waits for healthcheck.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/3] building docker image (this takes 5–10 min on first run)..."
docker compose build

echo "[2/3] starting container..."
docker compose up -d

echo "[3/3] waiting for torchserve to be healthy..."
for i in {1..60}; do
    if curl -fsS http://localhost:8080/ping >/dev/null 2>&1; then
        echo "torchserve healthy after ${i}0s"
        echo
        echo "next: drop a child's drawing into ./samples and run:"
        echo "  python3 src/pipeline.py samples/<file>.jpg out/"
        exit 0
    fi
    sleep 10
done

echo "torchserve did not become healthy in 10min." >&2
echo "check: docker compose logs animated-drawings" >&2
exit 1
