-- Build the catalog-and-collection-rows variant (schema 8 in docs/schema.md) from the JSON lines of crawl_tree.py.
-- One row per catalog and per collection, a `type` column, `links` on every row, and `parents` as a list of {id, href}
-- on every row. Catalog rows fill the fields a STAC Catalog has and leave the collection fields null.
-- Collection rows come in the Hilbert order of the published index, after the catalog rows.
-- usage: duckdb -c "SET VARIABLE j='work/madrid-tree/tree.jsonl'; SET VARIABLE o='work/madrid-tree/collections-catalog-rows.parquet';" -c ".read benchmarks/catalog-rows/build.sql"
.bail on
LOAD spatial;
CREATE TEMP TABLE idx AS
WITH src AS (
  SELECT type, href, parents, doc
  FROM read_json(getvariable('j'), format = 'newline_delimited',
                 columns = {'type': 'VARCHAR', 'href': 'VARCHAR', 'parents': 'STRUCT(id VARCHAR, href VARCHAR)[]', 'doc': 'JSON'})
), ext AS (
  SELECT *,
    CASE WHEN type = 'Collection' THEN json_extract(doc, '$.extent.spatial.bbox[0]')::DOUBLE[] END AS bb,
    CASE WHEN type = 'Collection' THEN json_extract_string(doc, '$.extent.temporal.interval[0][0]') END AS t0,
    CASE WHEN type = 'Collection' THEN json_extract_string(doc, '$.extent.temporal.interval[0][1]') END AS t1
  FROM src
)
SELECT
  type,
  json_extract_string(doc, '$.id')                                   AS id,
  parents,
  href,
  -- a bbox with west > east crosses the antimeridian: split it into two boxes, as build_index.sql does
  ST_AsWKB(CASE WHEN bb[1] > bb[3]
    THEN ST_Union(ST_MakeEnvelope(bb[1], bb[2], 180, bb[4]), ST_MakeEnvelope(-180, bb[2], bb[3], bb[4]))
    ELSE ST_MakeEnvelope(bb[1], bb[2], bb[3], bb[4]) END)::BLOB       AS geometry,
  CASE WHEN bb IS NOT NULL THEN {'xmin': bb[1], 'ymin': bb[2], 'xmax': bb[3], 'ymax': bb[4]} END AS bbox,
  CASE WHEN t0 IS NULL OR t0 = 'null' THEN NULL ELSE t0::TIMESTAMPTZ END AS start_datetime,
  CASE WHEN t1 IS NULL OR t1 = 'null' THEN NULL ELSE t1::TIMESTAMPTZ END AS end_datetime,
  json_extract_string(doc, '$.description')                          AS description,
  CASE WHEN type = 'Collection' THEN json_extract_string(doc, '$.license') END AS license,
  doc::VARCHAR                                                       AS original,
  json_extract_string(doc, '$.title')                                AS title,
  json_extract(doc, '$.keywords')::VARCHAR[]                         AS keywords,
  json_transform(json_extract(doc, '$.links'),
    '[{"href": "VARCHAR", "rel": "VARCHAR", "type": "VARCHAR", "title": "VARCHAR"}]') AS links
FROM ext
ORDER BY type = 'Collection',
  ST_Hilbert(ST_MakeEnvelope(least(bb[1], bb[3]), bb[2], greatest(bb[1], bb[3]), bb[4]));
-- the rules the variant states, checked before the file is written
SELECT
  count(*) FILTER (WHERE type = 'Catalog')                                        AS catalog_rows,
  count(*) FILTER (WHERE type = 'Collection')                                     AS collection_rows,
  count(*) FILTER (WHERE type NOT IN ('Catalog', 'Collection'))                   AS bad_type,
  count(*) FILTER (WHERE id IS NULL OR href IS NULL OR links IS NULL OR parents IS NULL OR original IS NULL) AS missing_common,
  count(*) FILTER (WHERE description IS NULL)                                     AS missing_description,
  count(*) FILTER (WHERE type = 'Collection' AND (geometry IS NULL OR bbox IS NULL OR license IS NULL)) AS collection_missing_required,
  count(*) FILTER (WHERE type = 'Catalog' AND (geometry IS NOT NULL OR bbox IS NOT NULL OR license IS NOT NULL
                   OR start_datetime IS NOT NULL OR end_datetime IS NOT NULL)) AS catalog_with_collection_fields,
  count(*) FILTER (WHERE len(parents) = 0)                                        AS root_rows,
  count(DISTINCT href) = count(*)                                                 AS href_unique
FROM idx;
-- every parent href in `parents` is a catalog row of the same file
SELECT count(*) AS ancestors_not_in_file
FROM (SELECT unnest(parents).href AS h FROM idx) a
WHERE h NOT IN (SELECT href FROM idx WHERE type = 'Catalog');
CREATE TEMP TABLE meta AS SELECT min(bbox.xmin) AS x0, min(bbox.ymin) AS y0, max(bbox.xmax) AS x1, max(bbox.ymax) AS y1 FROM idx;
SET VARIABLE geo = (SELECT '{"version":"1.1.0","primary_column":"geometry","columns":{"geometry":{"encoding":"WKB","geometry_types":["Polygon","MultiPolygon"],"bbox":[' || x0 || ',' || y0 || ',' || x1 || ',' || y1 || '],"covering":{"bbox":{"xmin":["bbox","xmin"],"ymin":["bbox","ymin"],"xmax":["bbox","xmax"],"ymax":["bbox","ymax"]}}}}}' FROM meta);
COPY idx TO (getvariable('o')) (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {geo: getvariable('geo')});
SELECT count(*) AS rows_written FROM read_parquet(getvariable('o'));
