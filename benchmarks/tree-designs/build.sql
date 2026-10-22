-- 5M collections in a 3-level tree: root / cat000..049 / sub00..19 / shard0..4 / collection
CREATE TABLE c AS
SELECT
  'root' AS r,
  'cat' || lpad((i // 100000)::VARCHAR, 3, '0')      AS p1,
  'sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0')  AS p2,
  'shard' || ((i // 1000) % 5)                        AS p3,
  'col-' || i                                          AS id,
  random() AS rnd
FROM range(5000000) t(i);
CREATE TABLE cols AS
SELECT 'Collection' AS type, id, [r, p1, p2, p3] AS parents, p1, p2, p3,
       r || '/' || p1 || '/' || p2 || '/' || p3 AS parent_path,
       r || '/' || p1 || '/' || p2 || '/' || p3 || '/' || id AS path, rnd
FROM c;
-- catalog rows so a recursive query can run inside the same file
CREATE TABLE cats AS
SELECT 'Catalog' AS type, p3 AS id, [r, p1, p2] AS parents, p1, p2, NULL::VARCHAR AS p3,
       r || '/' || p1 || '/' || p2 AS parent_path, r || '/' || p1 || '/' || p2 || '/' || p3 AS path, 0.0 AS rnd
FROM c GROUP BY ALL
UNION ALL SELECT 'Catalog', p2, [r, p1], p1, NULL, NULL, r || '/' || p1, r || '/' || p1 || '/' || p2, 0.0 FROM c GROUP BY ALL
UNION ALL SELECT 'Catalog', p1, [r], NULL, NULL, NULL, r, r || '/' || p1, 0.0 FROM c GROUP BY ALL;
COPY (SELECT * FROM cols UNION ALL SELECT * FROM cats ORDER BY path) TO 'tree_sorted.parquet' (FORMAT PARQUET, ROW_GROUP_SIZE 100000);
COPY (SELECT * FROM cols UNION ALL SELECT * FROM cats ORDER BY rnd)  TO 'tree_random.parquet' (FORMAT PARQUET, ROW_GROUP_SIZE 100000);
SELECT type, count(*) FROM 'tree_sorted.parquet' GROUP BY 1;
