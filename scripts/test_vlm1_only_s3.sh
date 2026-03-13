#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <s3://bucket/object> [service_url]" >&2
  exit 1
fi

IMAGE_URI="$1"
SERVICE_URL="${2:-http://127.0.0.1:8000}"

uv run python -m ares_agent.tools.post_inspection_item \
  --service-url "$SERVICE_URL" \
  --image-uri "$IMAGE_URI" \
  --camera-id front \
  --location 南山路 \
  --device-id dog-17 \
  --task-id patrol-s3-001 \
  --occur-time 2026-03-13T10:00:00Z
