LOAD spatial; LOAD httpfs;
.timer on
SELECT '--- A1 direct parent, parents column' AS q;
SELECT count(*) FROM read_parquet('https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet') WHERE parents[-1] = 'demografia/e-i';
SELECT '--- A2 direct parent, links column' AS q;
SELECT count(*) FROM read_parquet('https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections-links.parquet')
WHERE regexp_replace(href, '/[^/]+/[^/]+$', '') || '/catalog.json' = 'https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/demografia/e-i/catalog.json'
  AND list_filter(links, l -> l.rel = 'parent')[1].href = '../catalog.json';
SELECT '--- B1 theme, parents column' AS q;
SELECT count(*) FROM read_parquet('https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet') WHERE list_contains(parents, 'demografia');
SELECT '--- B2 theme, links column (path convention)' AS q;
SELECT count(*) FROM read_parquet('https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections-links.parquet')
WHERE regexp_replace(href, '/[^/]+/[^/]+$', '') LIKE '%/main/demografia/%'
  AND list_filter(links, l -> l.rel = 'parent')[1].href = '../catalog.json';
