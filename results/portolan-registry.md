# The whole Portolan registry as one federated index

Registry export: https://registry.portolan-sdi.org/next/catalogs.json, a STAC Catalog whose child links are the 86 registered catalogs. Mirrored on 2026-10-22, measured on 2026-10-22 and 2026-10-23 with DuckDB 1.5.6. Scripts: `scripts/mirror_registry.py`, `scripts/crawl_registry.py`, `scripts/build_index.sql`.

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

Source Cooperative and the R2 host answer HTTP 403 to Python's default User-Agent. The mirror script sends a named User-Agent.

## Ids collide across catalogs

26 collection ids appear in more than one catalog, 55 rows in all. `naturschutz/naturschutzgebiete` exists in Berlin, Bavaria, and North Rhine-Westphalia. `verkehr/behindertenparkplaetze` exists in Berlin, Munich, and Cologne. `places` exists in two unrelated catalogs. The key `parents` plus `id` is unique for all 5,852 rows. No two registered catalogs share a root id, so the first element of `parents` identifies the catalog, which is the federated rule in the schema.

## The index

`indexes/portolan-registry/collections.parquet`

| Property | Value |
|---|---|
| Rows | 5,852 |
| Size | 6.5 MB |
| Row groups | 1 |
| GeoParquet | 1.1 with `bbox` covering, 26 `gpio check` checks passed |

## Antimeridian

30 collections in 4 catalogs have a bbox with west greater than east, for example UTM zone 1 tiles with `xmin` 179.9 and `xmax` -173.9, and OpenStreetMap extracts. A polygon built from such a bbox with `ST_MakeEnvelope` covers the whole globe in longitude, and 26 of those collections matched a point in Madrid. The builder now splits such a bbox into a multipolygon of two boxes at the antimeridian. After the fix the index and the JSON walk agree on every count below.

## Question: collections in any catalog whose extent contains a point in Madrid

Point -3.7038, 40.4168. The answer is 2,254 collections in 35 catalogs. Most are global or national datasets.

| Method | HTTP requests | Time |
|---|---|---|
| JSON walk, whole registry, sequential | 6,726 | 43 min 13 s |
| JSON walk, whole registry, 16 threads | 6,726 | 2 min 37 s |
| JSON walk, Comunidad de Madrid only, sequential | 2,142 | 10 min 16 s |
| JSON walk, Comunidad de Madrid only, 16 threads | 2,142 | 30 s |
| Index over HTTPS, cold DuckDB process, 3 runs | 3 (1 HEAD, 2 GET), 122 KB read | 0.54 s, 0.55 s, 0.64 s |
| Index over HTTPS, warm session, runs 1 to 3 | | 0.62 s, 0.25 s, 0.24 s |

## Other federated queries over HTTPS, one row group, cold process

| Query | Hits | Requests | Bytes read | Time, 2 runs |
|---|---|---|---|---|
| Same point, bbox narrower than 1 degree, `id` and catalog returned | 62 in 4 catalogs | 3 | | 0.71 s, 0.83 s |
| Keyword `flood` in `keywords` or `title`, all catalogs | 25 in 9 catalogs | 3 | 574 KB | 0.85 s, 1.07 s |
| One catalog by root id, one group through `parents` | 146 | 3 | 33 KB | 0.60 s, 0.66 s |
| One full `original` document by catalog and id | 1 | 5 | 5.7 MB | 2.98 s, 3.23 s |

Two runs in an earlier series took 5.6 s and 10.2 s while the background JSON walk was competing for the network. They are not in the table.

## Row group layout

The one-document lookup reads 5.7 MB because the file is one row group, so `original` is read whole. Two more layouts, both sorted by `parents` and `id`, change that.

| Layout | Row groups | One document: bytes, requests, time | Point query, all catalogs: requests, time | Keyword query: requests, time |
|---|---|---|---|---|
| One row group, Hilbert order | 1 | 5.7 MB, 5, 3.0 s | 3, 0.75 s | 3, 0.85 to 1.07 s |
| DuckDB writer, 2,048 rows per group, tree order | 3 | 1.1 MB, 7, 1.5 s | 5, 0.8 to 0.9 s | 5, 0.85 to 0.90 s |
| pyarrow writer, 512 rows per group, tree order | 12 | 0.5 MB, 15, 1.0 to 1.3 s | 15, 0.77 to 0.79 s | 15, 0.97 to 1.01 s |

Smaller row groups cut the bytes of a point lookup tenfold, and every query then pays one range request per row group, so the whole-file queries get no faster. At this size, about 2,000 rows per group in tree order is the balance. DuckDB cannot write row groups smaller than 2,048 rows. pyarrow can, and DuckDB prunes on pyarrow's statistics even though DuckDB's `parquet_metadata()` does not display them.

The files are `indexes/portolan-registry/collections.parquet`, `collections-rg2048.parquet`, and `collections-pa512.parquet`.

## A defect found on the way

Reading the `geo` key back from `parquet_kv_metadata()` with a cast to text escapes every quote, and a file written with that string as its `geo` metadata opens with `geometry` as a plain blob. Use `decode(value)`. The derived files in this repository were rebuilt after the fix.
