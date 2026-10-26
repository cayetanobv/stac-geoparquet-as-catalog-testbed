# Comunidad de Madrid

Catalog: https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/catalog.json
Largest catalog in the Portolan registry on 2026-10-22. Index built and checked on 2026-10-23 with gpio 1.7.0. Timings measured on 2026-10-26 with DuckDB 2.0.0 and Python 3.14.9, from the test machine described in [docs/method.md](../docs/method.md).

## The catalog

| Property | Value |
|---|---|
| Catalogs | 177 |
| Collections | 1,964 |
| Tree depth | 3 for 1,917 collections, 2 for 47 |
| Shape | root, then a theme such as `demografia`, then an alphabetical shard such as `demografia/e-i` |
| Distinct ancestor chains | 159 |
| Spatial extents | the whole-world bbox `[-180, -90, 180, 90]` on 1,960 collections, a placeholder; a bbox of the region on 4 |

## The index

`indexes/comunidad-madrid-datos-abiertos/collections.parquet`

| Property | Value |
|---|---|
| Rows | 1,964 |
| Size | 1.5 MB |
| Row groups | 1 |
| GeoParquet | 1.1 with `bbox` covering, 30 `gpio check` checks passed |

## Question: collections under the `demografia` theme whose extent contains the city centre

Point -3.7038, 40.4168. The answer is 146 collections, every collection in the theme, because every one carries the whole-world placeholder extent. On this catalog the question tests the tree filter and the request count, not spatial selectivity.

The walks, at 1, 6 and 16 concurrent requests. Each cell gives the time with connections reused, then with a new connection for every document.

| Walk | HTTP requests | Hits | Sequential | 6 concurrent | 16 concurrent |
|---|---|---|---|---|---|
| Whole tree | 2,141, 11 MB | 1,964 | 3 min 9 s / 11 min 10 s | 31 s / 1 min 36 s | 14 s / 41 s |
| `demografia` subtree, known in advance | 159 | 146 | 11 s / 38 s | 2.2 s / 6.4 s | 1.4 s / 2.8 s |
| Group found from the titles of the root's child links, terms `demograf`, `poblacion` | 159, 1 of them to find | 146 | 5.4 s / 40 s | 1.7 s / 5.6 s | 1.1 s / 2.8 s |
| Group found from the title and description of every child catalog, same terms | 180, 23 of them to find | 146 | 11 s / 48 s | 2.6 s / 8.5 s | 1.3 s / 3.8 s |

The index, the same question:

| When in the session | HTTP requests | Bytes read | Cold, 3 runs | Cold wall-clock median | Warm median |
|---|---|---|---|---|---|
| Start, before the walks | 2 (1 HEAD, 1 GET) | 1.4 MB, the whole file | 1.13, 1.07, 1.08 s | 1.08 s | 0.07 s |
| End, after the walks | 2 (1 HEAD, 1 GET) | 1.4 MB, the whole file | 0.56, 0.65, 0.58 s | 0.57 s | 0.06 s |

Walks and index queries come from one session on 2026-10-26, 13:30 to 15:40 UTC, the same as [page 01](01-berlin-geoportal.md). The index rows are S2 of the [query suite](04-query-suite.md), run at the start and the end of the session; the same query took about half the time at the end. The walk rows are one run each, except the two that find their group, which are medians of 3. The noise shows in two walks that make the same 159 requests: run sequentially with reused connections, the one that knew the group took 11 s, early in the session, and the one that found it took 5.4 s.

DuckDB 2.0 reads this file whole in one request. Under 1.5.6, in the earlier pass, the same query read 17 KB in 4 requests.

## Finding the group first

Matching the titles of the root's child links and matching the description of every child catalog both choose `demografia` alone. By the same terms on title and keywords, 461 collections are about population, all with extents that contain the point. `demografia` holds 129 of them, 28%. `salud` holds 206, `empleo` 54, `economia` 48, and six more themes the rest. A walk that finds its group by name is as fast as one that knows it, and answers about a quarter of the topic. The index answers the whole topic in one query, A6 in `scripts/run_suite.py`, which filters `title` and `keywords` over every collection as `scripts/topic_coverage.sql` does. In a short session at 18:10 UTC it returned the 461 collections in the same 2 requests and 1.4 MB as S2, in 0.74 to 1.05 s cold, against 0.72 to 1.16 s for S2 in the same runs; warm median 0.22 s, against 0.06 s for S2, since matching every keyword of every row costs CPU.

## The mid-tree case

The direct parent of every `demografia` collection is one of 11 shard sub-catalogs. A single-value parent column cannot answer the theme question.

| Filter | Collections found |
|---|---|
| `list_contains(parents, 'demografia')` | 146 |
| direct parent equals `demografia` | 0 |
| `id LIKE 'demografia/%'` | 146 |

The path-shaped id works here because Portolan ids are paths. Generic STAC does not guarantee that.

## Where the bytes go

| Column | Compressed size | Share |
|---|---|---|
| `original` | 905 KB | 60% |
| `keywords` | 430 KB | 28% |
| `description` | 79 KB | 5% |
| `href` | 33 KB | 2% |
| `title` | 32 KB | 2% |
| `id` | 29 KB | 2% |
| `parents` | 1 KB | 0.1% |
