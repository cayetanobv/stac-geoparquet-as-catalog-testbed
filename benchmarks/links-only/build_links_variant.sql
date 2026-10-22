LOAD spatial;
CREATE TABLE idx AS
SELECT * EXCLUDE (parents),
  (SELECT list({'href': l->>'href', 'rel': l->>'rel', 'type': l->>'type', 'title': l->>'title'})
     FROM unnest(json_extract(original, '$.links')::JSON[]) AS t(l)) AS links
FROM read_parquet('collections.parquet');
SET VARIABLE geo = (SELECT decode(value) FROM parquet_kv_metadata('collections.parquet') WHERE decode(key) = 'geo');
COPY idx TO 'collections-links.parquet' (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {geo: getvariable('geo')});
DESCRIBE SELECT links FROM 'collections-links.parquet';
