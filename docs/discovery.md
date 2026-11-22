# How a catalog advertises the file

A catalog points at its `collections.parquet` with a link in its `links`:

```json
{
  "rel": "data",
  "href": "./collections.parquet",
  "type": "application/vnd.apache.parquet"
}
```

[stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) agreed on this link, with no fixed file name. A client finds the file by `rel` and `type`, not by its name.

## Why a link and not an asset

The stac-geoparquet spec advertises a collection's `items.parquet` as an asset of the Collection, with the role `collection-mirror`. A STAC 1.1 Catalog has no `assets` field, so a Catalog can name the file only with a link. The Portolan registry export is a Catalog too, so a federated file uses the same link.

## Why `data`

| Option | Meaning | Assessment |
|---|---|---|
| `data` | In OGC API Features and STAC API, the link from a landing page to the list of all collections | The exact meaning, and no new vocabulary. A client that follows `data` on an API reads the static file the same way |
| `alternate` | IANA: another representation of the same resource | The file is not another form of `catalog.json`. Catalogs also use `alternate` for an HTML view |
| A new relation, for example `collection-index` | This file and nothing else | Explicit, but no client knows it |

## Where the fixtures stand

Since 2026-11-05 the CARTO publication pipeline writes a `collections.parquet` in schema 8 beside each CARTO catalog, with this link in the root `catalog.json`. Berlin and Comunidad de Madrid carry it. The registry export at `https://registry.portolan-sdi.org/next/catalogs.json` carries it too. Its file has the columns of schema 8, plus `portolan_registry:id`. The mirrors under `catalogs/` are older and do not carry the link.

## What a client does

1. Open `catalog.json`.
2. Take the link with `rel` equal to `data` and `type` equal to `application/vnd.apache.parquet`.
3. Query that file.
4. When the link is absent, walk the `child` links. Pages 01 to 03 measure that walk.
