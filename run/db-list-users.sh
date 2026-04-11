#!/usr/bin/env bash
# 列出 PostgreSQL 中 users 表（默认与 .env.dev 中 DB_* 一致；Docker 下容器名 challenge-postgres）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DB_USER="${DB_USER:-user}"
DB_NAME="${DB_NAME:-dbname}"

if docker ps --format '{{.Names}}' | grep -qx 'challenge-postgres'; then
  exec docker exec -i challenge-postgres psql -U "$DB_USER" -d "$DB_NAME" -c \
    "SELECT id, username, role, created_at FROM users ORDER BY id;"
else
  echo "未检测到容器 challenge-postgres；若本机直连 Postgres，请自行执行:" >&2
  echo "  psql -h ... -U $DB_USER -d $DB_NAME -c \"SELECT id, username, role, created_at FROM users ORDER BY id;\"" >&2
  exit 1
fi
