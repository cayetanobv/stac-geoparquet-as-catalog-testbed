# Resolved asset hrefs and `items_href`

Issue #9 asks what a reader needs to go from the index to data without walking JSON, an agent writing SQL being the hard case. Two gaps show up once a query has found its collections. The asset hrefs inside `original` are mostly relative, and there is no single way to find a collection's `items.parquet`. This page checks where the index should stop, counts both gaps, and builds a variant that closes them.

## Where the index stops

`crawl.py` and `crawl_registry.py` stop at the first Collection. In the registry mirror, 689 `child` links sit on Collections, in 5 catalogs. `scripts/probe_below_collections.py` follows all of them live, through `child` links only.

| Below the 5,852 registry collections, 2026-11-02 | Count |
|---|---|
| Sub-catalogs | 5,254, 689 at depth 1 and 4,565 at depth 2 |
| Collections among them | 0 |
| `item` links in them | 135,796 |
| Fetch errors | 0 |

| Catalog | Documents below its collections |
|---|---|
| ftw-global-data-2e | 3,690 |
| global-data | 1,412 |
| madrid-datos-abiertos | 94 |
| oam-portolan | 46 |
| portolan-nl | 12 |

Every one of them is a zone, grid square or year partition of items. Stopping at the collection loses no collection, and what lies below belongs in `items.parquet`. The collections themselves carry another 151,188 `item` links.

## Relative hrefs

| Where, in the three indexes, 8,187 rows | Shape |
|---|---|
| `href` column | absolute https in every row |
| Asset hrefs in `original` | 32,525, of which 24,714 start with `./`, 4 with `../`, and 7,807 are absolute |
| Links in `original` | all relative |

A reader has to resolve every relative href against the row's `href`. An agent that reads `original` in SQL tends to skip that step and return `./items.parquet`.

## items.parquet

| Registry, 5,852 collections | Count |
|---|---|
| Collections with an `items.parquet` asset | 200, every URL answered 200 |
| Collections with `item` links and no `items.parquet` | 106 |

| Asset key | Roles | Collections |
|---|---|---|
| `geoparquet-items` | `collection-mirror` | 128 |
| `geoparquet-items` | `metadata`, `stac-items` | 23 |
| `mirror` | `collection-mirror`, `metadata` | 18 |
| `geoparquet-items` | `metadata`, `collection-mirror` | 18 |
| `items` | `metadata`, `collection-mirror` | 12 |
| `items` | `data`, `collection-mirror` | 1 |

No key or role finds all 200. The file name `items.parquet` with a Parquet media type does.

## The files

`scripts/agent_columns.sql` adds two columns after `license`, schema 8 in [docs/schema.md](../docs/schema.md#8-resolved-assets-and-items_href). Every other column, the row order and the geo metadata are copied from the committed index.

| Column | Type | Content |
|---|---|---|
| `items_href` | string | Absolute URL of the collection's `items.parquet`, or null |
| `assets` | list of struct of `key`, `href`, `type`, `roles`, `title` | Every asset of `original`, sorted by key, with `href` resolved against the row's `href` |

The resolver is a DuckDB macro. It agrees with Python's `urllib.parse.urljoin` on all 32,525 asset hrefs, and leaves none relative.

| Index | Rows | Assets | With `items_href` | Published | With the columns |
|---|---|---|---|---|---|
| Berlin | 371 | 2,267 | 0 | 312.5 KB | 362.2 KB |
| Madrid | 1,964 | 3,941 | 0 | 1.48 MB | 1.66 MB |
| Registry | 5,852 | 26,317 | 200 | 6.47 MB | 7.07 MB |

All three files have one row group, pass the 14 checks of `scripts/check_index.sql`, and equal the published index in every other column of every row. They are not uploaded, so no query on this page was timed against them over HTTPS.

## From a point to a data file

Two queries, no URL handling. The first reads the local registry variant, the second follows `items_href` over HTTPS.

```sql
SET VARIABLE it = (SELECT items_href FROM 'indexes/portolan-registry/collections-agent.parquet'
  WHERE id = 'utm-21s' AND ST_Intersects(geometry, ST_Point(-58.0, -12.0)));
SELECT id, assets.data.href FROM read_parquet(getvariable('it'))
WHERE ST_Intersects(geometry, ST_Point(-58.0, -12.0));
```

`items_href` is `https://data.source.coop/epoch/forest-typology-2020/south-21-30/utm-21s/items.parquet`, one level deeper than the collection id suggests. The second query returned tiles `raster_21L_20_9_6` and `raster_21L_20_10_6` with absolute COG URLs, in 10.1 s on 2026-11-02 from the test machine. Building that URL by hand from the ids gave a 404.

## Open questions

For radiantearth/stac-geoparquet-spec#17, whether `items_href` should be a column or an agreed asset role, and whether an index should resolve hrefs at all or only state that they resolve against `href`.
