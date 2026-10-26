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

The walks, at 1, 6 and 16 concurrent requests. Each cell gives the time with connections reused, then with a new connection for every document.

| Walk | HTTP requests | Hits | Sequential | 6 concurrent | 16 concurrent |
|---|---|---|---|---|---|
| Whole tree | 408, 2.2 MB | 367 | 36 s / 1 min 49 s | 7.7 s / 16 s | 3.1 s / 8.2 s |
| `verkehr` group, known in advance | 21 | 19 | 1.9 s / 5.4 s | 0.87 s / 1.4 s | 0.73 s / 1.0 s |
| Group found from the titles of the root's child links, terms `verkehr`, `mobilit` | 32, 1 of them to find | 29 | 2.9 s / 9.3 s | 0.80 s / 1.5 s | 0.80 s / 0.90 s |
| Group found from the title and description of every child catalog, same terms | 88, 37 of them to find | 51 | 6.9 s / 23 s | 1.4 s / 3.4 s | 0.79 s / 2.5 s |

The GeoParquet index, `collections.parquet`, over HTTPS, the same question:

| When in the session | HTTP requests | Bytes read | Cold, 3 runs | Cold wall-clock median | Warm median |
|---|---|---|---|---|---|
| Start, before the walks | 2 (1 HEAD, 1 GET) | 312 KB, the whole file | 0.59, 0.66, 0.62 s | 0.58 s | 0.08 s |
| End, after the walks | 2 (1 HEAD, 1 GET) | 312 KB, the whole file | 0.44, 0.42, 0.43 s | 0.47 s | 0.06 s |

Walks and index queries come from one session on 2026-10-26, 13:30 to 15:40 UTC; see [docs/method.md](../docs/method.md) for the connection modes and the concurrency levels. The index rows are S2 of the [query suite](04-query-suite.md), run at the start and the end of the session. The same query took up to a third less time at the end, so the network shifted during the session. The walk rows are one run each, except the two that find their group, which are medians of 3. Hits count every collection under the walked groups whose extent contains the point, so the two find rows, which walk more groups than `verkehr`, report more than 19.

At this size the index saves requests, not time, against a client that knows the group, reuses connections, and keeps 6 requests in flight: 2 requests against 21, in 0.43 to 0.62 s against 0.87 s. The time gap opens when the client walks one request at a time, opens a new connection per document, or walks the whole tree.

DuckDB 2.0 coalesces the byte ranges a query needs when they are close together, and on a file this small that is the whole file in one request. Under DuckDB 1.5.6, in the earlier pass, the same query made 5 requests for 30 KB.

All sixteen shapes of the [query suite](04-query-suite.md), measured in an earlier session the same day, read the same 312 KB, with wall-clock medians of 0.22 to 0.42 s cold. The box test S3 reports 0.00 s in `EXPLAIN ANALYZE` because DuckDB answers it while planning, outside the measured time; its wall clock is 0.23 s. See [docs/method.md](../docs/method.md).

The point filter is not selective here: 367 of 371 extents contain the city centre, because most extents cover the whole city. The 19 hits are all 19 collections under `verkehr`.

## Finding the group first

A client asked for transport data has to find the group before it can walk only that group. The two find rows above do that from the root: from the titles of its child links, which costs no request beyond the root, or from the title and description of every child catalog, which costs one request per group. With reused connections both take under 1.5 s at 6 or 16 concurrent requests, close to the walk of a known group. The question is what they miss.

By the same terms on title and keywords, 65 collections are about transport, all with extents that contain the point. Matching link titles chooses `verkehr` and `mobilitaet`, which hold 15 of them, 23%. Matching descriptions adds `oepnv` and `strassenbefahrung-punkte` and reaches 34, 52%. The road survey groups `strassenbefahrung-flaechen` and `strassenbefahrung-linien` hold 30 more and match neither way. A STAC Catalog has no extent, so the walk cannot prune by place either. The index answers the whole topic in one query, A6 in `scripts/run_suite.py`, which filters `title` and `keywords` over every collection as `scripts/topic_coverage.sql` does. In a session on 2026-10-26, 18:41 to 19:02 UTC, it was timed against a walk of the whole tree that counts the same topic, `walk_timing.py` with `whole topic=verkehr,mobilit`. Both return 65.

| Method | HTTP requests | Time, connections reused |
|---|---|---|
| JSON walk, whole tree, sequential | 408 | 27 s |
| JSON walk, whole tree, 6 concurrent | 408 | 6.6 s |
| JSON walk, whole tree, 16 concurrent | 408 | 2.9 s |
| Index, A6, cold, 3 runs at the start of the session | 2 (1 HEAD, 1 GET), 312 KB | 0.48, 0.40, 0.41 s; wall-clock median 0.41 s |
| Index, A6, cold, 3 runs at the end of the session | 2 (1 HEAD, 1 GET), 312 KB | 0.42, 0.81, 0.43 s; wall-clock median 0.43 s |
| Index, A6, warm median | | 0.06 s |


## Notes

- 328 of 371 collections have exactly 8 keywords. The published documents hold the first 8 tags of the upstream record in alphabetical order, while the upstream CKAN records hold 12 to 49 tags. This is a property of the publishing pipeline, not of the index.
