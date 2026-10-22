.timer on
-- Level-1 subtree: everything under cat017 (100 000 rows)
SELECT 'S1 parents list_contains' AS q;        SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND list_contains(parents, 'cat017');
SELECT 'S1 path prefix LIKE' AS q;             SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND path LIKE 'root/cat017/%';
SELECT 'S1 flat level column p1' AS q;         SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND p1 = 'cat017';
-- Level-2 subtree: everything under cat017/sub03 (5 000 rows). sub03 exists under every cat, so the list needs two terms.
SELECT 'S2 parents two list_contains' AS q;    SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND list_contains(parents, 'cat017') AND list_contains(parents, 'sub03');
SELECT 'S2 parents positional' AS q;           SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND parents[2] = 'cat017' AND parents[3] = 'sub03';
SELECT 'S2 path prefix LIKE' AS q;             SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND path LIKE 'root/cat017/sub03/%';
SELECT 'S2 flat level columns' AS q;           SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND p1 = 'cat017' AND p2 = 'sub03';
-- Recursive descent over catalog rows in the same file (what a parent-only design needs)
SELECT 'S1 recursive CTE over catalog rows' AS q;
WITH RECURSIVE sub AS (
  SELECT path FROM read_parquet(getvariable('f')) WHERE type='Catalog' AND path = 'root/cat017'
  UNION ALL
  SELECT t.path FROM read_parquet(getvariable('f')) t JOIN sub ON t.parent_path = sub.path WHERE t.type='Catalog')
SELECT count(*) FROM read_parquet(getvariable('f')) WHERE type='Collection' AND parent_path IN (SELECT path FROM sub);
