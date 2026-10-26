-- Rewrite a collection index with 2,048-row row groups, keeping its Hilbert order and the DuckDB writer,
-- so that the row group count is the only difference from collections.parquet.
-- Run in the directory that holds collections.parquet.
LOAD spatial;
SET preserve_insertion_order = true;
SET VARIABLE geo = (SELECT decode(value) FROM parquet_kv_metadata('collections.parquet') WHERE decode(key) = 'geo');
COPY (SELECT * REPLACE (ST_AsWKB(geometry)::BLOB AS geometry) FROM read_parquet('collections.parquet'))
  TO 'collections-rg2048-hilbert.parquet' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 2048, KV_METADATA {geo: getvariable('geo')});
