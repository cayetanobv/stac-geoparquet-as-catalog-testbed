#!/usr/bin/env bash
# Build one federated collection index from every catalog in a Portolan registry export.
# usage: scripts/index_registry.sh <registry catalogs.json URL> <mirror dir> <output dir>
set -euo pipefail
REGISTRY="$1"; MIRROR="$2"; OUT="$3"; HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT"
if [ -f "$MIRROR/manifest.json" ]; then
  python3 -I "$HERE/mirror_registry.py" "$REGISTRY" "$MIRROR" retry
else
  python3 -I "$HERE/mirror_registry.py" "$REGISTRY" "$MIRROR"
fi
python3 -I "$HERE/crawl_registry.py" "$MIRROR" "$OUT/collections.jsonl"
( cd "$OUT" && duckdb < "$HERE/build_index.sql" )
gpio check "$OUT/collections.parquet"
