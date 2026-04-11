#!/usr/bin/env bash
# 在已运行的 Redpanda/Kafka 上创建 topics（宿主机执行，默认 localhost:19092）
set -euo pipefail

command -v rpk >/dev/null 2>&1 || { echo "ERROR: rpk not found in PATH"; exit 1; }

BROKERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:19092}"
TOPICS=("data-uploaded" "data-processed" "model-trained" "prediction-done" "events-dlq")

echo "Creating topics on ${BROKERS}..."
for topic in "${TOPICS[@]}"; do
  if rpk -X "brokers=${BROKERS}" topic create "$topic" 2>&1; then
    echo "  ✓ $topic"
  else
    # rpk returns non-zero if topic already exists — check before failing
    if rpk -X "brokers=${BROKERS}" topic list | grep -q "^${topic}"; then
      echo "  ✓ $topic (already exists)"
    else
      echo "  ✗ Failed to create $topic"
      exit 1
    fi
  fi
done
echo "All topics OK on ${BROKERS}"
