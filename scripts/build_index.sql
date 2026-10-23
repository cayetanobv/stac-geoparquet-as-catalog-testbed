-- Build a collection index GeoParquet (proposal in portolan-spec#44) from collections.jsonl in the cwd.
LOAD spatial;
CREATE TABLE idx AS
WITH src AS (
  SELECT href, parents, doc
  FROM read_json('collections.jsonl', format='newline_delimited',
                 columns={'href':'VARCHAR','parents':'VARCHAR[]','doc':'JSON'})
), ext AS (
  SELECT *,
    json_extract(doc, '$.extent.spatial.bbox[0]')::DOUBLE[] AS bb,
    json_extract_string(doc, '$.extent.temporal.interval[0][0]') AS t0,
    json_extract_string(doc, '$.extent.temporal.interval[0][1]') AS t1
  FROM src
)
SELECT
  json_extract_string(doc, '$.id')                                   AS id,
  parents,
  href,
  -- a bbox with west > east crosses the antimeridian: split it into two boxes
  ST_AsWKB(CASE WHEN bb[1] > bb[3]
    THEN ST_Union(ST_MakeEnvelope(bb[1], bb[2], 180, bb[4]), ST_MakeEnvelope(-180, bb[2], bb[3], bb[4]))
    ELSE ST_MakeEnvelope(bb[1], bb[2], bb[3], bb[4]) END)::BLOB       AS geometry,
  {'xmin': bb[1], 'ymin': bb[2], 'xmax': bb[3], 'ymax': bb[4]}       AS bbox,
  CASE WHEN t0 IS NULL OR t0 = 'null' THEN NULL ELSE t0::TIMESTAMPTZ END AS start_datetime,
  CASE WHEN t1 IS NULL OR t1 = 'null' THEN NULL ELSE t1::TIMESTAMPTZ END AS end_datetime,
  json_extract_string(doc, '$.description')                          AS description,
  json_extract_string(doc, '$.license')                              AS license,
  doc::VARCHAR                                                       AS original,
  json_extract_string(doc, '$.title')                                AS title,
  json_extract(doc, '$.keywords')::VARCHAR[]                         AS keywords
FROM ext
ORDER BY ST_Hilbert(ST_MakeEnvelope(least(bb[1], bb[3]), bb[2], greatest(bb[1], bb[3]), bb[4]));
-- geo metadata with the real extent
CREATE TABLE meta AS SELECT min(bbox.xmin) AS x0, min(bbox.ymin) AS y0, max(bbox.xmax) AS x1, max(bbox.ymax) AS y1 FROM idx;
SET VARIABLE geo = (SELECT '{"version":"1.1.0","primary_column":"geometry","columns":{"geometry":{"encoding":"WKB","geometry_types":["Polygon","MultiPolygon"],"bbox":[' || x0 || ',' || y0 || ',' || x1 || ',' || y1 || '],"covering":{"bbox":{"xmin":["bbox","xmin"],"ymin":["bbox","ymin"],"xmax":["bbox","xmax"],"ymax":["bbox","ymax"]}}}}}' FROM meta);
COPY idx TO 'collections.parquet' (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {geo: getvariable('geo')});
SELECT count(*) AS rows, count(DISTINCT id) AS ids, count(DISTINCT parents) AS chains, max(len(parents)) AS max_depth FROM idx;
