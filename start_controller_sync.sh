#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
. .venv/bin/activate
exec python -m controller_agent.media_sync --device-id "${1:-controller-1}" --hub-url "${2:-http://127.0.0.1:8000}" --watch-dir "${3:-controller_media}" --interval "${4:-3}"
