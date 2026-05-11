#!/bin/bash
set -e

BOOTSTRAP="kafka:29092"

echo "Creating topic order-status-changed..."
kafka-topics --create \
  --if-not-exists \
  --bootstrap-server "$BOOTSTRAP" \
  --replication-factor 1 \
  --partitions 3 \
  --topic order-status-changed

echo "Topics:"
kafka-topics --list --bootstrap-server "$BOOTSTRAP"
