-- Rewrite a collection index in tree order with 2,048-row row groups (the smallest DuckDB writes).
-- Run in the directory that holds collections.parquet. For 512-row groups use build_pa512.py.
LOAD spatial;
SET VARIABLE geo = (SELECT decode(value) FROM parquet_kv_metadata('collections.parquet') WHERE decode(key) = 'geo');
COPY (SELECT * REPLACE (ST_AsWKB(geometry)::BLOB AS geometry) FROM read_parquet('collections.parquet') ORDER BY parents, id)
  TO 'collections-rg2048.parquet' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 2048, KV_METADATA {geo: getvariable('geo')});
