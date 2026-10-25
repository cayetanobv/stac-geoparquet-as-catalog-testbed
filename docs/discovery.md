# How a catalog advertises the index

The upstream spec says how a Collection advertises its `items.parquet`. It says nothing yet about how a Catalog advertises a `collections.parquet`, and the Portolan incubating draft of 2026-10-13 lists the relation type as an open question. This page records what the STAC specification allows, the options, and the choice this testbed proposes. It changes nothing in the Portolan spec; that is a decision for [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44) and [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17).

## The precedent: `items.parquet` is an asset

The stac-geoparquet spec references a collection's `items.parquet` as an Asset Object on the Collection:

| Field | Value |
|---|---|
| `href` | the Parquet file |
| `type` | `application/vnd.apache.parquet` |
| `roles` | `["collection-mirror"]` |

That works because the Collection object has an `assets` field.

## Why `collections.parquet` cannot be an asset of a catalog

The STAC 1.1.0 Catalog object has no `assets` field. Its JSON schema does not define one. A Catalog has `type`, `stac_version`, `stac_extensions`, `id`, `title`, `description`, and `links`. So the only place a Catalog can name the index is a Link Object in `links`. An extension could add `assets` to Catalog, and none proposes it.

The same holds for a registry. The Portolan registry export at `https://registry.portolan-sdi.org/next/catalogs.json` is a STAC Catalog whose child links are the registered catalogs, so a federated index is advertised from it the same way.

## The link

```json
{
  "rel": "data",
  "href": "./collections.parquet",
  "type": "application/vnd.apache.parquet",
  "title": "Every collection in this catalog, one row each"
}
```

## Which relation type

STAC does not restrict `rel` to a list. Its link specification recommends IANA relation types where possible, and STAC defines its own where IANA has none with the right meaning: `root`, `parent`, `child`, and in STAC API `items`, `data`, `search`, `conformance`. Catalogs in the wild add more; the Berlin fixture carries `pmtiles` and `agents` links.

| Option | Status | Meaning | Assessment |
|---|---|---|---|
| `alternate` | IANA registered | a substitute representation of the same resource | Registered but wrong. The index is not another form of `catalog.json`; it is the list of the catalog's collections. Catalogs also use `alternate` for their HTML view, so a client has to tell the two apart by `type`. This is what the Portolan draft uses today. |
| `data` | OGC API Features relation, inherited by STAC API, not in IANA | the link from a landing page to the list of all collections, the `/collections` endpoint | Exact meaning, no new vocabulary. Every STAC API landing page already carries it. A client that follows `data` on an API reads the static index the same way. The client still filters on `type`, which STAC best practice already asks for hierarchical links. |
| a dedicated relation, for example `collection-index`, defined by stac-geoparquet | would be new | this file and nothing else | The most explicit option and the one no client knows. Worth it only if the community rejects `data`. |

The proposal from this testbed is `data`, with `alternate` acceptable but weaker.

## Side by side

| | `items.parquet` | `collections.parquet` |
|---|---|---|
| Lives under | a Collection | a Catalog, or a registry root |
| Referenced as | Asset Object, role `collection-mirror` | Link Object, `rel: "data"` |
| One row per | Item of that collection | Collection anywhere in that catalog's tree |
| Why the difference | Collections have `assets` | Catalogs do not |

## The nested-collection case

Generic STAC lets a Collection hold child collections. An index of that subtree could sit as an asset of the Collection, and it would then need a role of its own, distinct from `collection-mirror`, which upstream already uses for items. The upstream spec should say which form applies where, or a client has to look in two places. Portolan never needs the asset form, because a Portolan collection has no child collections.

## Where the fixtures stand

None of the catalogs measured here carry the link. The published root documents of Berlin, Comunidad de Madrid, and the registry do not reference the index, and the mirrors under `catalogs/` are verbatim copies of them. The measurements read the files by the URLs listed under Upload in the README. Adding the link is a change to the publishing pipeline of each catalog and to the registry export, not to this repository.

## What a client does with it

1. Open `catalog.json`.
2. Take the link with `rel` equal to `data` and `type` equal to `application/vnd.apache.parquet`.
3. Query that file, with the schema in [schema.md](schema.md).
4. Fall back to walking `child` links when the link is absent.

Step 4 is the whole catalog walk measured in `results/`, which is what the link saves.
