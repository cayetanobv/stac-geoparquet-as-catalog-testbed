# Collection index schema under test

One file, `collections.parquet`, at the catalog root. One row per collection in the catalog tree. The schema is the one proposed in [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44#issuecomment-6145944730) on 2026-10-13, and it starts from the `id`, `extents`, `properties` sketch in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17#issuecomment-3954676604).

| Column | Type | Requirement | Content |
|---|---|---|---|
| `id` | string | MUST | The collection `id` |
| `parents` | list of string | MAY, MUST in a federated index | Ancestor ids from the root to the direct parent, in order |
| `href` | string | SHOULD, MUST in a federated index | URL of the `collection.json` |
| `geometry` | GeoParquet geometry, OGC:CRS84 | MUST | `extent.spatial.bbox[0]` as a polygon |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | MUST | The 2D values of `extent.spatial.bbox[0]` |
| `start_datetime` | timestamp, UTC | MUST | `extent.temporal.interval[0][0]`, null when open |
| `end_datetime` | timestamp, UTC | MUST | `extent.temporal.interval[0][1]`, null when open |
| `description` | string | MUST | The collection `description` |
| `license` | string | MUST | The collection `license` |
| `original` | string, JSON | MUST | The full collection document |
| `title` | string | SHOULD | The collection `title` |
| `keywords` | list of string | SHOULD | The collection `keywords` |

`scripts/build_index.sql` writes this schema. A bbox with west greater than east crosses the antimeridian, and the builder splits it into a multipolygon of two boxes. The Portolan registry holds 30 such collections, and without the split they match every longitude within their latitude band. The file it produces is GeoParquet 1.1 with the `bbox` covering declared, ZSTD compression, rows in Hilbert order on the geometry, and the DuckDB writer's statistics and bloom filters.

## How a catalog points at the file

As a Link Object in the catalog's `links` with `rel: "data"` and the Parquet media type, not as an asset, because a STAC Catalog has no `assets` field. The options and the reasoning are in [discovery.md](discovery.md).

## Why `parents` is a list

STAC ids are unique only among siblings, and a collection document links only to its direct parent and to the root. A filter on a catalog in the middle of the tree needs the full chain of ancestor ids. `list_contains(parents, 'transport')` matches a collection at any depth below `transport`. In generic STAC an ancestor can be a catalog or a collection, so the column name does not state the type.

The unique key of a row is `parents` plus `id`.

`parents` holds ids, not URLs. A reader that needs to fetch an ancestor, outside a tree it already knows, needs its href as well. Two shapes were measured for that, below; neither is part of the schema under test yet.

## Variants measured

Every other schema the testbed built, how it differs from the one above, and where it is measured. Columns not named are as in the table above.

| Variant | Differs from the schema under test | Raised by | Files | Measured on |
|---|---|---|---|---|
| Links only | No `parents`. A `links` column holds the collection's STAC links as a list of `{href, rel, type, title}`, as in the stac-geoparquet items table. | #17, that `parents` repeats the `parent` and `root` links | `indexes/comunidad-madrid-datos-abiertos/collections-links.parquet` | [06](../results/06-links-only-variant.md) |
| Links with catalog rows | As links only, plus one row per catalog with its `href` and `links`, and a `type` column, `Collection` or `Catalog`. | [Page 05](../results/05-tree-designs.md), to resolve parent links inside the file | `benchmarks/links-catalog-rows/collections-links-catalogs.parquet` | [08](../results/08-follow-up-checks.md) |
| Ancestors as `{id, href}` | `parents` is a list of `{id, href}` structs, the ancestor's id and the absolute URL of its `catalog.json`. | #17, how a reader outside Portolan finds each ancestor | `indexes/*/collections-parents-struct.parquet` | [09](../results/09-parent-hrefs.md) |
| Ancestors with `parent_hrefs` | `parents` unchanged, plus `parent_hrefs`, a list of string with the URL of each ancestor's `catalog.json`, same length and order as `parents`. | This testbed, as the alternative to the struct | `indexes/*/collections-parent-hrefs.parquet` | [09](../results/09-parent-hrefs.md) |
| Tree columns, synthetic | Beside `parents`: a materialized `path` string joined by `/`, level columns `p1`, `p2`, `p3`, and a `parent_path` for a recursive query over catalog rows, plus a `type` column. 5 million rows, no geometry. | This testbed, the alternatives to `parents` | `benchmarks/tree-designs/` | [05](../results/05-tree-designs.md) |
| List shapes, synthetic | The same parent fact as a flat string, a list of strings, and a list of link structs. 5 million rows. | #17, how searchable a list is | `benchmarks/list-shapes/` | [07](../results/07-list-shapes.md) |

Layouts of the schema under test, same columns and rows:

| Layout | Files | Measured on |
|---|---|---|
| One row group, Hilbert order, DuckDB writer: the published index | `indexes/*/collections.parquet` | every page |
| Three row groups of 2,048 rows, tree order | `indexes/portolan-registry/collections-rg2048.parquet` | [03](../results/03-portolan-registry.md), [04](../results/04-query-suite.md) |
| Twelve row groups of 512 rows, tree order, pyarrow writer | `indexes/portolan-registry/collections-pa512.parquet` | [03](../results/03-portolan-registry.md), [04](../results/04-query-suite.md) |
| Three row groups of 2,048 rows, Hilbert order | `collections-rg2048-hilbert.parquet`, in the bucket, built by `benchmarks/row-groups/build_hilbert.sql` | [08](../results/08-follow-up-checks.md) |

What each one showed is in the [README findings](../README.md#schema-proposals-compared).

## Size

In the Comunidad de Madrid index `original` is 60 percent of the bytes and `keywords` 28 percent. See [results/02-comunidad-madrid.md](../results/02-comunidad-madrid.md). A query engine with column projection can skip both unless the query names them. On files of a few megabytes DuckDB 2.0 reads the whole file anyway, in one request, so the saving shows only on larger files: on the 6.5 MB registry file a query that does not name `original` reads about 1 MB. See [results/04-query-suite.md](../results/04-query-suite.md).
