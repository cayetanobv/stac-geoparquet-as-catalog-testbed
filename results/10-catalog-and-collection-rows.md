# Catalog and collection rows

On 2026-11-03 and 2026-11-04 the discussion in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) settled on a new shape. One file holds a row per catalog and a row per collection, with a `type` column and the STAC `links` on every row. `parents` becomes optional, as a list of `{id, href}` on every row. This page builds that shape for the three indexes and compares it with the `{id, href}` files of [page 09](09-parent-hrefs.md), which hold collection rows only. The full column list is [schema 8](../docs/schema.md#8-catalog-and-collection-rows).

Everything on this page was measured on local files on 2026-11-06, with DuckDB 2.0.0, pyarrow 26.0.0 and Python 3.14.9. The files are not uploaded yet, so nothing here is timed over HTTPS.

## The files

`benchmarks/catalog-rows/crawl_tree.py` walks the committed mirrors and writes one line per catalog and per collection. `benchmarks/catalog-rows/build.sql` writes the file and checks its rules first. The files are committed as `indexes/*/collections-catalog-rows.parquet`. The collection rows keep the Hilbert order of the published index, after the catalog rows.

| Index | Catalog rows | Collection rows | Rows with no parent |
|---|---|---|---|
| Berlin | 37 | 371 | 1 |
| Madrid | 177 | 1,964 | 1 |
| Registry | 873 | 5,852 | 86, one per registered catalog |

The registry export gets no row of its own, so the first ancestor of a row is the registered catalog, as in the other indexes. The row counts equal the requests of the JSON walks on pages 01 to 03: 408, 2,141 and 6,725.

Checked in all three files:

- Every row has `type`, `id`, `href`, `links`, `parents`, `description` and `original`.
- Every collection row has `geometry`, `bbox` and `license`. No catalog row has any of them, or a datetime.
- `href` is unique. Every ancestor href in `parents` is the `href` of a catalog row in the same file.
- Joined on `href`, every collection row equals its row in `collections-parents-struct.parquet` in every column the two files share, `original` compared as JSON.

## Same answers

Every query of the [suite](04-query-suite.md), 17 on each index, returns the same result on the new file as on the `{id, href}` file. The runner reads only the collection rows with `scripts/run_suite.py --parents-struct --catalog-rows`.

The theme question of [page 02](02-comunidad-madrid.md), every collection under `demografia` in Madrid, has two answers in the new file. Both give 146:

| Client | Query | Collections | Local time |
|---|---|---|---|
| `parents` | `list_contains(list_transform(parents, lambda p: p.id), 'demografia') AND type = 'Collection'` | 146 | about 0.02 s |
| Links only | `benchmarks/links-catalog-rows/theme.py`: read `type`, `id`, `href` and the parent link, then climb in memory | 146 | 0.035 to 0.050 s |

Without the `type` filter, the `parents` query also returns the 11 catalogs under `demografia`.

## Size on disk and in memory

The in-memory size is what pyarrow holds after it reads the whole file into an Arrow table. A browser client such as DuckDB-Wasm or Arrow JS decodes into the same form. MB is 10⁶ bytes. Script: `benchmarks/catalog-rows/sizes.py`.

| Index | File | Rows | On disk | Uncompressed | In memory | In memory without `original` and `links` |
|---|---|---|---|---|---|---|
| Berlin | `{id, href}`, page 09 | 371 | 0.32 MB | 2.35 MB | 2.44 MB | 0.41 MB |
| Berlin | catalog and collection rows | 408 | 0.37 MB | 2.68 MB | 2.88 MB | 0.44 MB |
| Madrid | `{id, href}`, page 09 | 1,964 | 1.56 MB | 16.07 MB | 17.14 MB | 6.94 MB |
| Madrid | catalog and collection rows | 2,141 | 1.71 MB | 17.71 MB | 19.29 MB | 7.09 MB |
| Registry | `{id, href}`, page 09 | 5,852 | 6.81 MB | 60.73 MB | 62.37 MB | 10.90 MB |
| Registry | catalog and collection rows | 6,725 | 8.74 MB | 76.70 MB | 84.83 MB | 11.50 MB |

The columns that take the space in the registry file:

| Column | On disk | In memory |
|---|---|---|
| `original` | 5.58 MB | 53.41 MB |
| `links` | 1.61 MB | 19.93 MB |
| `keywords` | 0.49 MB | 4.97 MB |
| `description` | 0.51 MB | 2.22 MB |
| `parents` | 0.04 MB | 1.72 MB |
| every other column | 0.49 MB | 2.59 MB |

What it shows:

- **The new shape costs 1.9 MB on disk and 22 MB in memory on the registry.** Almost all of it is `links`. The catalog rows add 873 rows, about 13%.
- **`links` is mostly item links in the registry.** Collections there carry 151,188 `item` links, about 23 times the 6,639 `child` links of the catalogs. Berlin and Madrid have no item links, and `links` takes 0.32 MB and 1.39 MB in memory.
- **`original` decodes to about ten times its size on disk.** In Madrid `keywords` does the same, 0.44 MB on disk and 4.72 MB in memory.
- **Without `original` and `links`, the registry fits in 11.5 MB.** A client that reads only the columns it filters on stays near that, in either shape.
- **`parents` costs 0.04 MB on disk and 1.72 MB in memory** in the registry, the cost of a list of structs in Arrow.

## Not measured yet

- Times and byte ranges over HTTPS. The files have to be uploaded beside the others under `_testbed/` first.
- Readers other than DuckDB and pyarrow.
- A file without the `item` links. The size table suggests it would remove most of the cost of `links` in the registry.
