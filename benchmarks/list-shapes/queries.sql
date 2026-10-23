.timer on
SELECT 'A flat parent_root' AS q; SELECT count(*) FROM 'big.parquet' WHERE parent_root = 'cat017';
SELECT 'B list_contains parents' AS q; SELECT count(*) FROM 'big.parquet' WHERE list_contains(parents, 'cat017');
SELECT 'B2 parents[1]' AS q; SELECT count(*) FROM 'big.parquet' WHERE parents[1] = 'cat017';
SELECT 'C links list_filter' AS q; SELECT count(*) FROM 'big.parquet' WHERE list_filter(links, lambda l: l.rel = 'parent')[1].href = '../sub03/catalog.json';
SELECT 'D links unnest' AS q; SELECT count(*) FROM (SELECT unnest(links) AS l FROM 'big.parquet') WHERE l.rel='parent' AND l.href='../sub03/catalog.json';
SELECT 'E flat parent (direct)' AS q; SELECT count(*) FROM 'big.parquet' WHERE parent = 'sub03';
SELECT 'F list_contains parents sub03' AS q; SELECT count(*) FROM 'big.parquet' WHERE list_contains(parents, 'sub03');
