# Berlin Geoportal

Catalog: https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json
Measured on 2026-10-22 with DuckDB 1.5.6. Round trip to Google Cloud Storage from the test machine was about 150 ms.

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
| Size | 320 KB |
| Row groups | 1 |
| GeoParquet | 1.1 with `bbox` covering, 26 `gpio check` checks passed |
| Bloom filters | `parents` elements, `license`, `start_datetime`, `end_datetime` |

## Question: collections under `verkehr` whose extent contains the city centre

Point 13.405, 52.52. The answer is 19 collections.

| Method | HTTP requests | Bytes read | Time |
|---|---|---|---|
| JSON walk, whole tree, sequential | 408 | 2.2 MB | 132 s |
| JSON walk, whole tree, 16 threads | 408 | 2.2 MB | 6.1 s |
| JSON walk, `verkehr` group only, sequential | 21 | | 9.7 s |
| JSON walk, `verkehr` group only, 16 threads | 21 | | 0.9 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 5 (1 HEAD, 4 GET) | 30 KB | 0.72 s, 0.76 s, 1.27 s |
| Index over HTTPS, warm session, runs 1 to 3 | | | 0.65 s, 0.43 s, 0.32 s |

Other queries against the remote index, cold process:

| Query | Time |
|---|---|
| Whole tree, count of collections containing the point, one column read | 0.15 to 0.17 s |
| Keyword plus `bbox` struct filter, no geometry read | 0.48 to 0.57 s |
| One full collection document by id | 0.51 to 0.84 s |

The whole-tree count is faster than the subtree query because it reads one column and needs fewer range requests. Query CPU was 15 to 45 ms in every run.

## Notes

- Every collection has exactly 8 keywords in 328 of 371 cases. The published documents hold the first 8 tags of the upstream record in alphabetical order. The upstream CKAN records hold 12 to 49 tags. This is a property of the publishing pipeline, not of the index.
- A rewrite of the file through pyarrow to patch the `geo` metadata dropped the bloom filters that DuckDB had written, and DuckDB's `parquet_metadata()` then reported no string statistics. The final file is written by DuckDB with the `geo` metadata passed as key-value metadata, so statistics and bloom filters stay.
