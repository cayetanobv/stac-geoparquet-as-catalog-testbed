# The whole Portolan registry as one federated index

Registry export: https://registry.portolan-sdi.org/next/catalogs.json, a STAC Catalog whose child links are the 86 registered catalogs. Mirrored on 2026-10-22, with the failed catalogs retried early on 2026-10-23; the manifest's timestamp is the retry. Index built and checked on 2026-10-23 with gpio 1.7.0. Timings measured on 2026-10-26 with DuckDB 2.0.0 and Python 3.14.9, from the test machine described in [docs/method.md](../docs/method.md). Scripts: `scripts/mirror_registry.py`, `scripts/crawl_registry.py`, `scripts/build_index.sql`.

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

30 collections in 4 catalogs have a bbox with west greater than east, for example UTM zone 1 tiles with `xmin` 179.9 and `xmax` -173.9, and OpenStreetMap extracts. A polygon built from such a bbox with `ST_MakeEnvelope` covers the whole globe in longitude, and 26 of those collections matched a point in Madrid. The builder splits such a bbox into a multipolygon of two boxes at the antimeridian. After the fix the index and the JSON walk agreed on every count, on 2026-10-23. The walk's own bbox test treats a box with west greater than east as empty, so it agrees with the split polygons for points outside those boxes, such as Madrid, and would miss them for a point inside one.

## Question: collections in any catalog whose extent contains a point in Madrid

Point -3.7038, 40.4168. The answer is 2,254 collections in 33 catalogs. 1,964 of them are the whole Comunidad de Madrid catalog, 1,960 of those through the whole-world placeholder extent described on [page 02](02-comunidad-madrid.md). The other 290 come from 32 catalogs.

The walks, at 1, 6 and 16 concurrent requests, one run each. Each cell gives the time with connections reused, then with a new connection for every document.

| Walk | HTTP requests | Hits | Sequential | 6 concurrent | 16 concurrent |
|---|---|---|---|---|---|
| Whole registry | 6,725 | 2,251 | 17 min 48 s / 34 min 36 s | 2 min 49 s / 13 min 43 s | 1 min 31 s / 7 min 22 s |
| Comunidad de Madrid only, known in advance | 2,142 | 1,964 | 3 min 16 s / 11 min 39 s | 50 s / 2 min 55 s | 18 s / 1 min 26 s |

The GeoParquet index, `collections.parquet`, over HTTPS, the same question:

| When in the session | HTTP requests | Bytes read | Cold, 3 runs | Cold wall-clock median | Warm median |
|---|---|---|---|---|---|
| Start, before the walks | 4 (1 HEAD, 3 GET) | 1.0 MB | 1.09, 0.92, 0.99 s | 1.14 s | 0.07 s |
| End, after the walks | 4 (1 HEAD, 3 GET) | 1.0 MB | 0.68, 0.72, 0.66 s | 0.66 s | 0.06 s |

Walks and index queries come from one session on 2026-10-26, 13:30 to 15:40 UTC, the same as pages [01](01-berlin-geoportal.md) and [02](02-comunidad-madrid.md). The index rows are S1 of the [query suite](04-query-suite.md), run at the start and the end of the session. The question is the point alone, so no group applies; the Comunidad de Madrid row shows what one catalog of the federation costs to walk. On 2026-10-26 one catalog, root id `bot-portolan-catalog`, answered its `catalog.json` URL at `data.back-on-track.eu/bot-open-data/` with a redirect to an HTML page. The walk counts that request, records the failure, and finds 2,251 collections instead of 2,254, one request fewer than on 2026-10-23. The 3 missing collections are that catalog's, all of which contain the Madrid point; the index holds them from the mirror of 2026-10-22.

The README headline repeats this question in a shorter session on 2026-10-26, 18:41 to 19:02 UTC, with the whole walk only and reused connections: 15 min 4 s sequential, 2 min 14 s at 6 concurrent, 56 s at 16 concurrent, the same 6,725 requests and 2,251 hits. The index, S1, took 0.59, 0.70, 0.70 s cold at the start and 0.62, 0.60, 0.61 s at the end, with wall-clock medians 0.61 and 0.60 s.

## Other federated queries over HTTPS, one row group, cold process

From the [query suite](04-query-suite.md), measured in an earlier session the same day, 08:20 to 09:47 UTC. Its times are not compared with the walks above.

| Query | Hits | Requests | Bytes read | Cold median of 3 |
|---|---|---|---|---|
| Box test on the `bbox` struct alone | 2,254 | 4 | 110 KB | 0.47 s |
| Keyword `Total` across all catalogs | 261 | 4 | 490 KB | 0.60 s |
| Title substring across all catalogs | 50 | 3 | 110 KB | 0.42 s |
| One catalog by root id, one group through `parents` | 146 | 4 | 1.0 MB | 0.61 s |
| One full `original` document by catalog and id | 1 | 7 | 5.9 MB | 1.41 s |

The full table of sixteen shapes is in the [query suite](04-query-suite.md).

## Row group layout

The one-document lookup reads 5.9 MB because the file is one row group, so `original` is read whole. Three more layouts were measured: two sorted by `parents` and `id`, and one in Hilbert order from [page 08](08-follow-up-checks.md).

| Layout | Row groups | One document: bytes, requests, time | Point query, all catalogs: bytes, requests, time |
|---|---|---|---|
| One row group, Hilbert order | 1 | 5.9 MB, 7, 1.41 s | 1.0 MB, 4, 0.62 s |
| DuckDB writer, 2,048 rows per group, tree order | 3 | 3.3 MB, 9, 0.93 s | 2.8 MB, 8, 1.11 s |
| pyarrow writer, 512 rows per group, tree order | 12 | 4.7 MB, 20, 1.03 s | 5.6 MB, 33, 1.21 s |
| DuckDB writer, 2,048 rows per group, Hilbert order | 3 | 5.3 MB, 10, 1.86 s | 2.8 MB, 8, 0.94 s |

Times are `EXPLAIN ANALYZE` cold medians of 3 from the [query suite](04-query-suite.md), D1 and S1.

Under DuckDB 2.0 one row group is the right layout at this size. Its prefetch cost model coalesces nearby byte ranges into one request, and the files with more row groups read more bytes in more requests for every query. Smaller groups cut the one-document lookup, to 0.93 s against 1.41 s on the 3-group file, and every other query pays for them. The three files differ in more than the row group count: the one-group file is in Hilbert order and the others in tree order, and the 12-group file is written by pyarrow, without DuckDB's bloom filters. The Hilbert-ordered file with three row groups separates the sort order: it reads the same 2.8 MB in 8 requests for the point query as the tree-ordered one, so the cost comes from the row group count. Only the one-document lookup differs, because the order decides which row group holds the document. Under DuckDB 1.5.6 the same variants had cut that lookup from 5.7 MB to 1.1 MB without a penalty elsewhere, so this conclusion is engine specific.

The files are `indexes/portolan-registry/collections.parquet`, `collections-rg2048.parquet`, and `collections-pa512.parquet`, built by `benchmarks/row-groups/`.

## Defects found on the way

Three, all in how the `geo` metadata was written, and none visible to the gpio version first used. The files in this repository were rebuilt after each fix and hold the same rows.

- Reading the `geo` key back from `parquet_kv_metadata()` with a cast to text escapes every quote, and a file written with that string as its `geo` metadata opens with `geometry` as a plain blob. Use `decode(value)`.
- The builder wrote `"crs": null`, which GeoParquet reads as an unknown CRS. The key is now omitted, which means OGC:CRS84.
- The derived files carried two `geo` keys, one passed as `KV_METADATA` and one DuckDB adds for a geometry column when `spatial` is loaded. They are now written from a WKB blob, so only the passed key remains.
