#!/usr/bin/env bash
# 生产构建。可通过环境变量覆盖 API（与 vite 一致，前缀 VITE_）
# 示例: VITE_API_BASE_URL=https://api.example.com VITE_WS_URL=wss://api.example.com/ws ./run/frontend-build.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

if [[ ! -d node_modules ]]; then
  echo ">>> npm install …"
  npm install
fi

echo ">>> npm run build …"
npm run build
echo ">>> 产物目录: frontend/dist"
