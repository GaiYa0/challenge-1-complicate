#!/usr/bin/env bash
# 用法: ./run/docker-logs.sh [服务名...]   默认跟踪 backend
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

svc=(backend)
if [[ $# -gt 0 ]]; then
  svc=("$@")
fi

docker compose logs -f "${svc[@]}"
