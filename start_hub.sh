#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
. .venv/bin/activate
if [ -n "${1:-}" ]; then
	export MP3_MEDIA_DIR="$1"
fi
exec python -m uvicorn device_service.main:app --host 0.0.0.0 --port 8000
