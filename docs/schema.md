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

## How a catalog points at the file

The upstream spec references `items.parquet` as an Asset Object on the Collection, with the media type `application/vnd.apache.parquet` and the role `collection-mirror`. That form is not available one level up: the STAC 1.1.0 Catalog schema has no `assets` field. So the index is a Link Object in the catalog's `links`:

```json
{
  "rel": "data",
  "href": "./collections.parquet",
  "type": "application/vnd.apache.parquet",
  "title": "Every collection in this catalog, one row each"
}
```

`data` is the relation that OGC API Features defines, and STAC API inherits, for the landing page link to the list of all collections, the `/collections` endpoint. The index is that list as Parquet, so the relation already fits and no new vocabulary is needed. A client that knows only the JSON form filters on `type`, as STAC best practice already asks for hierarchical links. The registry export is itself a STAC Catalog, so a federated index gets the same link from its root.

STAC does not restrict `rel` to a list. Its link specification recommends IANA relation types where possible, and STAC uses its own where IANA has none with the right meaning: `root`, `parent`, `child`, `items`, `data`. `data` is not in the IANA registry. `alternate` is, but it means a substitute representation of the same resource, which the index is not, and catalogs use it for their HTML view. The Portolan incubating draft of 2026-10-13 used `rel: "alternate"` and listed the relation as an open question. `data` is the answer proposed here, with `alternate` acceptable but weaker. A dedicated relation defined by stac-geoparquet would be the most explicit choice and the one no client knows yet.

| | `items.parquet` | `collections.parquet` |
|---|---|---|
| Lives under | a Collection | a Catalog, or a registry root |
| Referenced as | Asset Object, role `collection-mirror` | Link Object, `rel: "data"` |
| One row per | Item of that collection | Collection anywhere in that catalog's tree |
| Why the difference | Collections have `assets` | Catalogs do not |

Generic STAC lets a Collection hold child collections. An index of that subtree could sit as an asset of the Collection and would need a role of its own, distinct from `collection-mirror`. Portolan never needs that form, because a Portolan collection has no child collections.

None of the catalogs measured here carry the link yet. The published root documents of Berlin, Madrid, and the registry do not reference the index, and the mirrors under `catalogs/` are verbatim copies, so the measurements read the files by their known URLs, listed in the README under Upload.

## Why `parents` is a list

STAC ids are unique only among siblings, and a collection document links only to its direct parent and to the root. A filter on a catalog in the middle of the tree needs the full chain of ancestor ids. `list_contains(parents, 'transport')` matches a collection at any depth below `transport`. In generic STAC an ancestor can be a catalog or a collection, so the column name does not state the type.

The unique key of a row is `parents` plus `id`.

## Size

In the Comunidad de Madrid index `original` is 60 percent of the bytes and `keywords` 28 percent. See [results/02-comunidad-madrid.md](../results/02-comunidad-madrid.md). A query engine with column projection reads neither unless the query names it.
