#!/usr/bin/env bash
# 本地启动 Vite（需本机可访问 docker compose 暴露的 8000 端口）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

if [[ ! -f .env.development ]]; then
  echo "提示: 未找到 frontend/.env.development，默认应含 VITE_API_BASE_URL=/api（由 Vite 代理到 127.0.0.1:8000）" >&2
fi

if [[ ! -d node_modules ]]; then
  echo ">>> npm install …"
  npm install
fi

echo ">>> npm run dev …"
exec npm run dev
