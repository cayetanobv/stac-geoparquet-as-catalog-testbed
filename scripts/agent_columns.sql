-- A variant of a committed index for readers that do not walk JSON, the question in issue #9.
-- `items_href` is the absolute URL of the collection's items.parquet, or null.
-- `assets` is every asset of `original` as {key, href, type, roles, title}, with `href` resolved against the row's `href`.
-- Both go after `license`. Every other column, the row order and the geo metadata are copied unchanged.
-- usage: duckdb -c "SET VARIABLE u='indexes/portolan-registry/collections.parquet'; SET VARIABLE o='indexes/portolan-registry/collections-agent.parquet';" -c ".read scripts/agent_columns.sql"
LOAD spatial;
-- RFC 3986 resolution for the shapes the catalogs use, absolute, root-relative, ./ and up to two ../
CREATE MACRO resolve_href(base, h) AS CASE
  WHEN h IS NULL THEN NULL
  WHEN regexp_matches(h, '^[a-zA-Z][a-zA-Z0-9+.-]*://') THEN h
  WHEN starts_with(h, '/') THEN regexp_extract(base, '^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]+') || h
  ELSE regexp_replace(regexp_replace(regexp_replace(regexp_replace(
         regexp_replace(base, '[^/]*$', '') || h, '/\./', '/', 'g'), '^\./', ''), '/[^/]+/\.\./', '/'), '/[^/]+/\.\./', '/') END;
CREATE TEMP TABLE src AS SELECT * FROM read_parquet(getvariable('u'), file_row_number = true);
CREATE TEMP TABLE a AS
SELECT file_row_number, k AS key, resolve_href(href, v->>'href') AS href, v->>'type' AS type,
       json_extract_string(v, '$.roles[*]') AS roles, v->>'title' AS title
FROM (SELECT file_row_number, href, k, json_extract(original::JSON, '$.assets."' || k || '"') AS v
      FROM (SELECT file_row_number, href, original, unnest(json_keys(original::JSON -> 'assets')) AS k FROM src));
CREATE TEMP TABLE agg AS
SELECT file_row_number,
  list({'key': key, 'href': href, 'type': type, 'roles': roles, 'title': title} ORDER BY key) AS assets,
  -- the items file goes by six key and role combinations in the registry, its file name and media type are the stable part
  any_value(href) FILTER (href LIKE '%/items.parquet' AND type ILIKE '%parquet%') AS items_href
FROM a GROUP BY file_row_number;
CREATE TEMP TABLE idx AS
SELECT s.id, s.parents, s.href, ST_AsWKB(s.geometry)::BLOB AS geometry, s.bbox, s.start_datetime, s.end_datetime,
       s.description, s.license, g.items_href, g.assets, s.original, s.title, s.keywords
FROM src s LEFT JOIN agg g USING (file_row_number) ORDER BY s.file_row_number;
SET VARIABLE geo = (SELECT decode(value) FROM parquet_kv_metadata(getvariable('u')) WHERE decode(key) = 'geo');
COPY idx TO (getvariable('o')) (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {geo: getvariable('geo')});
SELECT count(*) AS rows_written, count(items_href) AS with_items_href, sum(len(assets)) AS assets,
       count(*) FILTER (WHERE list_bool_or(list_transform(assets, lambda x: NOT regexp_matches(x.href, '^https?://')))) AS rows_with_unresolved
FROM idx;
