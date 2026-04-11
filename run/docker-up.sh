#!/usr/bin/env bash
# 在项目根目录执行 docker compose up -d --build
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.dev ]]; then
  echo "错误: 未找到 .env.dev，请从仓库恢复该文件或复制 .env.prod 并改名为 .env.dev" >&2
  exit 1
fi

echo ">>> 启动 Docker Compose（构建镜像）…"
docker compose --env-file .env.dev up -d --build "$@"
echo ">>> 完成。"
echo "    站点（前后端同域）: http://127.0.0.1:8080"
echo "    API 直连 / 文档:     http://127.0.0.1:8000  文档: http://127.0.0.1:8000/docs"
