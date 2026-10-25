# Comunidad de Madrid

Catalog: https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/catalog.json
Largest catalog in the Portolan registry on 2026-10-22. Measured on 2026-10-23 with DuckDB 2.0.0, Python 3.14.9, and gpio 1.7.0, from the test machine described in [docs/method.md](../docs/method.md).

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

| Method | HTTP requests | Bytes read | Time |
|---|---|---|---|
| JSON walk, `demografia` subtree, sequential | 159 | | 27 s |
| JSON walk, `demografia` subtree, 16 threads | 159 | | 2.1 s |
| JSON walk, whole tree, 16 threads | 2,141 | 11 MB | 25 s |
| JSON walk, whole tree, sequential | 2,141 | 11 MB | 7 min 2 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 2 (1 HEAD, 1 GET) | 1.4 MB, the whole file | 0.76 s, 0.78 s, 0.74 s |
| Index over HTTPS, warm session | | | 0.06 to 0.11 s |

DuckDB 2.0 reads this file whole in one request. Under 1.5.6 the same query read 17 KB in 4 requests and took 0.5 to 0.6 s. The extra bytes cost about 0.2 s at this round trip and save two requests.

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
