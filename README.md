# STAC GeoParquet as catalog: testbed

Experiments behind a proposal to describe a whole STAC catalog, every collection in its tree, in one GeoParquet file at the catalog root. The proposal is under discussion in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) and [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44). The schema under test is in [docs/schema.md](docs/schema.md).

The testbed answers two questions. Can one Parquet file replace the walk through catalog JSON documents that a client does today? And which column shape for the catalog tree makes that file fast to query?

## Findings

Three real fixtures from the Portolan registry, from one city catalog to the whole federation. The headline measurement on each is one question, collections under one group of the tree whose extent contains a point, asked two ways: a walk through the catalog JSON and one query on the index. For the registry the question is the point alone, across every catalog. Beyond the headline, the [query suite](results/04-query-suite.md) runs sixteen more shapes, spatial, tree, attribute, document, and combined, plus seven against real polygons from the catalogs, and two synthetic benchmarks compare designs at 5 million rows. [docs/method.md](docs/method.md) says why that question and why the measurements are remote.

| Fixture | Collections | Depth | JSON walk, whole tree: sequential, 16 threads | JSON walk, the group only: sequential, 16 threads | One query on the index over HTTPS |
|---|---|---|---|---|---|
| Berlin Geoportal | 371 | 2 | 78 s, 6.1 s, 408 requests | 4.6 s, 0.8 s, 21 requests | 0.44 to 0.48 s, 2 requests |
| Comunidad de Madrid | 1,964 | 3 | 7 min 2 s, 25 s, 2,141 requests | 27 s, 2.1 s, 159 requests | 0.74 to 0.78 s, 2 requests |
| Portolan registry, 86 catalogs | 5,852 | 4 | 40 min 41 s, 2 min 35 s, 6,726 requests | does not apply | 0.8 to 1.3 s, 4 requests |

For the registry the question is the point alone, across every catalog, so only the whole walk answers it. For the two city catalogs the group-only walk is the cheapest a client can do when it already knows which child link leads to the group; the whole walk is what it pays when it does not, or when the question spans groups. Measured on 2026-10-23 with DuckDB 2.0.0 and Python 3.14.9. DuckDB 2.0 reads a file of a few megabytes whole in one request, so the index query's time is one handshake and one or three round trips, not rows. Read the [caveats](#caveats) before quoting these numbers.

What the pages under [results/](results/README.md) establish, in one table:

| Question | Finding | Evidence |
|---|---|---|
| Does one file replace the JSON walk? | Yes. Two to four requests at these sizes, against one request per document: 78 s, 7 min, and 41 min of sequential walking become about a second. | [01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md), [03](results/03-portolan-registry.md) |
| Does the tree column need the full ancestor chain? | Yes, for a file that holds only collections. In Madrid the theme has 146 collections through `parents` and 0 through the direct parent. A links-only file needs 178 requests for the same answer. A file that also held catalog rows was not measured. | [02](results/02-comunidad-madrid.md), [06](results/06-links-only-variant.md) |
| Is there a better tree column for generic STAC? | Not at real sizes, where the column shape does not change the cost. At 5 million rows a path string is faster but needs an escaping rule; level columns fix the depth; a recursive query is slowest. | [05](results/05-tree-designs.md), [07](results/07-list-shapes.md) |
| Does the schema hold across a federation? | Yes, with `parents` plus `id` as the key. 26 ids repeat, 25 of them across catalogs and one under two parents in the same catalog; the pair is unique for all 5,852 rows. | [03](results/03-portolan-registry.md) |
| Does the geometry column earn its place? | Yes. Point, box, polygon containment, distance, area ranking, and a spatial join with real boundaries all run in about a second or less over HTTPS. Antimeridian bboxes must be split or they match every longitude. | [04](results/04-query-suite.md), [03](results/03-portolan-registry.md) |
| How does a catalog advertise the file? | As a link with `rel: "data"` and the Parquet media type. A Catalog has no `assets` field, so the asset form used for `items.parquet` is not available one level up. | [docs/discovery.md](docs/discovery.md) |
| How should the file be laid out? | One row group at this size, under DuckDB 2.0. It reads small files whole, and the files with more row groups cost more on every query. Those files also differ in sort order and writer, so the row group count is not isolated. | [03](results/03-portolan-registry.md), [04](results/04-query-suite.md) |

The same findings, with the numbers behind them:

- **The index turns a cost that grows with the tree into a near constant.** Two to four requests at these sizes, against one request per document. The bytes read still grow with the file: 312 KB on Berlin, 1.4 MB on Madrid, 1.0 MB of 6.5 MB on the registry. ([01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md), [03](results/03-portolan-registry.md))
- **`parents` answers the mid-tree case that the STAC links cannot.** In Madrid the `demografia` theme has 146 collections through `parents` and 0 through the direct parent, because every collection sits under a shard sub-catalog. A links-only file needs 178 requests for that question. ([02](results/02-comunidad-madrid.md), [06](results/06-links-only-variant.md))
- **The case for `parents` is simplicity, not speed.** At real sizes every tree column costs the same over HTTPS. `parents` answers the subtree question in one column, with ids rather than URLs to resolve, and without catalog rows in the file. At 5 million rows a materialized path is faster but needs an escaping rule, since STAC ids may contain any character. Level columns fix the depth. A recursive query is slowest. ([05](results/05-tree-designs.md), [07](results/07-list-shapes.md))
- **Federation works with `parents` plus `id` as the key.** 25 ids repeat across the 86 catalogs, and one more repeats under two parents inside one catalog. The pair is unique for all 5,852 rows. ([03](results/03-portolan-registry.md))
- **A bbox that crosses the antimeridian must be split.** 30 collections have west greater than east, and as plain envelopes 26 of them matched a point in Madrid. ([03](results/03-portolan-registry.md))
- **One row group is the right layout at this size, under DuckDB 2.0.** It coalesces nearby byte ranges into one request, and the files with 3 and 12 row groups read more bytes in more requests for every query. The one expensive shape, reading a full `original` document, costs the whole column chunk, 5.9 MB on the registry, and smaller row groups cut it only modestly. The multi-group files are also in tree order rather than Hilbert order, and the 12-group one is written by pyarrow, so the comparison does not isolate the row group count. Under DuckDB 1.5.6 the opposite held. ([03](results/03-portolan-registry.md), [04](results/04-query-suite.md))

## Caveats

- **The walk client opens a new connection for every document.** `scripts/walk_timing.py` uses `urllib`, which does not keep connections alive, so each request pays TCP and TLS setup. A sequential Berlin walk over one kept-alive connection took 41 s on 2026-10-25, against 83 s for the same walk without it. The request counts do not change.
- **The spatial filter selects almost nothing in the two city catalogs.** 1,960 of the 1,964 Comunidad de Madrid collections carry the whole-world bbox `[-180, -90, 180, 90]` as a placeholder, and 367 of 371 Berlin extents contain the test point. Those fixtures test the tree filter and the request count. Only the registry tests spatial selectivity.
- **Cold times are `EXPLAIN ANALYZE` totals.** They include the TLS handshake and the reads made while the query runs. They leave out process start and any read DuckDB makes while planning, which is why one query shows 0.00 s. Warm times are cache hits: one HEAD request, no data read.
- **The engine decides the layout result.** The row group conclusion holds for DuckDB 2.0 and reversed under 1.5.6. Other readers were not measured.
- **The sizes are small.** The largest file is 6.5 MB. Whether the request count stays flat for a federation of a hundred thousand collections was not measured.

KB and MB in these pages are KiB and MiB.

## Repository layout

| Path | Content |
|---|---|
| `docs/` | The schema under test, how a catalog advertises the file, and the method |
| `results/` | One page per measurement, numbered in reading order, with an index |
| `catalogs/` | Metadata mirrors: every `catalog.json` and `collection.json` of the three fixtures, no data assets, with a manifest for the registry |
| `indexes/` | The indexes built from the mirrors, as measured |
| `scripts/` | The pipeline: mirror, crawl, build, check, and measure |
| `benchmarks/` | SQL and Python behind the row group layouts on page 3 and the design comparisons on pages 5 to 7 |

Requirements: the [DuckDB CLI](https://duckdb.org/docs/installation/) 2.0 or later with the `spatial` and `httpfs` extensions, [uv](https://docs.astral.sh/uv/) for the Python environment, and [gpio](https://github.com/geoparquet-io/geoparquet-io) for the GeoParquet check.

```bash
uv sync                      # Python 3.14.9 with duckdb 2.0.0 and pyarrow 26.0.0, as pinned in pyproject.toml and uv.lock
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

`uv run` puts the pinned Python 3.14.9 first on the path. The drivers use only the standard library.

Each writes `collections.jsonl` and `collections.parquet` in the output directory and runs `gpio check`. The index built from the Berlin mirror matched the committed one in every row.

### 3. Upload

The measured files are served from the same bucket as the CARTO catalogs. Both city fixtures, and 43 of the 86 catalogs in the registry, are published by CARTO in that bucket; the other 43 are published by others on their own hosting. The Berlin and Madrid indexes sit beside their catalogs. The registry files sit in a scratch prefix, because the registry export is not a bucket this testbed can write to. Nothing links to them from a `catalog.json` yet; [docs/discovery.md](docs/discovery.md) says how a catalog would. A later publish of a catalog can remove them. The same files are committed under `indexes/`, so any host that answers HTTP range requests reproduces the measurements.

| File | URL |
|---|---|
| Berlin index | https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet |
| Madrid index | https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet |
| Madrid, links-only variant | https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections-links.parquet |
| Registry index, 1 row group | https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections.parquet |
| Registry index, 3 row groups | https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048.parquet |
| Registry index, 12 row groups | https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-pa512.parquet |

The real-polygon queries also read two boundary files that the catalogs publish: Berlin districts at `berlin-geoportal/main/alkis/bezirke/alkis_bezirke_bezirksgrenzen.parquet` and Madrid neighbourhoods at `madrid-datos-abiertos/main/urbanismo/barrios-municipales/BARRIOS.parquet`, under the same host.

Upload your own copies with any tool that sets the content type `application/vnd.apache.parquet`:

```bash
gsutil -h "Content-Type:application/vnd.apache.parquet" cp work/berlin/collections.parquet gs://<bucket>/<catalog prefix>/collections.parquet
```

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

Apache-2.0 covers the code and the documentation. The metadata under `catalogs/`, and the copies of it in the `original` column of the files under `indexes/`, belong to the publishers of each catalog and stay under their terms. It is mirrored here so that the measurements can be reproduced after the published catalogs change.
