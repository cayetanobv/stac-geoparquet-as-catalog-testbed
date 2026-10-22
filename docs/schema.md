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

`scripts/build_index.sql` writes this schema. A bbox with west greater than east crosses the antimeridian, and the builder splits it into a multipolygon of two boxes. The Portolan registry holds 30 such collections, and without the split they match every point on Earth. The file it produces is GeoParquet 1.1 with the `bbox` covering declared, ZSTD compression, rows in Hilbert order on the geometry, and the DuckDB writer's statistics and bloom filters.

## Why `parents` is a list

STAC ids are unique only among siblings, and a collection document links only to its direct parent and to the root. A filter on a catalog in the middle of the tree needs the full chain of ancestor ids. `list_contains(parents, 'transport')` matches a collection at any depth below `transport`. In generic STAC an ancestor can be a catalog or a collection, so the column name does not state the type.

The unique key of a row is `parents` plus `id`.

## Where the bytes go

In the Comunidad de Madrid index, 1.5 MB for 1,964 rows:

| Column | Share |
|---|---|
| `original` | 60% |
| `keywords` | 28% |
| `description` | 5% |
| `href`, `title`, `id` | 2% each |
| `parents` | 0.1% |

A query engine with column projection never reads `original` unless the query names it. The remote measurements confirm it.
