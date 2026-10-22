-- Queries against a collection index over HTTPS.
-- usage: duckdb -c "SET VARIABLE u='https://host/catalog/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE grp='verkehr';" -c ".read scripts/remote_queries.sql"
LOAD spatial; LOAD httpfs;
.timer on
SELECT '--- Q1 subtree of grp, point inside extent' AS q;
SELECT count(*) AS hits FROM read_parquet(getvariable('u'))
WHERE list_contains(parents, getvariable('grp'))
  AND ST_Intersects(geometry, ST_Point(getvariable('lon'), getvariable('lat')));
SELECT '--- Q2 whole tree, point inside extent' AS q;
SELECT count(*) AS hits FROM read_parquet(getvariable('u'))
WHERE ST_Intersects(geometry, ST_Point(getvariable('lon'), getvariable('lat')));
SELECT '--- Q3 subtree of grp with title and href returned' AS q;
SELECT id, title, href FROM read_parquet(getvariable('u')) WHERE list_contains(parents, getvariable('grp')) ORDER BY id LIMIT 5;
SELECT '--- Q4 HTTP requests for Q1' AS q;
EXPLAIN ANALYZE SELECT count(*) FROM read_parquet(getvariable('u'))
WHERE list_contains(parents, getvariable('grp'))
  AND ST_Intersects(geometry, ST_Point(getvariable('lon'), getvariable('lat')));
