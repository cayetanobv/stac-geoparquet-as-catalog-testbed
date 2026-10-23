# STAC GeoParquet as catalog: testbed

Experiments behind a proposal to describe a whole STAC catalog, every collection in its tree, in one GeoParquet file at the catalog root. The proposal is under discussion in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) and [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44). The schema under test is in [docs/schema.md](docs/schema.md).

The testbed answers two questions. Can one Parquet file replace the walk through catalog JSON documents that a client does today? And which column shape for the catalog tree makes that file fast to query?

## Findings

Three real fixtures from the Portolan registry, from one city catalog to the whole federation. The question is the same on each: collections under one group of the tree whose extent contains a point. [docs/method.md](docs/method.md) says why that question and why the measurements are remote.

| Fixture | Collections | Depth | JSON walk, sequential | JSON walk, 16 threads | One query on the index over HTTPS |
|---|---|---|---|---|---|
| Berlin Geoportal | 371 | 2 | 78 s, 408 requests | 6.1 s | 0.44 to 0.48 s, 2 requests |
| Comunidad de Madrid | 1,964 | 3 | 7 min 2 s, 2,141 requests | 25 s | 0.74 to 0.78 s, 2 requests |
| Portolan registry, 86 catalogs | 5,852 | 4 | 40 min 41 s, 6,726 requests | 2 min 35 s | 0.8 to 1.3 s, 4 requests |

For the registry the question is the point alone, across every catalog. Measured on 2026-10-23 with DuckDB 2.0.0 and Python 3.14.9. DuckDB 2.0 reads a file of a few megabytes whole in one request, so the index query's time is one handshake and one or three round trips, not rows.

What the pages under [results/](results/README.md) establish:

- **The index turns a cost that grows with the tree into a constant.** Two to four requests whatever the row count, against one request per document. ([01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md), [03](results/03-portolan-registry.md))
- **`parents` answers the mid-tree case that the STAC links cannot.** In Madrid the `demografia` theme has 146 collections through `parents` and 0 through the direct parent, because every collection sits under a shard sub-catalog. A links-only file needs 181 requests for that question. ([02](results/02-comunidad-madrid.md), [06](results/06-links-only-variant.md))
- **No measured alternative to `parents` is better for generic STAC.** A materialized path is faster above a million rows but needs an escaping rule, since STAC ids may contain any character. Level columns fix the depth. A recursive query is slowest. ([05](results/05-tree-designs.md), [07](results/07-list-shapes.md))
- **Federation works with `parents` plus `id` as the key.** 26 ids repeat across the 86 catalogs. The pair is unique for all 5,852 rows. ([03](results/03-portolan-registry.md))
- **A bbox that crosses the antimeridian must be split.** 30 collections have west greater than east, and as plain envelopes 26 of them matched a point in Madrid. ([03](results/03-portolan-registry.md))
- **One row group is the right layout at this size, and the engine decides it.** DuckDB 2.0 coalesces nearby byte ranges into one request, so every extra row group adds requests and bytes to every query. The one expensive shape, reading a full `original` document, costs the whole column chunk, 5.9 MB on the registry, and smaller row groups cut it only modestly. Under DuckDB 1.5.6 the opposite held. ([03](results/03-portolan-registry.md), [04](results/04-query-suite.md))

## Repository layout

| Path | Content |
|---|---|
| `docs/` | The schema under test and the method |
| `results/` | One page per measurement, numbered in reading order, with an index |
| `catalogs/` | Metadata mirrors: every `catalog.json` and `collection.json` of the three fixtures, no data assets, with a manifest for the registry |
| `indexes/` | The indexes built from the mirrors, as measured |
| `scripts/` | The pipeline: mirror, crawl, build, check, and measure |
| `benchmarks/` | SQL and Python behind the row group layouts on page 3 and the design comparisons on pages 5 to 7 |

Requirements: the [DuckDB CLI](https://duckdb.org/docs/installation/) 2.0 or later with the `spatial` and `httpfs` extensions, [uv](https://docs.astral.sh/uv/) for the Python environment, and [gpio](https://github.com/geoparquet-io/geoparquet-io) for the GeoParquet check.

```bash
uv sync                      # Python 3.12 with duckdb 2.0 and pyarrow 26, as pinned in pyproject.toml
pipx install geoparquet-io   # gpio pins an older duckdb, so it gets its own environment
duckdb -c "INSTALL spatial; INSTALL httpfs;"
```

The scripts under `scripts/` use the standard library. Only `benchmarks/row-groups/build_pa512.py` and `benchmarks/links-only/links_only_theme.py` import the pinned packages. Measured with Python 3.14.9.

## Reproduce

The pipeline has four steps: mirror a catalog's metadata, build the index from the mirror, upload the index beside the catalog, and measure. The mirrors and the indexes are committed, so the first two steps are optional.

### 1. Mirror

One catalog:

```bash
python3 -I scripts/mirror_catalog.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json catalogs/berlin-geoportal
```

Every catalog in the registry, with a manifest of counts and failures:

```bash
python3 -I scripts/mirror_registry.py https://registry.portolan-sdi.org/next/catalogs.json catalogs/registry
```

Both follow `child` links and save each document at its relative path. Pass `retry` as a third argument to the registry script to mirror again only the catalogs that failed.

### 2. Build

One catalog, from its mirror, with the public URL so that `href` holds canonical links. The same script accepts the published URL instead of a local path.

```bash
uv run bash scripts/index_catalog.sh catalogs/berlin-geoportal/catalog.json work/berlin https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json
```

The federated index from the registry mirror:

```bash
uv run bash scripts/index_registry.sh https://registry.portolan-sdi.org/next/catalogs.json catalogs/registry work/registry
```

`uv run` puts the pinned Python first on the path. The drivers also run with any system Python 3.12 or later.

Each writes `collections.jsonl` and `collections.parquet` in the output directory and runs `gpio check`. The index built from the Berlin mirror matched the committed one in every row.

### 3. Upload

The measured indexes sit beside their catalogs on the same storage, unlinked from `catalog.json`. A later publish of a catalog can remove them. Upload your own with any tool that sets the content type `application/vnd.apache.parquet`.

### 4. Measure

The JSON walk a client does today:

```bash
python3 -I scripts/walk_timing.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json 13.405 52.52 verkehr
```

The same question against the index:

```bash
duckdb -c "SET VARIABLE u='https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE grp='verkehr';" -c ".read scripts/remote_queries.sql"
```

The sixteen-query suite, cold and warm, as a Markdown table:

```bash
uv run python scripts/run_suite.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet --lon 13.405 --lat 52.52 --grp verkehr --kw Radverkehr --cat berlin-geoportal --id gruenflaechen/grillflaechen --runs 3
```

Measure against the published storage, not a local server. A mirror served with `python3 -m http.server` is fine for checking results, and useless for latency, for the reasons in [docs/method.md](docs/method.md).

### Synthetic benchmarks

Each folder under `benchmarks/` has a `build.sql` that writes a 5 million row file and a `queries.sql` that runs the comparison:

```bash
cd benchmarks/tree-designs && duckdb < build.sql && duckdb -c "SET VARIABLE f='tree_sorted.parquet';" -c ".read queries.sql"
```

## License

Apache-2.0.
