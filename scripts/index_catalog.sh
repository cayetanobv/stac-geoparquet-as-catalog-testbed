#!/usr/bin/env bash
# Build a collection index for one static STAC catalog.
# usage: scripts/index_catalog.sh <root catalog.json URL or local path> <output dir> [public root catalog URL]
set -euo pipefail
ROOT="$1"; OUT="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT"
PUBLIC="${3:-}"
python3 -I "$HERE/crawl.py" "$ROOT" "$OUT/collections.jsonl" $PUBLIC
( cd "$OUT" && duckdb < "$HERE/build_index.sql" )
gpio check "$OUT/collections.parquet"
