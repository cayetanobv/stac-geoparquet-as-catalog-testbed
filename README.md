# STAC GeoParquet as catalog: testbed

Measurements for one proposal: put every catalog and collection of a static STAC catalog in one GeoParquet file at its root. A client then queries one file, and does not walk the tree of JSON documents. The proposal is discussed in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) and [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44).

## Where the discussion stands

| Schema | Status | Pages |
|---|---|---|
| [8. Catalog and collection rows](docs/schema.md#8-catalog-and-collection-rows) | Agreed in #17 on 2026-11-04. The CARTO pipeline writes it for every CARTO catalog since 2026-11-05, and the Portolan registry publishes it | [10](results/10-catalog-and-collection-rows.md), [11](results/11-decomposed-columns.md) |
| [9. Decomposed columns](docs/schema.md#9-decomposed-columns) | Proposed in #17 on 2026-11-18, under discussion | [11](results/11-decomposed-columns.md) |
| [1 to 7](docs/schema.md) | Earlier designs. They answer the questions that led to schema 8 | [01 to 09](results/README.md) |

Schema 8 has one row per catalog and one row per collection, with a `type` column. Search columns hold the first box and the first interval of each extent: `geometry`, `bbox`, `start_datetime` and `end_datetime`. `original` holds the full STAC document as JSON, and `links` holds its links. `parents` is optional and lists the ancestors from the root, as `{id, href}`. A catalog points at the file with a `rel: "data"` link ([docs/discovery.md](docs/discovery.md)).

Schema 9 has one column for each field that STAC defines and an `extra_fields` column for the rest. It has no `original` and no `parents`.

### How we got here

Each schema answers a question from the discussion, in the order the questions came up:

| Schema | Question | What the testbed showed | What it changed |
|---|---|---|---|
| [1](docs/schema.md#1-parents-as-ids) `parents` as ids, one row per collection | Does one file replace the JSON walk? | Yes: 2 to 4 requests against one per document. `list_contains(parents, 'demografia')` finds a whole subtree | The base of every later schema |
| [2](docs/schema.md#2-links-only) STAC `links` instead of `parents` | `parents` repeats the `parent` links. Can the links replace it? | Not in a file of collections only. In Madrid the direct parent finds 0 of the 146 collections under `demografia`. The client needs 178 more requests | Rejected |
| [6](docs/schema.md#6-tree-columns-synthetic) Path string, level columns, recursive query | Is there a faster tree column? | Only at 5 million rows. A path needs an escaping rule, level columns fix the depth, a recursive query is slowest | Not adopted |
| [7](docs/schema.md#7-list-shapes-synthetic) List of strings against list of structs | Is a list of structs harder to filter? | DuckDB does not push the filter into the scan. At real sizes the cost does not show | A list of structs is acceptable |
| [3](docs/schema.md#3-links-with-catalog-rows) Links plus a row per catalog | Can the links resolve inside the file? | Yes, in about the time of `parents`. Each client then climbs the tree in its own code | The catalog rows and the links went into schema 8 |
| [4](docs/schema.md#4-parents-as-id-href) `parents` as `{id, href}` | How does a reader outside Portolan find each ancestor? | Same requests and results as the ids. The hrefs add 21 KB on the registry | This `parents` went into schema 8 |
| [5](docs/schema.md#5-parents-with-parent_hrefs) `parents` plus `parent_hrefs` | The same, without a change to `parents` | Same cost as schema 4 | Not adopted |
| [8](docs/schema.md#8-catalog-and-collection-rows) Catalog and collection rows | One shape for upstream | Same results as schema 4 on all 17 queries. The item links add 1.9 MB on the registry | Agreed in #17, `parents` optional |
| [9](docs/schema.md#9-decomposed-columns) Decomposed columns | Is one column per STAC field better than a copy of the document? | Same search cost as schema 8. Faster for one field, slower for a whole document, smaller, and not exact for 137 registry documents | Under discussion |

The questions still open in #17:

- A copy of the document in `original`, or one column per field with `extra_fields`.
- `parents` as an optional column, or the `links` alone to climb the tree.
- Links to a row of a file with a URL fragment such as `#id=x`. #17 deferred fragments to a later version. Schema 9 needs them, and they need an id that is unique in the file.

## What the measurements show

The main question is the one a user brings to a catalog: which collections about a topic cover this place? The walk opens every JSON document, because the extent is only there. The file answers with one query.

| Catalog | Answer | JSON walk, 6 requests in flight | One query on the file |
|---|---|---|---|
| Berlin Geoportal, 371 collections: transport data at the city centre | 65 collections | 408 requests, 6.6 s | 2 requests, 0.41 to 0.43 s |
| Comunidad de Madrid, 1,964 collections: population data at the city centre | 461 collections | 2,141 requests, 20 s | 2 requests, 0.72 to 0.74 s |
| Portolan registry, 86 catalogs, 5,852 collections: all data at central Madrid | 2,254 collections in 33 catalogs | 6,725 requests, 2 min 14 s | 4 requests, 0.61 to 0.70 s |

Measured on 2026-10-26 with schema 1 and DuckDB 2.0. The query time is the median of three cold runs in a fresh process. One request at a time, the walks take 27 s, 1 min 10 s and 15 min. Pages [01](results/01-berlin-geoportal.md) to [03](results/03-portolan-registry.md) give the details.

| Finding | Pages |
|---|---|
| **One file replaces the walk.** The file needs 2 to 4 requests, and the walk needs one request per document. A walk of one small group with 6 requests in flight is about as fast, but needs 21 requests against 2. | [01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md), [03](results/03-portolan-registry.md) |
| **A walk cannot prune by topic or place.** The groups whose names match the topic hold 23% of the transport collections in Berlin and 28% of the population collections in Madrid. A Catalog has no extent, so a walk cannot prune by place. | [01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md) |
| **A subtree question needs the ancestors in the file.** In Madrid, 146 collections sit under `demografia`, two levels up. The direct parent finds 0 of them. A file with only `parent` links needs 178 more requests. With catalog rows in the file, or with `parents`, it needs none. | [02](results/02-comunidad-madrid.md), [06](results/06-links-only-variant.md), [08](results/08-follow-up-checks.md) |
| **The shape of the tree column does not change the cost at real sizes.** A list of ids, a list of `{id, href}`, or catalog rows with links: same requests, same results. Only at 5 million rows do the shapes differ. | [05](results/05-tree-designs.md), [07](results/07-list-shapes.md), [09](results/09-parent-hrefs.md), [10](results/10-catalog-and-collection-rows.md) |
| **An id does not identify a row in a federated file.** In the registry, 26 collection ids repeat. With catalog rows, 205 rows share one of 81 ids. The ancestors plus the id, or the `href`, identify a row. | [03](results/03-portolan-registry.md), [11](results/11-decomposed-columns.md) |
| **The extents need care.** 30 registry collections have a box across the antimeridian, which must be split in two. 11 have a first box that does not contain their other boxes, against the STAC rule. | [03](results/03-portolan-registry.md), [11](results/11-decomposed-columns.md) |
| **Schemas 8 and 9 cost the same for search.** They differ on the document. Schema 9 reads one field faster and is about 35% smaller. Schema 8 reads a whole document faster and gives it back exactly. | [11](results/11-decomposed-columns.md) |
| **Use one row group at these sizes.** DuckDB 2.0 reads a file of a few MB whole. More row groups cost more on every query except the read of one full document. | [03](results/03-portolan-registry.md), [08](results/08-follow-up-checks.md) |

## Caveats

- **The fixtures are small.** The largest file is 8.7 MB. A file of a hundred thousand collections was not measured.
- **The city catalogs barely test the spatial filter.** 1,960 of the 1,964 Madrid collections have the whole world as their bbox. Only the registry tests spatial selectivity.
- **Times depend on the network of the hour.** The pages compare only times from the same session. The request counts are the durable result.
- **One engine.** All the remote times come from DuckDB 2.0. Under DuckDB 1.5.6 the row group result was the opposite. Other readers were not measured.

## Repository

| Path | Content |
|---|---|
| [`docs/schema.md`](docs/schema.md) | Every schema, with its columns and status |
| [`docs/files.md`](docs/files.md) | Every measured file, local and remote |
| [`docs/method.md`](docs/method.md) | How the times are measured, the sessions, and pitfalls |
| [`docs/discovery.md`](docs/discovery.md) | How a catalog points at the file |
| [`results/`](results/README.md) | One page per measurement |
| `catalogs/` | Metadata mirrors of Berlin, Madrid and the whole registry, without data assets |
| `indexes/` | The files built from the mirrors, as measured |
| `scripts/` | Mirror, build and measure schema 1 |
| `benchmarks/` | Build and measure the other schemas, one folder each |

## Reproduce

Install the [DuckDB CLI](https://duckdb.org/docs/installation/) 2.0 or later and [uv](https://docs.astral.sh/uv/). Then:

```bash
uv sync
duckdb -c "INSTALL spatial; INSTALL httpfs;"
```

The mirrors and the files are committed, so you can skip to "Measure". Each script has a docstring or a comment with its usage and options.

### Mirror and build

```bash
# mirror a catalog, or the whole registry
python3 -I scripts/mirror_catalog.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json catalogs/berlin-geoportal
python3 -I scripts/mirror_registry.py https://registry.portolan-sdi.org/next/catalogs.json catalogs/registry

# schema 1, then schemas 4 and 5 from the same crawl
uv run bash scripts/index_catalog.sh catalogs/berlin-geoportal/catalog.json work/berlin https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json
uv run bash scripts/index_registry.sh https://registry.portolan-sdi.org/next/catalogs.json catalogs/registry work/registry
duckdb -c "SET VARIABLE u='indexes/berlin-geoportal/collections.parquet'; SET VARIABLE j='work/berlin/collections.jsonl'; SET VARIABLE os='work/berlin/collections-parents-struct.parquet'; SET VARIABLE oc='work/berlin/collections-parent-hrefs.parquet';" -c ".read scripts/parent_hrefs.sql"

# schema 8; for the registry: crawl_tree.py registry catalogs/registry OUT_JSONL
mkdir -p work/berlin-tree
python3 -I benchmarks/catalog-rows/crawl_tree.py catalog catalogs/berlin-geoportal https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json work/berlin-tree/tree.jsonl
duckdb -c "SET VARIABLE j='work/berlin-tree/tree.jsonl'; SET VARIABLE o='work/berlin-tree/collections-catalog-rows.parquet';" -c ".read benchmarks/catalog-rows/build.sql"

# schema 9, from the schema 8 file
uv run python -I benchmarks/decomposed/build.py indexes/berlin-geoportal/collections-catalog-rows.parquet work/berlin
```

`index_catalog.sh` and `index_registry.sh` run `scripts/check_index.sql`, which checks the GeoParquet metadata and the keys. `build.sql` checks the rules of schema 8 before it writes the file.

### Measure

| Page | Command |
|---|---|
| 01 to 03, the walk | `python3 -I scripts/walk_timing.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json 13.405 52.52 whole topic=verkehr,mobilit` |
| 01 to 03, the query | `duckdb -c "SET VARIABLE u='https://storage.googleapis.com/carto-open-catalogs/_testbed/berlin-geoportal/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE grp='verkehr';" -c ".read scripts/remote_queries.sql"` |
| 01 and 02, topic under the chosen groups | `scripts/topic_coverage.sql`, usage in its header |
| 04 and 09, the query suite | `uv run python scripts/run_suite.py https://storage.googleapis.com/carto-open-catalogs/_testbed/berlin-geoportal/collections.parquet --lon 13.405 --lat 52.52 --grp verkehr --kw Radverkehr --cat berlin-geoportal --id gruenflaechen/grillflaechen --runs 3` |
| 05 and 07, synthetic | `cd benchmarks/tree-designs && duckdb < build.sql && duckdb -c "SET VARIABLE f='tree_sorted.parquet';" -c ".read queries.sql"`, the same for `list-shapes` |
| 06 | `benchmarks/links-only/` |
| 08 | `benchmarks/links-catalog-rows/` and `benchmarks/row-groups/` |
| 10 | `uv run python benchmarks/catalog-rows/sizes.py indexes/berlin-geoportal/collections-parents-struct.parquet indexes/berlin-geoportal/collections-catalog-rows.parquet` |
| 11 | `benchmarks/decomposed/roundtrip.py`, `sizes.py` and `remote.py berlin 3` |

The walk reads the live catalog, which changes over time. Measure against the published storage, not a local server. [docs/method.md](docs/method.md) gives the reasons.

## License

Apache-2.0 covers the code and the documentation. The metadata under `catalogs/`, and its copies in the `original` column of the files under `indexes/`, belong to the publishers of each catalog and stay under their terms.
