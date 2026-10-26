# Berlin Geoportal

Catalog: https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json
Index built and checked on 2026-10-23 with gpio 1.7.0. Timings measured on 2026-10-26 with DuckDB 2.0.0 and Python 3.14.9, from the test machine described in [docs/method.md](../docs/method.md).

## The catalog

| Property | Value |
|---|---|
| Catalogs | 37, the root and 36 thematic groups |
| Collections | 371, all at depth 2 |
| Collection ids | path shaped, for example `umweltatlas-wasser/flurabstand-2020` |
| Temporal extents | open on both ends in 370 of 371 |

## The index

`indexes/berlin-geoportal/collections.parquet`

| Property | Value |
|---|---|
| Rows | 371 |
| Size | 312 KB |
| Row groups | 1 |
| GeoParquet | 1.1 with `bbox` covering, 30 `gpio check` checks passed |
| Bloom filters | `parents` elements, `license`, `start_datetime`, `end_datetime` |

## Question: collections under `verkehr` whose extent contains the city centre

Point 13.405, 52.52. The answer is 19 collections.

| Method | HTTP requests | Bytes read | Time, connections reused | Time, new connection per document |
|---|---|---|---|---|
| JSON walk, whole tree, sequential | 408 | 2.2 MB | 27 s | 66 s |
| JSON walk, whole tree, 16 threads | 408 | 2.2 MB | 2.5 s | 13 s |
| JSON walk, `verkehr` group only, sequential | 21 | | 1.8 s | 3.4 s |
| JSON walk, `verkehr` group only, 16 threads | 21 | | 0.54 s | 0.71 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 2 (1 HEAD, 1 GET) | 312 KB, the whole file | 0.35 s, 0.25 s, 0.41 s; wall-clock median 0.39 s | |
| Index over HTTPS, warm session | | | 0.06 s | |

The index rows are S2 of the [query suite](04-query-suite.md). Both walks ran in the same session as the index queries; see [docs/method.md](../docs/method.md) for the two connection modes.

At this size the index saves requests, not time, against a client that reuses connections and runs 16 threads: 2 requests against 21, in 0.39 s against 0.54 s. The time gap opens when the client does not know which child leads to the group, or walks one request at a time.

DuckDB 2.0 coalesces the byte ranges a query needs when they are close together, and on a file this small that is the whole file in one request. Under DuckDB 1.5.6, in the earlier pass, the same query made 5 requests for 30 KB.

All sixteen shapes of the [query suite](04-query-suite.md) read the same 312 KB, with wall-clock medians of 0.22 to 0.42 s cold. The box test S3 reports 0.00 s in `EXPLAIN ANALYZE` because DuckDB answers it while planning, outside the measured time; its wall clock is 0.23 s. See [docs/method.md](../docs/method.md).

The point filter is not selective here: 367 of 371 extents contain the city centre, because most extents cover the whole city. The 19 hits are all 19 collections under `verkehr`.


## Notes

- 328 of 371 collections have exactly 8 keywords. The published documents hold the first 8 tags of the upstream record in alphabetical order, while the upstream CKAN records hold 12 to 49 tags. This is a property of the publishing pipeline, not of the index.
