#!/usr/bin/env bash
# 将 neo4j_seed_graph.cypher 导入 Neo4j（需已 docker compose 启动 neo4j）
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PW="${NEO4J_PASSWORD:-dev032500}"
if docker ps --format '{{.Names}}' | grep -q '^challenge-neo4j$'; then
  docker exec -i challenge-neo4j cypher-shell -u neo4j -p "$PW" < "$DIR/neo4j_seed_graph.cypher"
  echo "OK: graph seed applied (challenge-neo4j)"
else
  echo "ERROR: container challenge-neo4j not running. Start: docker compose --env-file .env.dev up -d neo4j" >&2
  exit 1
fi
