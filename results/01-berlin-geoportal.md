# Berlin Geoportal

Catalog: https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json
Measured on 2026-10-23 with DuckDB 2.0.0, Python 3.14.9, and gpio 1.7.0, from the test machine described in [docs/method.md](../docs/method.md).

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

| Method | HTTP requests | Bytes read | Time |
|---|---|---|---|
| JSON walk, whole tree, sequential | 408 | 2.2 MB | 78 s |
| JSON walk, whole tree, 16 threads | 408 | 2.2 MB | 6.1 s |
| JSON walk, `verkehr` group only, sequential | 21 | | 4.6 s |
| JSON walk, `verkehr` group only, 16 threads | 21 | | 0.8 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 2 (1 HEAD, 1 GET) | 312 KB, the whole file | 0.47 s, 0.48 s, 0.44 s |
| Index over HTTPS, warm session | | | 0.06 to 0.09 s |

DuckDB 2.0 coalesces the byte ranges a query needs when they are close together, and on a file this small that is the whole file in one request. Under DuckDB 1.5.6 the same query made 5 requests for 30 KB and took 0.7 to 1.3 s. Fewer round trips won.

All sixteen shapes of the [query suite](04-query-suite.md) read the same 312 KB. Fifteen take 0.44 to 0.56 s cold. The box test S3 reports 0.00 s because DuckDB answers it while planning, outside the measured time; see [docs/method.md](../docs/method.md).

The point filter is not selective here: 367 of 371 extents contain the city centre, because most extents cover the whole city. The 19 hits are all 19 collections under `verkehr`.

The JSON walk was run with a client that opens a new connection per document, so its times are an upper bound; see [docs/method.md](../docs/method.md).

## Notes

- 328 of 371 collections have exactly 8 keywords. The published documents hold the first 8 tags of the upstream record in alphabetical order, while the upstream CKAN records hold 12 to 49 tags. This is a property of the publishing pipeline, not of the index.
