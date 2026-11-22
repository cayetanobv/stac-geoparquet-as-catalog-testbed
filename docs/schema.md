# Schemas

Every schema the testbed measured. Schemas 8 and 9 are the two in discussion in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17), and their full column lists come first. Schemas 1 to 7 are earlier designs. Each one answered a question that led to schema 8, and each is described by how it differs from schema 1. [files.md](files.md) lists the files of each schema.

| Schema | Status | Question it answers | Pages |
|---|---|---|---|
| [8. Catalog and collection rows](#8-catalog-and-collection-rows) | Agreed in #17 on 2026-11-04. The CARTO pipeline writes it since 2026-11-05 | Which shape does upstream adopt? | [10](../results/10-catalog-and-collection-rows.md), [11](../results/11-decomposed-columns.md) |
| [9. Decomposed columns](#9-decomposed-columns) | Proposed in #17 on 2026-11-18 | Is one column per STAC field better than a copy of the document? | [11](../results/11-decomposed-columns.md) |
| [1. `parents` as ids](#1-parents-as-ids) | The first proposal, 2026-10-13. Replaced by schema 8 | Does one file replace the JSON walk? | [01](../results/01-berlin-geoportal.md) to [04](../results/04-query-suite.md) |
| [2. Links only](#2-links-only) | Rejected | Can the STAC `parent` links replace `parents`? | [06](../results/06-links-only-variant.md) |
| [3. Links with catalog rows](#3-links-with-catalog-rows) | Became part of schema 8 | Can those links resolve inside the file if the catalogs are rows too? | [08](../results/08-follow-up-checks.md) |
| [4. `parents` as `{id, href}`](#4-parents-as-id-href) | Became part of schema 8 | How does a reader outside Portolan find each ancestor? | [09](../results/09-parent-hrefs.md) |
| [5. `parents` with `parent_hrefs`](#5-parents-with-parent_hrefs) | Not adopted | The same, without a change to `parents` | [09](../results/09-parent-hrefs.md) |
| [6. Tree columns, synthetic](#6-tree-columns-synthetic) | Not adopted | Is there a faster tree column than `parents`? | [05](../results/05-tree-designs.md) |
| [7. List shapes, synthetic](#7-list-shapes-synthetic) | No schema, a measurement | How does DuckDB filter a list of strings and a list of structs? | [07](../results/07-list-shapes.md) |

## 8. Catalog and collection rows

One row per catalog and one row per collection of the tree, in one file. A client that reads the search columns finds collections by place, time and topic. A client that reads `original` gets the STAC document back exactly. `parents` is optional. When a file has it, every row has it. Built by `benchmarks/catalog-rows/crawl_tree.py` and `benchmarks/catalog-rows/build.sql`.

| Column | Type | Collection row | Catalog row |
|---|---|---|---|
| `type` | string | `Collection` | `Catalog` |
| `id` | string | The `id` | The `id` |
| `parents` | list of struct of `id`, `href` | One element per ancestor, from the root to the direct parent | The same. An empty list in the root row |
| `href` | string | URL of the `collection.json` | URL of the `catalog.json` |
| `geometry` | GeoParquet geometry, OGC:CRS84 | `extent.spatial.bbox[0]` as a polygon. A box across the antimeridian becomes two | null |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | The 2D values of `extent.spatial.bbox[0]` | null |
| `start_datetime` | timestamp, UTC | `extent.temporal.interval[0][0]`, null when open | null |
| `end_datetime` | timestamp, UTC | `extent.temporal.interval[0][1]`, null when open | null |
| `description` | string | The `description` | The `description` |
| `license` | string | The `license` | null |
| `original` | string, JSON | The full document | The full document |
| `title` | string | The `title` | The `title` |
| `keywords` | list of string | The `keywords` | null. STAC defines `keywords` for a Collection only |
| `links` | list of struct of `href`, `rel`, `type`, `title` | Every link of the document | Every link of the document |

A catalog advertises the file with a link with `rel: "data"` and the Parquet media type. [discovery.md](discovery.md) gives the reasons.

A query that does not name a column does not read it. On the 8.7 MB registry file a search reads about 1 MB, because DuckDB skips `original` and `links`. On files of a few MB, DuckDB 2.0 reads the whole file in one request.

A filter on a subtree reads the ancestor hrefs, `list_contains(list_transform(parents, lambda p: p.href), …)`. The ids alone are not enough in a federated file, because catalogs in different trees can have the same id.

## 9. Decomposed columns

Each field that STAC 1.1 defines for a Catalog or a Collection has a column of its own. Every other top-level field goes into `extra_fields`. The file has no `original`, no `parents` and no `href`. A link to a row of the same file can be written as `#id=<id>`. Built from the schema 8 file by `benchmarks/decomposed/build.py`, with the same rows in the same order.

| Column | Type | Collection row | Catalog row |
|---|---|---|---|
| `type` | string | `Collection` | `Catalog` |
| `stac_version` | string | The `stac_version` | The `stac_version` |
| `stac_extensions` | list of string | The `stac_extensions` | The `stac_extensions` |
| `id` | string | The `id` | The `id` |
| `title` | string | The `title` | The `title` |
| `description` | string | The `description` | The `description` |
| `keywords` | list of string | The `keywords` | The `keywords`, when the catalog has them |
| `license` | string | The `license` | null |
| `providers` | list of struct, keys inferred | The `providers` | The `providers`, when the catalog has them |
| `extent` | struct of `spatial.bbox`, a list of lists of double, and `temporal.interval`, a list of lists of timestamp in UTC | Every box and every interval | null |
| `summaries` | string, JSON | The `summaries` | null |
| `item_assets` | map of string to struct, keys inferred | The `item_assets` | null |
| `assets` | map of string to struct, keys inferred | The `assets` | null |
| `extra_fields` | string, JSON | Every other top-level field, null when there is none | The same |
| `links` | list of struct, keys inferred | Every link of the document | Every link of the document |

"Keys inferred" means that the struct holds every key that occurs in any document of the file, extension keys included. A document that does not have a key gets null for it.

Two more files of each index test variants of the proposal:

- `collections-decomposed-search.parquet` adds the `geometry`, `bbox`, `start_datetime` and `end_datetime` of schema 8 after `id`.
- `collections-decomposed-fragments.parquet` is the search file with each `child`, `parent`, `root` and `collection` link to a row of the same file written as `#id=<id>`. It exists for Berlin and Madrid only. In the registry, 205 rows share one of 81 ids.

## 1. `parents` as ids

The first proposal, made in [portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44#issuecomment-6145944730) on 2026-10-13. Pages 01 to 04 measure it. Built by `scripts/build_index.sql`.

It has one row per collection and no catalog rows. Its columns are those of schema 8 without `type` and `links`, with one difference: `parents` is a list of ancestor ids. A filter on a subtree is `list_contains(parents, 'demografia')`. The unique key of a row is `parents` plus `id`, because STAC ids are unique only among siblings.

## 2. Links only

Schema 1 without `parents`, with the STAC `links` of each collection. In Madrid every `parent` link is `../catalog.json`, so the file holds only the direct parent, as a URL. A subtree question then needs the ancestor catalogs from the network. Built by `benchmarks/links-only/build_links_variant.sql`.

## 3. Links with catalog rows

Schema 2 plus one row for each catalog, with a `type` column, so that every `parent` link points at a row of the same file. The catalog rows have only `type`, `id`, `href` and `links`. Built by `benchmarks/links-catalog-rows/build.py`. Schema 8 keeps the catalog rows and the links, and fills the catalog fields.

## 4. `parents` as `{id, href}`

Schema 1 with `parents` as a list of struct of `id` and `href`: each ancestor's id and the URL of its `catalog.json`. Built by `scripts/parent_hrefs.sql`. Schema 8 uses this `parents`.

## 5. `parents` with `parent_hrefs`

Schema 1 unchanged, plus `parent_hrefs`, a list of the ancestor URLs in the order of `parents`. Built by `scripts/parent_hrefs.sql`. It costs the same as schema 4.

## 6. Tree columns, synthetic

One file of 5 million collections under 6,050 catalogs, in three catalog levels below the root, with every candidate tree column side by side: `parents`, level columns `p1` to `p3`, a materialized `path` string, and a `parent_path` for a recursive query. No geometry or metadata. Built by `benchmarks/tree-designs/build.sql`, sorted in tree order and in random order.

## 7. List shapes, synthetic

One file of 5 million rows that stores the same parent fact as flat strings, as a list of strings and as a list of link structs. Built by `benchmarks/list-shapes/build.sql`.

## Layouts

Schema 1 on the registry, written in different ways. Pages [03](../results/03-portolan-registry.md) and [08](../results/08-follow-up-checks.md) measure them. Every other file in the testbed has one row group.

| Layout | File |
|---|---|
| One row group, Hilbert order on the geometry | `collections.parquet` |
| Three row groups of 2,048 rows, tree order | `collections-rg2048.parquet` |
| Twelve row groups of 512 rows, tree order, pyarrow writer | `collections-pa512.parquet` |
| Three row groups of 2,048 rows, Hilbert order | `collections-rg2048-hilbert.parquet` |
