LOAD spatial;
.timer on
SELECT '--- A1 direct parent, parents column' AS q;
SELECT count(*) FROM 'collections.parquet' WHERE parents[-1] = 'demografia/e-i';
SELECT '--- A2 direct parent, links column: pick rel=parent, resolve ../catalog.json against href' AS q;
SELECT count(*) FROM 'collections-links.parquet'
WHERE regexp_replace(href, '/[^/]+/[^/]+$', '') || '/catalog.json'
      = 'https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/demografia/e-i/catalog.json'
  AND list_filter(links, l -> l.rel = 'parent')[1].href = '../catalog.json';
SELECT '--- B1 theme (mid-tree), parents column' AS q;
SELECT count(*) FROM 'collections.parquet' WHERE list_contains(parents, 'demografia');
SELECT '--- B2 theme, links column: not expressible; closest is a path-convention match on the resolved parent URL' AS q;
SELECT count(*) FROM 'collections-links.parquet'
WHERE regexp_replace(href, '/[^/]+/[^/]+$', '') LIKE '%/main/demografia/%'
  AND list_filter(links, l -> l.rel = 'parent')[1].href = '../catalog.json';
SELECT '--- B3 catalog documents a links-only client must fetch to learn the theme of every collection' AS q;
SELECT count(DISTINCT regexp_replace(href, '/[^/]+/[^/]+$', '') || '/catalog.json') AS distinct_parent_catalogs FROM 'collections-links.parquet';
