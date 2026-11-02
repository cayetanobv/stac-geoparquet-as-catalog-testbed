-- Check a collection index with a `parents` column against the GeoParquet 1.1 metadata it declares and the keys the schema relies on, in DuckDB alone.
-- Prints one row per check and fails, with a non-zero exit, if any check fails.
-- usage: duckdb -c "SET VARIABLE f='indexes/berlin-geoportal/collections.parquet';" -c ".read scripts/check_index.sql"
.bail on
LOAD spatial;
CREATE TEMP TABLE kv AS
SELECT decode(key) AS k, decode(value) AS v FROM parquet_kv_metadata(getvariable('f'));
SET VARIABLE geo = (SELECT any_value(v) FROM kv WHERE k = 'geo');
SET VARIABLE col = (SELECT json_extract(getvariable('geo'), '$.columns.geometry'));
SET VARIABLE b = (SELECT json_extract(getvariable('col'), '$.bbox')::DOUBLE[]);
-- read the geometry as WKB so a file without geo metadata reaches the checks instead of failing to bind
CREATE TEMP TABLE idx AS SELECT * REPLACE (ST_GeomFromWKB(geometry::BLOB) AS geometry) FROM read_parquet(getvariable('f'));
CREATE TEMP TABLE ext AS
SELECT id, parents, bbox, geometry,
  ST_XMin(geometry) AS x0, ST_YMin(geometry) AS y0, ST_XMax(geometry) AS x1, ST_YMax(geometry) AS y1
FROM idx;
-- a covering with west > east crosses the antimeridian, and build_index.sql splits its geometry into two boxes from -180 to 180
CREATE TEMP TABLE cov AS
SELECT *, abs(bbox.ymin - y0) > 1e-9 OR abs(bbox.ymax - y1) > 1e-9 OR CASE WHEN bbox.xmin > bbox.xmax
  THEN abs(x0 + 180) > 1e-9 OR abs(x1 - 180) > 1e-9 ELSE abs(bbox.xmin - x0) > 1e-9 OR abs(bbox.xmax - x1) > 1e-9 END AS differs
FROM ext;
CREATE TEMP TABLE checks AS
-- two geo keys make readers pick different ones, see docs/method.md
SELECT 'one geo key' AS name, (SELECT count(*) FROM kv WHERE k = 'geo') = 1 AS ok,
  (SELECT count(*) FROM kv WHERE k = 'geo') || ' geo keys' AS detail
UNION ALL SELECT 'geo version 1.1.0', json_extract_string(getvariable('geo'), '$.version') = '1.1.0',
  json_extract_string(getvariable('geo'), '$.version')
UNION ALL SELECT 'primary column is geometry', json_extract_string(getvariable('geo'), '$.primary_column') = 'geometry',
  json_extract_string(getvariable('geo'), '$.primary_column')
UNION ALL SELECT 'encoding WKB', json_extract_string(getvariable('col'), '$.encoding') = 'WKB',
  json_extract_string(getvariable('col'), '$.encoding')
-- an explicit "crs": null means an unknown CRS, and an omitted key means OGC:CRS84
UNION ALL SELECT 'crs omitted or set', coalesce(json_type(getvariable('col'), '$.crs') <> 'NULL', true),
  coalesce(json_type(getvariable('col'), '$.crs'), 'omitted')
UNION ALL SELECT 'bbox covering declared',
  json_extract(getvariable('col'), '$.covering.bbox')::VARCHAR
    = '{"xmin":["bbox","xmin"],"ymin":["bbox","ymin"],"xmax":["bbox","xmax"],"ymax":["bbox","ymax"]}',
  json_extract(getvariable('col'), '$.covering.bbox')::VARCHAR
-- an empty geometry_types list means any type
UNION ALL SELECT 'geometry types declared',
  (SELECT len(json_extract_string(getvariable('col'), '$.geometry_types[*]')) = 0
     OR bool_and(list_contains(json_extract_string(getvariable('col'), '$.geometry_types[*]'), t))
   FROM (SELECT DISTINCT CASE ST_GeometryType(geometry)::VARCHAR WHEN 'POLYGON' THEN 'Polygon' WHEN 'MULTIPOLYGON' THEN 'MultiPolygon'
     ELSE ST_GeometryType(geometry)::VARCHAR END AS t FROM ext)),
  (SELECT string_agg(DISTINCT ST_GeometryType(geometry)::VARCHAR, ', ') FROM ext)
UNION ALL SELECT 'geometry present', (SELECT count(*) FROM ext WHERE geometry IS NULL) = 0,
  (SELECT count(*) FROM ext WHERE geometry IS NULL) || ' null'
-- a collection whose bbox is a point becomes a zero-area polygon, which OGC calls invalid, so it is reported and not failed
UNION ALL SELECT 'geometry valid', (SELECT count(*) FROM ext WHERE NOT ST_IsValid(geometry) AND ST_Area(geometry) > 0) = 0,
  (SELECT count(*) FROM ext WHERE NOT ST_IsValid(geometry) AND ST_Area(geometry) > 0) || ' invalid, '
  || (SELECT count(*) FROM ext WHERE ST_Area(geometry) = 0) || ' zero-area from a point bbox'
UNION ALL SELECT 'covering matches geometry', (SELECT count(*) FROM cov WHERE differs) = 0,
  (SELECT count(*) FROM cov WHERE differs) || ' rows differ, '
  || (SELECT count(*) FROM cov WHERE bbox.xmin > bbox.xmax) || ' cross the antimeridian'
UNION ALL SELECT 'file bbox covers every row',
  (SELECT min(x0) >= getvariable('b')[1] - 1e-9 AND min(y0) >= getvariable('b')[2] - 1e-9
     AND max(x1) <= getvariable('b')[3] + 1e-9 AND max(y1) <= getvariable('b')[4] + 1e-9 FROM ext),
  getvariable('b')::VARCHAR
UNION ALL SELECT 'id and parents present', (SELECT count(*) FROM ext WHERE id IS NULL OR parents IS NULL OR len(parents) = 0) = 0,
  (SELECT count(*) FROM ext WHERE id IS NULL OR parents IS NULL OR len(parents) = 0) || ' rows missing'
-- ids repeat across a federation, so the key is the pair, see results/03
UNION ALL SELECT 'parents and id unique', (SELECT count(*) = count(DISTINCT (parents, id)) FROM ext),
  (SELECT count(*) - count(DISTINCT (parents, id)) FROM ext) || ' duplicates'
UNION ALL SELECT 'row groups', true,
  (SELECT count(DISTINCT row_group_id) FROM parquet_metadata(getvariable('f'))) || ' (one is the measured layout)';
SELECT name, CASE WHEN ok THEN 'pass' ELSE 'FAIL' END AS result, detail FROM checks;
SELECT CASE WHEN count(*) FILTER (ok IS NOT TRUE) = 0 THEN count(*) || ' checks passed'
  ELSE error(count(*) FILTER (ok IS NOT TRUE) || ' of ' || count(*) || ' checks failed') END AS summary FROM checks;
