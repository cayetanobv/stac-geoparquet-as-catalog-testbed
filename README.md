# STAC GeoParquet as catalog: testbed

Experiments behind a proposal to describe a whole STAC catalog, every collection in its tree, in one GeoParquet file at the catalog root. The proposal is under discussion in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) and [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44).

The question the testbed answers: can one Parquet file replace the walk through catalog JSON documents that a client does today, and which column shape for the catalog tree makes that file fast to query?

## What is here

| Path | Content |
|---|---|
| `docs/schema.md` | The collection index schema under test |
| `scripts/` | Mirror a catalog's metadata, build an index from it, and time queries against it |
| `catalogs/` | Metadata mirrors of the test catalogs and of every catalog in the Portolan registry: `catalog.json` and `collection.json` only, no data assets |
| `indexes/` | Indexes built from the two test catalogs and from the whole registry on 2026-10-22 |
| `results/` | Measurements and what they show, including a sixteen-query suite in `results/query-suite.md` |
| `benchmarks/` | Synthetic benchmarks of column shapes at 5 million rows |

## Why this question

Every results page asks the same question: collections under one group of the tree whose extent contains a point. It is what an SDI user asks, "what transport data is there for this place", and it is the smallest query that touches everything under test. The group filter exercises the `parents` column, which is the point debated upstream, and in Madrid it is a mid-tree case that a direct-parent column cannot answer. The point filter exercises the GeoParquet side, geometry and `bbox` covering. And because the extent lives inside each `collection.json`, a client without the index has to open every collection document to answer it, so the walk pays its real cost. Both methods return the same count, which is how the antimeridian defect was caught. `results/query-suite.md` adds fifteen more query shapes for comparison.

## Results in one table

Two real catalogs, both published by [CARTO's Portolan mirrors](https://github.com/portolan-sdi/portolan-registry). The question in each case is "collections under one group of the tree whose extent contains a point".

| Catalog | Collections | Tree depth | JSON walk, sequential | JSON walk, 16 threads | One query on the index over HTTPS |
|---|---|---|---|---|---|
| Berlin Geoportal | 371 | 2 | 132 s, 408 requests | 6.1 s | 0.7 to 1.3 s, 5 requests |
| Comunidad de Madrid | 1,964 | 3 | 9 min 12 s, 2,141 requests | 30 s | 0.5 to 0.6 s, 4 requests |
| The whole Portolan registry, 86 catalogs | 5,852 | 4 | 43 min 13 s, 6,726 requests | 2 min 37 s | 0.5 to 0.6 s, 3 requests |

For the registry the question is the point alone, across every catalog. The index query reads 17 to 122 KB of the file. Its time is HTTP round trips, not bytes or rows. See [results/berlin-geoportal.md](results/berlin-geoportal.md), [results/comunidad-madrid.md](results/comunidad-madrid.md), and [results/portolan-registry.md](results/portolan-registry.md). The registry page also covers id collisions across catalogs, antimeridian bboxes, and row group layout.

The tree is stored as a `parents` column, a list of ancestor ids from the root to the direct parent. In the Madrid catalog a filter on the `demografia` theme finds 146 collections through `parents` and 0 through the direct parent alone, because every collection sits under an alphabetical shard sub-catalog. See [results/links-only-variant.md](results/links-only-variant.md) for the comparison with a file that carries only STAC links, and [results/tree-designs.md](results/tree-designs.md) for the alternatives that were measured and rejected.

## The test catalogs

Two catalogs from the Portolan registry are the fixtures. Their metadata is mirrored under `catalogs/`, so every test runs from the repository without network access, and the same scripts run against the published catalogs for the remote measurements.

| Catalog | Root | Documents |
|---|---|---|
| Berlin Geoportal | https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json | 37 catalogs, 371 collections |
| Comunidad de Madrid | https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/catalog.json | 177 catalogs, 1,964 collections |

To refresh a mirror, or mirror another catalog:

```bash
python3 -I scripts/mirror_catalog.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json catalogs/berlin-geoportal
```

The script follows `child` links from the root and saves each document at its relative path. It does not download assets.

To mirror every catalog in the Portolan registry, and to build one federated index from the mirror:

```bash
python3 -I scripts/mirror_registry.py https://registry.portolan-sdi.org/next/catalogs.json catalogs/registry
python3 -I scripts/crawl_registry.py catalogs/registry work/registry/collections.jsonl
(cd work/registry && duckdb < ../../scripts/build_index.sql)
```

The mirror writes `catalogs/registry/manifest.json` with counts and failures per catalog. Pass `retry` as a third argument to mirror again only the catalogs that failed.

## Build an index

Requirements: Python 3.10 or later, [DuckDB CLI](https://duckdb.org/docs/installation/) 1.5 or later with the `spatial` and `httpfs` extensions, and [gpio](https://github.com/geoparquet-io/geoparquet-io) for the GeoParquet check.

From the local mirror, with the public URL so that the `href` column holds canonical links:

```bash
scripts/index_catalog.sh catalogs/berlin-geoportal/catalog.json work/berlin https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json
```

From the published catalog:

```bash
scripts/index_catalog.sh https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json work/berlin
```

Either way the script writes `work/berlin/collections.jsonl` and `work/berlin/collections.parquet` and runs `gpio check` on the file. On 2026-10-22 the index built from the mirror matched `indexes/berlin-geoportal/collections.parquet` in every row.

## Serve a mirror locally

A mirror plus its index is a complete local copy of the catalog for query tests:

```bash
cp work/berlin/collections.parquet catalogs/berlin-geoportal/
(cd catalogs && python3 -m http.server 8765)
python3 -I scripts/walk_timing.py http://127.0.0.1:8765/berlin-geoportal/catalog.json 13.405 52.52 verkehr
```

Use this to check correctness and to develop queries. Do not read latency from it. Python's HTTP server is single threaded and has no keep-alive, so it distorts both the walk and the Parquet range requests. The latency figures in `results/` come from the published catalogs.

## Time the queries

The JSON walk a client does today, against the same catalog:

```bash
python3 -I scripts/walk_timing.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json 13.405 52.52 verkehr
```

The same questions against an index served over HTTPS:

```bash
duckdb -c "SET VARIABLE u='https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE grp='verkehr';" -c ".read scripts/remote_queries.sql"
```

The two indexes under `indexes/` were uploaded next to their catalogs for the measurements. The catalogs do not link to them, and a later publish of the catalog can remove them.

## Synthetic benchmarks

Each folder under `benchmarks/` has a `build.sql` that writes a 5 million row Parquet file and a `queries.sql` that runs the comparison. Run them from inside the folder:

```bash
cd benchmarks/tree-designs && duckdb < build.sql && duckdb -c "SET VARIABLE f='tree_sorted.parquet';" -c ".read queries.sql"
```

The results pages record the numbers from 2026-10-22 on DuckDB 1.5.6.

## License

Apache-2.0.
