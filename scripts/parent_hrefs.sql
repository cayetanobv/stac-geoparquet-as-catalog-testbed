-- Two variants of a committed index that also carry each ancestor's href, the question in radiantearth/stac-geoparquet-spec#17:
-- `os` gets `parents` as a list of {id, href} instead of ids;
-- `oc` keeps `parents` as ids and adds `parent_hrefs` after it, the href of parents[i] at parent_hrefs[i].
-- Every other column, the row order and the geo metadata are copied unchanged.
-- The hrefs come from collections.jsonl written by crawl.py or crawl_registry.py, joined on the collection's href.
-- usage: duckdb -c "SET VARIABLE u='indexes/berlin-geoportal/collections.parquet'; SET VARIABLE j='work/berlin-ps/collections.jsonl'; SET VARIABLE os='indexes/berlin-geoportal/collections-parents-struct.parquet'; SET VARIABLE oc='indexes/berlin-geoportal/collections-parent-hrefs.parquet';" -c ".read scripts/parent_hrefs.sql"
LOAD spatial;
CREATE TEMP TABLE src AS SELECT * FROM read_parquet(getvariable('u'), file_row_number = true);
CREATE TEMP TABLE crawl AS
SELECT href, parents, parent_hrefs FROM read_json(getvariable('j'), format = 'newline_delimited',
  columns = {'href': 'VARCHAR', 'parents': 'VARCHAR[]', 'parent_hrefs': 'VARCHAR[]'});
-- every row must find its crawl line with the same id chain, or the variants would not be the same index
SELECT count(*) AS rows, count(c.href) AS joined, count(*) FILTER (WHERE c.parents = s.parents) AS same_parents,
       count(*) FILTER (WHERE len(c.parent_hrefs) = len(s.parents)) AS one_href_per_parent
FROM src s LEFT JOIN crawl c USING (href);
CREATE TEMP TABLE idx AS
SELECT s.id, s.parents, c.parent_hrefs, s.href, ST_AsWKB(s.geometry)::BLOB AS geometry, s.bbox, s.start_datetime,
       s.end_datetime, s.description, s.license, s.original, s.title, s.keywords
FROM src s JOIN crawl c ON c.href = s.href AND c.parents = s.parents
ORDER BY s.file_row_number;
SET VARIABLE geo = (SELECT decode(value) FROM parquet_kv_metadata(getvariable('u')) WHERE decode(key) = 'geo');
COPY (SELECT id, list_transform(list_zip(parents, parent_hrefs), lambda p: {'id': p[1], 'href': p[2]}) AS parents,
             * EXCLUDE (id, parents, parent_hrefs) FROM idx)
  TO (getvariable('os')) (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {geo: getvariable('geo')});
COPY idx TO (getvariable('oc')) (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {geo: getvariable('geo')});
SELECT count(*) AS rows_written FROM idx;
