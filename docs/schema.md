# Collection index schemas

One file, `collections.parquet`, at the catalog root, with one row per collection in the catalog tree. The testbed measures one proposed schema and six variants of it, each built to answer a question raised in [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44) or [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17). Each has its full column list below. In the variants, the columns that differ from the proposed schema are in bold. What each one showed is compared in the [README findings](../README.md#schema-proposals-compared).

| Schema | Question it answers | Files | Measured on |
|---|---|---|---|
| [1. Proposed: `parents` as ids](#1-proposed-parents-as-ids) | The schema under test | `indexes/*/collections.parquet` | every page |
| [2. Links only](#2-links-only) | Can the STAC `parent` and `root` links replace `parents`? | `indexes/comunidad-madrid-datos-abiertos/collections-links.parquet` | [06](../results/06-links-only-variant.md) |
| [3. Links with catalog rows](#3-links-with-catalog-rows) | Can those links resolve inside the file if the catalogs are rows too? | `benchmarks/links-catalog-rows/collections-links-catalogs.parquet` | [08](../results/08-follow-up-checks.md) |
| [4. `parents` as `{id, href}`](#4-parents-as-id-href) | How does a reader outside Portolan find each ancestor's document? | `indexes/*/collections-parents-struct.parquet` | [09](../results/09-parent-hrefs.md) |
| [5. `parents` with `parent_hrefs`](#5-parents-with-parent_hrefs) | The same, without changing `parents` | `indexes/*/collections-parent-hrefs.parquet` | [09](../results/09-parent-hrefs.md) |
| [6. Tree columns, synthetic](#6-tree-columns-synthetic) | Is there a faster tree column than `parents`? | `benchmarks/tree-designs/` | [05](../results/05-tree-designs.md) |
| [7. List shapes, synthetic](#7-list-shapes-synthetic) | How searchable is a list, of strings or of structs? | `benchmarks/list-shapes/` | [07](../results/07-list-shapes.md) |

The row group layouts measured on page 03 and page 08 keep schema 1 and change only how the file is written; they are listed [at the end](#layouts).

## 1. Proposed: `parents` as ids

The schema proposed in [portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44#issuecomment-6145944730) on 2026-10-13. It starts from the `id`, `extents`, `properties` sketch in [stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17#issuecomment-3954676604).

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

### Why `parents` is a list

STAC ids are unique only among siblings, and a collection document links only to its direct parent and to the root. A filter on a catalog in the middle of the tree needs the full chain of ancestor ids. `list_contains(parents, 'transport')` matches a collection at any depth below `transport`. In generic STAC an ancestor can be a catalog or a collection, so the column name does not state the type.

The unique key of a row is `parents` plus `id`.

`parents` holds ids, not URLs. A reader that needs to fetch an ancestor, outside a tree it already knows, needs its href as well. Schemas 4 and 5 carry it; neither is part of the proposal yet.

### How a catalog points at the file

As a Link Object in the catalog's `links` with `rel: "data"` and the Parquet media type, not as an asset, because a STAC Catalog has no `assets` field. The options and the reasoning are in [discovery.md](discovery.md).

### Size

In the Comunidad de Madrid index `original` is 60 percent of the bytes and `keywords` 28 percent. See [results/02-comunidad-madrid.md](../results/02-comunidad-madrid.md). A query engine with column projection can skip both unless the query names them. On files of a few megabytes DuckDB 2.0 reads the whole file anyway, in one request, so the saving shows only on larger files: on the 6.5 MB registry file a query that does not name `original` reads about 1 MB. See [results/04-query-suite.md](../results/04-query-suite.md).

## 2. Links only

`parents` removed, and the collection's STAC links added in the shape the stac-geoparquet items table uses. Raised in stac-geoparquet-spec#17: `parents` repeats what the `parent` and `root` links already carry. Built for Comunidad de Madrid by `benchmarks/links-only/build_links_variant.sql`, 1,964 rows.

| Column | Type | Content |
|---|---|---|
| `id` | string | The collection `id` |
| `href` | string | URL of the `collection.json` |
| `geometry` | GeoParquet geometry, OGC:CRS84 | `extent.spatial.bbox[0]` as a polygon |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | The 2D values of `extent.spatial.bbox[0]` |
| `start_datetime` | timestamp, UTC | `extent.temporal.interval[0][0]`, null when open |
| `end_datetime` | timestamp, UTC | `extent.temporal.interval[0][1]`, null when open |
| `description` | string | The collection `description` |
| `license` | string | The collection `license` |
| `original` | string, JSON | The full collection document |
| `title` | string | The collection `title` |
| `keywords` | list of string | The collection `keywords` |
| **`links`** | **list of struct of `href`, `rel`, `type`, `title`** | **Every link of the collection document, as written there. In this catalog every `parent` link is `../catalog.json`, relative to the row's `href`** |

## 3. Links with catalog rows

Schema 2 plus one row for each catalog in the tree, so that every `parent` link points at a row in the same file. Suggested by [page 05](../results/05-tree-designs.md). Built by `benchmarks/links-catalog-rows/build.py`, 1,964 collection rows and 177 catalog rows.

| Column | Type | Content in a collection row | Content in a catalog row |
|---|---|---|---|
| **`type`** | **string** | **`Collection`** | **`Catalog`** |
| `id` | string | The collection `id` | The catalog `id` |
| `href` | string | URL of the `collection.json` | **URL of the `catalog.json`** |
| `geometry` | GeoParquet geometry, OGC:CRS84 | `extent.spatial.bbox[0]` as a polygon | **null** |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | The 2D values of `extent.spatial.bbox[0]` | **null** |
| `start_datetime` | timestamp, UTC | `extent.temporal.interval[0][0]`, null when open | **null** |
| `end_datetime` | timestamp, UTC | `extent.temporal.interval[0][1]`, null when open | **null** |
| `description` | string | The collection `description` | **null** |
| `license` | string | The collection `license` | **null** |
| `original` | string, JSON | The full collection document | **null** |
| `title` | string | The collection `title` | **null** |
| `keywords` | list of string | The collection `keywords` | **null** |
| **`links`** | **list of struct of `href`, `rel`, `type`, `title`** | **Every link of the collection document** | **Every link of the catalog document** |

## 4. `parents` as `{id, href}`

Schema 1 with each ancestor's href inside `parents`. Raised in stac-geoparquet-spec#17: how does a reader outside Portolan learn where each ancestor is? Built for all three indexes by `scripts/parent_hrefs.sql`, from the crawl that `scripts/crawl.py` or `scripts/crawl_registry.py` writes. Rows, row order, and every other value as in schema 1.

| Column | Type | Content |
|---|---|---|
| `id` | string | The collection `id` |
| **`parents`** | **list of struct of `id`, `href`** | **One element per ancestor, from the root to the direct parent: its id, and the absolute URL of its `catalog.json`** |
| `href` | string | URL of the `collection.json` |
| `geometry` | GeoParquet geometry, OGC:CRS84 | `extent.spatial.bbox[0]` as a polygon |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | The 2D values of `extent.spatial.bbox[0]` |
| `start_datetime` | timestamp, UTC | `extent.temporal.interval[0][0]`, null when open |
| `end_datetime` | timestamp, UTC | `extent.temporal.interval[0][1]`, null when open |
| `description` | string | The collection `description` |
| `license` | string | The collection `license` |
| `original` | string, JSON | The full collection document |
| `title` | string | The collection `title` |
| `keywords` | list of string | The collection `keywords` |

A filter on the ancestors reads the ids with `list_contains(list_transform(parents, lambda p: p.id), 'transport')`.

## 5. `parents` with `parent_hrefs`

Schema 1 unchanged, plus the ancestors' hrefs in a second list. The alternative to schema 4 that keeps `parents` as it is. Built by the same script, from the same crawl.

| Column | Type | Content |
|---|---|---|
| `id` | string | The collection `id` |
| `parents` | list of string | Ancestor ids from the root to the direct parent, in order |
| **`parent_hrefs`** | **list of string** | **The absolute URL of each ancestor's `catalog.json`, in the order of `parents`: `parent_hrefs[i]` is the href of `parents[i]`** |
| `href` | string | URL of the `collection.json` |
| `geometry` | GeoParquet geometry, OGC:CRS84 | `extent.spatial.bbox[0]` as a polygon |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | The 2D values of `extent.spatial.bbox[0]` |
| `start_datetime` | timestamp, UTC | `extent.temporal.interval[0][0]`, null when open |
| `end_datetime` | timestamp, UTC | `extent.temporal.interval[0][1]`, null when open |
| `description` | string | The collection `description` |
| `license` | string | The collection `license` |
| `original` | string, JSON | The full collection document |
| `title` | string | The collection `title` |
| `keywords` | list of string | The collection `keywords` |

A filter on the ancestors stays `list_contains(parents, 'transport')`. If the column were added to the proposal, it would be optional, with the rule that it has the length and order of `parents`.

## 6. Tree columns, synthetic

One file that holds every candidate tree column side by side, so each query uses only its own. A synthetic tree: a root, 50 catalogs, 20 sub-catalogs under each, 5 shards under each of those, and 5 million collections, plus a row for each of the 6,050 catalogs. No geometry or metadata, which the tree question does not read. Built by `benchmarks/tree-designs/build.sql`, sorted in tree order and in random order, 100,000 rows per row group.

| Column | Type | Content in a collection row | Design it serves |
|---|---|---|---|
| **`type`** | **string** | **`Collection`, or `Catalog` in a catalog row** | the recursive query |
| `id` | string | `col-0` to `col-4999999` | all |
| `parents` | list of string | `[root, cat000, sub00, shard0]` | `parents`, as in schema 1 |
| **`p1`**, **`p2`**, **`p3`** | **string** | **The ancestor at each level below the root: `cat000`, `sub00`, `shard0`; in a catalog row, null at its own level and below** | level columns |
| **`parent_path`** | **string** | **The path of the direct parent: `root/cat000/sub00/shard0`** | the recursive query |
| **`path`** | **string** | **The row's own path, ancestor ids joined by `/`: `root/cat000/sub00/shard0/col-0`** | materialized path |
| **`rnd`** | **double** | **A random number, the sort key of the random-order file** | none |

## 7. List shapes, synthetic

One file that stores the same parent fact three ways, to measure how DuckDB filters each. 5 million rows, under 50 catalogs of 20 sub-catalogs each. Built by `benchmarks/list-shapes/build.sql`, 100,000 rows per row group.

| Column | Type | Content | Shape |
|---|---|---|---|
| **`parent_root`** | **string** | **The top-level catalog, `cat000`** | flat string |
| **`parent`** | **string** | **The direct parent, `sub00`** | flat string |
| `id` | string | `col-0` to `col-4999999` | |
| **`parents`** | **list of string** | **`[cat000, sub00]`, without the root** | list of strings |
| **`links`** | **list of struct of `href`, `rel`, `type`, `title`** | **Three links: `root` to `../../catalog.json`, `parent` to `../sub00/catalog.json`, `self` to `./collection.json`** | list of structs, as in schema 2 |

## Layouts

Schema 1, the same columns and rows, written differently. Measured on the registry index.

| Layout | Files | Measured on |
|---|---|---|
| One row group, Hilbert order, DuckDB writer: the published index | `indexes/*/collections.parquet` | every page |
| Three row groups of 2,048 rows, tree order | `indexes/portolan-registry/collections-rg2048.parquet` | [03](../results/03-portolan-registry.md), [04](../results/04-query-suite.md) |
| Twelve row groups of 512 rows, tree order, pyarrow writer | `indexes/portolan-registry/collections-pa512.parquet` | [03](../results/03-portolan-registry.md), [04](../results/04-query-suite.md) |
| Three row groups of 2,048 rows, Hilbert order | `collections-rg2048-hilbert.parquet`, in the bucket, built by `benchmarks/row-groups/build_hilbert.sql` | [08](../results/08-follow-up-checks.md) |
