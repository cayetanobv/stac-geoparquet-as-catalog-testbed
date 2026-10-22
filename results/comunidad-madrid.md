# Comunidad de Madrid

Catalog: https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/catalog.json
Largest catalog in the Portolan registry on 2026-10-22. Measured with DuckDB 1.5.6.

## The catalog

| Property | Value |
|---|---|
| Catalogs | 177 |
| Collections | 1,964 |
| Tree depth | 3 for 1,917 collections, 2 for 47 |
| Shape | root, then a theme such as `demografia`, then an alphabetical shard such as `demografia/e-i` |
| Distinct ancestor chains | 159 |
| Spatial extents | the same region-wide bbox on every collection |

## The index

`indexes/comunidad-madrid-datos-abiertos/collections.parquet`

| Property | Value |
|---|---|
| Rows | 1,964 |
| Size | 1.5 MB |
| Row groups | 1 |
| GeoParquet | 1.1 with `bbox` covering, 26 `gpio check` checks passed |

## Question: collections under the `demografia` theme whose extent contains the city centre

Point -3.7038, 40.4168. The answer is 146 collections.

| Method | HTTP requests | Bytes read | Time |
|---|---|---|---|
| JSON walk, `demografia` subtree, sequential | 159 | | 34 s |
| JSON walk, `demografia` subtree, 16 threads | 159 | | 2.7 s |
| JSON walk, whole tree, 16 threads | 2,141 | 11 MB | 30 s |
| JSON walk, whole tree, sequential | 2,141 | 11 MB | 9 min 12 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 4 (1 HEAD, 3 GET) | 17 KB | 0.63 s, 0.52 s, 0.54 s |
| Index over HTTPS, warm session, runs 1 to 3 | | | 0.73 s, 0.17 s, 0.17 s |

Other queries against the remote index, cold process:

| Query | Time |
|---|---|
| Whole tree, count of collections containing the point | 0.17 s |
| `demografia` subtree with `title` returned | 0.64 to 0.77 s |
| One full collection document by id | 0.78 to 0.86 s |

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
