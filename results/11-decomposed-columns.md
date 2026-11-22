# Decomposed columns

On 2026-11-18 a new layout was proposed in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17). Each field that STAC 1.1 defines for a Catalog or a Collection gets a column of its own. One `extra_fields` column holds every other top-level field as JSON text. The file has no copy of the whole document, no `parents` and no `href`. Links that point to a row of the same file can use a URL fragment such as `#id=x`.

This page builds that layout for the three indexes and compares it with [schema 8](../docs/schema.md#8-catalog-and-collection-rows), the catalog and collection rows of [page 10](10-catalog-and-collection-rows.md). The full column list is [schema 9](../docs/schema.md#9-decomposed-columns).

The build, the round trip and the sizes were measured on local files on 2026-11-19. The remote times come from one session on 2026-11-19, 23:12 to 23:16 UTC. The tools were DuckDB 2.0.0, pyarrow 26.0.0 and Python 3.14.9.

## Result

For search, the two layouts cost the same. A query on place, time, topic or subtree reads the same bytes in the same requests, and takes the same time within the noise of one session.

The difference is in the document:

- Schema 9 reads one field faster when schema 8 has that field only inside `original`.
- Schema 8 reads one whole document faster, because it reads one cell and not every column.
- Schema 9 is about 35% smaller on disk and 40% smaller in memory, because it does not store the document twice.
- Schema 8 gives back each document exactly. Schema 9 gives back 9,137 of the 9,274 documents exactly.

## The files

`benchmarks/decomposed/build.py` reads the schema 8 file of each index. Thus the rows, the row order and the search columns are the same as on page 10. The script writes three files for each index:

| File | Content |
|---|---|
| `collections-decomposed.parquet` | The proposal as written |
| `collections-decomposed-search.parquet` | The same, plus `geometry`, `bbox`, `start_datetime` and `end_datetime` from schema 8 |
| `collections-decomposed-fragments.parquet` | The search file, with each `child`, `parent`, `root` and `collection` link to a row of the same file written as `#id=<id>` |

The nested columns use the Arrow type that pyarrow infers from the documents. A struct holds every key that occurs in any document, and a key that a document does not have is null in that row. stac-geoparquet infers the item schema in the same way. The real documents need this. Their links, assets and providers carry extension fields, such as `file:size`, `file:checksum`, `pmtiles:layers` and `alternate`. A struct with only the core fields loses them. `summaries` is JSON text, because its values have no fixed type. The inference worked on all three indexes, with the mixed extensions of the 91 registered catalogs.

The registry has no fragments file. 81 ids occur in more than one row, and 205 of its 6,725 rows have one of these ids. Thus `#id=x` does not point at one row.

The files are committed as `indexes/*/collections-decomposed*.parquet` and are uploaded under `_testbed/`. The [README](../README.md#3-upload) lists their URLs.

## Round trip

`benchmarks/decomposed/roundtrip.py` rebuilds each document from its row and compares it with `original` in schema 8. The script takes every core column that is not null, then every key of `extra_fields`. Inside a struct, it leaves out the null keys.

| Index | Documents | Exact | Differ |
|---|---|---|---|
| Berlin | 408 | 408 | 0 |
| Madrid | 2,141 | 2,141 | 0 |
| Registry | 6,725 | 6,588 | 137 |

The 137 documents differ in two ways:

| Difference | Documents | Example |
|---|---|---|
| An integer comes back as a float | 125 | `item_assets.data.bands[].raster:spatial_resolution` is an integer in some documents and a float in others. The inferred column is a double. The bbox of one extent has the same problem |
| A key with the value `null` is removed | 12 | `assets.*.phl:source_updated: null` and `assets.data.proj:code: null`. A struct column cannot tell a null value from a key that is not there |

The JSON value of each number does not change. A client that compares the documents as text sees a change. A client that compares them as values sees a change only for the 12 null keys.

## Size on disk and in memory

The in-memory size is what pyarrow holds after it reads the file into an Arrow table. The search columns are `type`, `id`, `title`, `keywords`, `geometry`, `bbox`, `start_datetime` and `end_datetime`. MB is 10⁶ bytes. Script: `benchmarks/decomposed/sizes.py`.

| Index | File | On disk | Whole table in memory | Search columns in memory |
|---|---|---|---|---|
| Berlin | schema 8 | 0.37 MB | 2.88 MB | 0.14 MB |
| Berlin | schema 9 with search columns | 0.31 MB | 1.96 MB | 0.14 MB |
| Madrid | schema 8 | 1.71 MB | 19.29 MB | 5.35 MB |
| Madrid | schema 9 with search columns | 1.04 MB | 10.50 MB | 5.35 MB |
| Registry | schema 8 | 8.74 MB | 84.83 MB | 6.59 MB |
| Registry | schema 9 with search columns | 5.60 MB | 51.39 MB | 6.59 MB |
| Registry | schema 9 as proposed | 5.39 MB | 50.49 MB | no search columns |

A client that reads the whole table holds 40% less with schema 9. A client that reads only the search columns holds the same in both layouts. Most of the saving comes from `original`, which repeats every field that other columns of schema 8 also hold.

## Times over HTTPS

`benchmarks/decomposed/remote.py` runs each question on each layout over HTTPS. Each query runs 3 times cold, in a fresh process. The requests and the bytes come from `EXPLAIN ANALYZE`, as in `scripts/run_suite.py`.

| Layout | File |
|---|---|
| 8 | schema 8 |
| 9 | schema 9 as proposed. The place filter reads `extent` |
| 9s | schema 9 with search columns |
| 9f | schema 9 with search columns and fragment links |

### Registry

The registry file is large enough that DuckDB 2.0 reads only the column chunks that a query needs.

| Question | Layout | Result | Requests | Bytes read | Wall median |
|---|---|---|---|---|---|
| Q1 collections whose extent contains central Madrid | 8 | 2,254 | 4 | 1,004 KiB | 0.82 s |
| | 9s | 2,254 | 6 | 1,015 KiB | 0.88 s |
| | 9, on `extent` | 2,265 | 6 | 1,013 KiB | 0.99 s |
| | 9, on `extent`, antimeridian boxes split | 2,265 | 6 | 1,013 KiB | 0.88 s |
| Q2 list of id and title | 8 | 5,852 rows | 4 | 200 KiB | 0.61 s |
| | 9 | 5,852 rows | 5 | 213 KiB | 0.80 s |
| Q3 one whole document | 8, `original` | 1 row | 6 | 5.4 MiB | 1.82 s |
| | 9, every column | 1 row | 16 | 5.2 MiB | 3.03 s |
| Q4 a core field: number of first provider names | 8, from `original` | 377 | 5 | 5.3 MiB | 1.79 s |
| | 9, from `providers` | 377 | 5 | 1,005 KiB | 0.98 s |
| Q5 an extension field: sum of `table:row_count` | 8, from `original` | 1,323,824,933 | 5 | 5.3 MiB | 1.43 s |
| | 9, from `extra_fields` | 1,323,824,933 | 4 | 585 KiB | 0.66 s |

### Berlin and Madrid

DuckDB 2.0 reads these files whole in 2 requests. The bytes read are the file size, and every query on a layout reads the same bytes. All layouts give the same results: 65 and 461 for Q1, 19 and 146 for Q6. The medians stay between 0.42 and 0.50 s in Berlin, and between 0.54 and 0.97 s in Madrid. Three single runs in Madrid took 1.45 to 2.09 s, in both layouts. The full tables are in `work/decomposed/remote.md` after a run.

| Question | Berlin, 8 | Berlin, 9 | Madrid, 8 | Madrid, 9 |
|---|---|---|---|---|
| Q1 place and topic | 0.43 s | 0.43 s, 0.50 s with search columns | 0.97 s | 0.78 s, 0.72 s with search columns |
| Q3 one whole document | 0.44 s | 0.44 s | 0.57 s | 0.56 s |
| Q5 an extension field | 0.44 s | 0.43 s | 0.67 s | 0.56 s |
| Q6 collections anywhere under one group | 0.43 s, `parents` | 0.45 s, recursive query on `#id=` links | 0.63 s, `parents` | 0.62 s, recursive query on `#id=` links |

## Search on `extent` alone

On the registry, the filter on `extent` finds 11 collections that `geometry` does not find. The split at the antimeridian does not change the count. The 11 collections are `building`, `segment`, `land_cover`, `water`, `connector`, `land`, `infrastructure`, `division_area`, `place`, `land_use` and `address`. Each one has 8 to 512 boxes. In each one, the first box does not contain all the other boxes. STAC requires the first box to contain them.

`geometry` and `bbox` come from the first box, so they miss these collections. `extent` keeps every box, so it finds them. The query on `extent` is a list filter with a lambda. It is not a GeoParquet geometry column, so it cannot use the GeoParquet row-group statistics.

## Tree walk with fragments

In the fragments file, the question "every collection anywhere under one group" is a recursive query on `id` and the `parent` links:

```sql
WITH RECURSIVE t AS MATERIALIZED (
  SELECT id, type, list_transform(list_filter(links, lambda l: l.rel = 'parent'), lambda l: l.href) AS up
  FROM read_parquet('collections-decomposed-fragments.parquet')),
sub(id) AS (SELECT 'demografia' UNION SELECT t.id FROM t JOIN sub ON list_contains(t.up, '#id=' || sub.id))
SELECT count(*) FROM t JOIN sub USING (id) WHERE t.type = 'Collection';
```

It gives 146 in Madrid and 19 for `verkehr` in Berlin, the same as `parents`, in the same time. The query needs an id that is unique in the file. Without fragments, a client must match each link `href` to the URL of a row. Schema 9 has no `href` column, and only 51 of the 6,725 registry documents have a `self` link.

## What it shows

- **For search, the layout does not change the cost.** The place, topic, list and subtree queries read the same bytes in both layouts.
- **The full copy costs time only when a query reads it.** DuckDB reads `original` only for Q3, Q4 and Q5. On the registry, schema 9 answers Q4 and Q5 in about half the time, because `providers` and `extra_fields` are smaller than `original`. A `providers` column in schema 8 would probably give the same gain for Q4. This page does not measure it.
- **The full copy is faster for a whole document.** Schema 9 reads each column chunk of the row group for one row: 16 requests against 6.
- **The full copy is exact.** Schema 9 changes 137 registry documents. The cause is the inferred types and the null keys, not a lost field.
- **Fragments need ids that are unique in the file.** In the registry, 205 rows share one of 81 ids. A federated file needs another way to point at a row.
- **The search columns trust the first box.** 11 registry collections have a first box that does not contain the others. `extent` finds them, and `geometry` from the first box does not.

## Not measured yet

- Readers other than DuckDB over HTTPS, such as pyarrow and hyparquet.
- `extra_fields` as Variant instead of JSON text.
- Files without the `item` links.
- A link scheme for a federated file whose ids repeat.
