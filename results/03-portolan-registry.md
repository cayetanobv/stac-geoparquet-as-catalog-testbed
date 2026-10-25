# The whole Portolan registry as one federated index

Registry export: https://registry.portolan-sdi.org/next/catalogs.json, a STAC Catalog whose child links are the 86 registered catalogs. Mirrored on 2026-10-22, with the failed catalogs retried early on 2026-10-23; the manifest's timestamp is the retry. Measured on 2026-10-23 with DuckDB 2.0.0, Python 3.14.9, and gpio 1.7.0, from the test machine described in [docs/method.md](../docs/method.md). Scripts: `scripts/mirror_registry.py`, `scripts/crawl_registry.py`, `scripts/build_index.sql`.

## The federation

| Property | Value |
|---|---|
| Registered catalogs | 86, all with status `valid` |
| Catalog documents | 873 |
| Collections | 5,852 |
| Hosting providers | 9: Google Cloud Storage, Source Cooperative, Azure Blob, Cloudflare R2, S3, GitHub Pages, and three self-hosted servers |
| Tree depth | 500 collections at depth 1, 3,194 at 2, 2,138 at 3, 20 at 4 |
| Distinct ancestor chains | 790 |
| Mirror time | 282 s for the first pass, 110 s for the 28 catalogs retried |

Source Cooperative and the R2 host answer HTTP 403 to Python's default User-Agent. The mirror script sends a named one.

## Ids collide across catalogs

26 collection ids appear more than once, 55 rows in all. 25 of them, 53 rows, appear in more than one catalog. The other, `post-event-planetscope-2026-10-11`, appears twice inside `disasterdata` under different parents, so even within one catalog `id` alone is not a key. `naturschutz/naturschutzgebiete` exists in Berlin, Bavaria, and North Rhine-Westphalia. `verkehr/behindertenparkplaetze` exists in Berlin, Munich, and Cologne. `places` exists in two unrelated catalogs. The key `parents` plus `id` is unique for all 5,852 rows. No two registered catalogs share a root id, so the first element of `parents` identifies the catalog, which is the federated rule in the schema.

## The index

`indexes/portolan-registry/collections.parquet`

| Property | Value |
|---|---|
| Rows | 5,852 |
| Size | 6.5 MB |
| Row groups | 1 |
| GeoParquet | 1.1 with `bbox` covering, 30 `gpio check` checks passed |

## Antimeridian

30 collections in 4 catalogs have a bbox with west greater than east, for example UTM zone 1 tiles with `xmin` 179.9 and `xmax` -173.9, and OpenStreetMap extracts. A polygon built from such a bbox with `ST_MakeEnvelope` covers the whole globe in longitude, and 26 of those collections matched a point in Madrid. The builder splits such a bbox into a multipolygon of two boxes at the antimeridian. After the fix the index and the JSON walk agree on every count below. The walk's own bbox test treats a box with west greater than east as empty, so it agrees with the split polygons for points outside those boxes, such as Madrid, and would miss them for a point inside one.

## Question: collections in any catalog whose extent contains a point in Madrid

Point -3.7038, 40.4168. The answer is 2,254 collections in 33 catalogs. 1,964 of them are the whole Comunidad de Madrid catalog, 1,960 of those through the whole-world placeholder extent described on [page 02](02-comunidad-madrid.md). The other 290 come from 32 catalogs.

| Method | HTTP requests | Bytes read | Time |
|---|---|---|---|
| JSON walk, whole registry, sequential | 6,726 | | 40 min 41 s |
| JSON walk, whole registry, 16 threads | 6,726 | | 2 min 35 s |
| JSON walk, Comunidad de Madrid only, sequential | 2,142 | | 6 min 17 s |
| JSON walk, Comunidad de Madrid only, 16 threads | 2,142 | | 26 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 4 (1 HEAD, 3 GET) | 1.0 MB | 1.10 s, 1.34 s, 0.77 s |
| Index over HTTPS, warm session | | | 0.07 to 0.09 s |

## Other federated queries over HTTPS, one row group, cold process

| Query | Hits | Requests | Bytes read | Cold median of 3 |
|---|---|---|---|---|
| Box test on the `bbox` struct alone | 2,254 | 4 | 110 KB | 0.53 s |
| Keyword `Total` across all catalogs | 261 | 4 | 490 KB | 0.75 s |
| Title substring across all catalogs | 50 | 3 | 110 KB | 0.52 s |
| One catalog by root id, one group through `parents` | 146 | 4 | 1.0 MB | 0.82 s |
| One full `original` document by catalog and id | 1 | 7 | 5.9 MB | 2.41 s |

The full table of sixteen shapes is in the [query suite](04-query-suite.md).

## Row group layout

The one-document lookup reads 5.9 MB because the file is one row group, so `original` is read whole. Two more layouts, both sorted by `parents` and `id`, were measured.

| Layout | Row groups | One document: bytes, requests, time | Point query, all catalogs: bytes, requests, time |
|---|---|---|---|
| One row group, Hilbert order | 1 | 5.9 MB, 7, 2.4 s | 1.0 MB, 4, 0.85 s |
| DuckDB writer, 2,048 rows per group, tree order | 3 | 3.3 MB, 9, 1.9 s | 2.8 MB, 8, 1.8 s |
| pyarrow writer, 512 rows per group, tree order | 12 | 4.7 MB, 20, 2.1 s | 5.6 MB, 34, 2.3 s |

Under DuckDB 2.0 one row group is the right layout at this size. Its prefetch cost model coalesces nearby byte ranges into one request, and the files with more row groups read more bytes in more requests for every query. Smaller groups cut the one-document lookup only modestly. The three files differ in more than the row group count: the one-group file is in Hilbert order and the others in tree order, and the 12-group file is written by pyarrow, without DuckDB's bloom filters. The comparison does not separate those effects. Under DuckDB 1.5.6 the same variants had cut that lookup from 5.7 MB to 1.1 MB without a penalty elsewhere, so this conclusion is engine specific.

The files are `indexes/portolan-registry/collections.parquet`, `collections-rg2048.parquet`, and `collections-pa512.parquet`, built by `benchmarks/row-groups/`.

## Defects found on the way

Three, all in how the `geo` metadata was written, and none visible to the gpio version first used. The files in this repository were rebuilt after each fix and hold the same rows.

- Reading the `geo` key back from `parquet_kv_metadata()` with a cast to text escapes every quote, and a file written with that string as its `geo` metadata opens with `geometry` as a plain blob. Use `decode(value)`.
- The builder wrote `"crs": null`, which GeoParquet reads as an unknown CRS. The key is now omitted, which means OGC:CRS84.
- The derived files carried two `geo` keys, one passed as `KV_METADATA` and one DuckDB adds for a geometry column when `spatial` is loaded. They are now written from a WKB blob, so only the passed key remains.
