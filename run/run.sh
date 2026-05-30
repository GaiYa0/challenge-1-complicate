#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  sed -n '1,40p' <<'EOF'
用法: ./run/run.sh <子命令> [参数]

  docker-up       构建并启动 docker compose（同 docker-up.sh）
  docker-down     停止 docker compose
  docker-logs     跟踪日志，默认同 docker compose logs -f backend
  help            显示本说明
EOF
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  docker-up) exec "$ROOT/run/docker-up.sh" "$@" ;;
  docker-down) exec "$ROOT/run/docker-down.sh" "$@" ;;
  docker-logs) exec "$ROOT/run/docker-logs.sh" "$@" ;;
  help|-h|--help) usage ;;
  *) echo "未知子命令: $cmd" >&2; usage; exit 1 ;;
esac
