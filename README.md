# STAC GeoParquet as catalog: testbed

Experiments behind a proposal to describe a whole STAC catalog, every collection in its tree, in one GeoParquet file at the catalog root. The proposal is under discussion in [radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17) and [portolan-sdi/portolan-spec#44](https://github.com/portolan-sdi/portolan-spec/issues/44). The schema under test, and every variant measured against it, is in [docs/schema.md](docs/schema.md).

The testbed answers two questions. Can one Parquet file replace the walk through catalog JSON documents that a client does today? And which column shape for the catalog tree makes that file fast to query?

## Findings

Two real catalogs from the Portolan registry, Berlin Geoportal and Comunidad de Madrid, and the whole registry as one federated index of 86 catalogs. The headline asks each one the question a user brings to a catalog: what data about a topic, or any data, covers this place? It is asked two ways: a walk through the catalog JSON, as a client does today, and one query on the index, `collections.parquet`, the GeoParquet file at the catalog root with one row per collection. "The index" means that file throughout. Beyond the headline, the [query suite](results/04-query-suite.md) runs sixteen more shapes, spatial, tree, attribute, document, and combined, plus seven against real polygons from the catalogs, and two synthetic benchmarks compare designs at 5 million rows. [docs/method.md](docs/method.md) says why the measurements are remote.

| Question | Answer | JSON walk of the whole catalog | One query on the GeoParquet index | What a walk of only the groups named like the topic finds |
|---|---|---|---|---|
| Berlin Geoportal, 371 collections: transport datasets whose extent covers the city centre | 65 collections | 408 requests, 6.6 s | 2 requests, 0.41 to 0.43 s | 15 of the 65 |
| Comunidad de Madrid, 1,964 collections: population datasets whose extent covers the city centre | 461 collections | 2,141 requests, 20 s | 2 requests, 0.72 to 0.74 s | 129 of the 461 |
| Portolan registry, 86 catalogs and 5,852 collections: every dataset whose extent covers central Madrid | 2,254 collections in 33 catalogs | 6,725 requests, 2 min 14 s | 4 requests, 0.61 to 0.70 s | no group applies: the answer spans 33 catalogs, and a Catalog has no extent to prune by |

A dataset is about transport when its title or a keyword contains `verkehr` or `mobilit`, and about population when it contains `demograf` or `poblacion`, without case or accents. The walk and the index return the same counts, except that the registry walk finds 2,251 because one catalog now answers with an HTML page; see [page 03](results/03-portolan-registry.md). The walk keeps 6 requests in flight, a typical HTTP/1.1 client, and reuses one connection per host and thread. One request at a time it takes 27 s, 1 min 10 s, and 15 min 4 s; with 16 in flight, 2.9 s, 9.1 s, and 56 s. The index time is the median of three cold runs in a fresh process, at the start and at the end of the session. All measured in one session on 2026-10-26, 18:41 to 19:02 UTC, with DuckDB 2.0.0 and Python 3.14.9. DuckDB 2.0 reads a file of a few megabytes whole in one request, so the index query's time is one handshake and one or three round trips, not rows. The last column counts, in the committed index, the answer that sits under the groups whose link titles match the same terms: `verkehr` and `mobilitaet` in Berlin, `demografia` in Madrid. Walking only those is the shortcut a client has without the index; [pages 01 to 03](results/01-berlin-geoportal.md) time it, with the group known or found, at 1, 6 and 16 concurrent requests. Read the [caveats](#caveats) before quoting these numbers.

What the pages under [results/](results/README.md) establish, in one table:

| Question | Finding | Evidence |
|---|---|---|
| Does one file replace the JSON walk? | Yes. Two to four requests at these sizes, against one request per document: 27 s, 1 min 10 s, and 15 min of sequential walking with reused connections become under a second. A walk of one small group with 6 requests in flight is about as fast as the index; there the gain is requests, 21 against 2, and coverage. | [01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md), [03](results/03-portolan-registry.md) |
| Can a walk prune to the right group by itself? | Only by name, and names miss most of a topic. Matching the root's child links costs no extra request and takes about as long as walking a known group, but the groups it finds hold 23% of the transport collections in Berlin and 28% of the population collections in Madrid. Reading every group's description raises Berlin to 52%. A Catalog has no extent, so a walk cannot prune by place. | [01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md) |
| Does the tree column need the full ancestor chain? | Yes, for a file that holds only collections. In Madrid the theme has 146 collections through `parents` and 0 through the direct parent. A links-only file needs 178 requests for the same answer. With catalog rows in the same file it needs none beyond the file and costs about the same as `parents`, so the case for `parents` there is simplicity and ids, not speed. | [02](results/02-comunidad-madrid.md), [06](results/06-links-only-variant.md), [08](results/08-follow-up-checks.md) |
| Is there a better tree column for generic STAC? | Not at real sizes, where the column shape does not change the cost. At 5 million rows a path string is faster but needs an escaping rule; level columns fix the depth; a recursive query is slowest. | [05](results/05-tree-designs.md), [07](results/07-list-shapes.md) |
| Can the index carry each ancestor's href? | Yes, at no measurable cost in DuckDB 2.0, as a list of `{id, href}` or as a `parent_hrefs` list beside `parents`. Both make the same requests as the ids alone, with the same results. DuckDB fetches the hrefs inside a range it reads anyway, so most queries read the same byte ranges; only those that read the whole `original` column read the 21 KB more. | [09](results/09-parent-hrefs.md) |
| Does the schema hold across a federation? | Yes, with `parents` plus `id` as the key. 26 ids repeat, 25 of them across catalogs and one under two parents in the same catalog; the pair is unique for all 5,852 rows. | [03](results/03-portolan-registry.md) |
| Does the geometry column earn its place? | Yes. Point, box, polygon containment, distance, area ranking, and a spatial join with real boundaries all run in about a second or less over HTTPS. Antimeridian bboxes must be split or they match every longitude. | [04](results/04-query-suite.md), [03](results/03-portolan-registry.md) |
| How does a catalog advertise the file? | As a link with `rel: "data"` and the Parquet media type. A Catalog has no `assets` field, so the asset form used for `items.parquet` is not available one level up. | [docs/discovery.md](docs/discovery.md) |
| How should the file be laid out? | One row group at this size, under DuckDB 2.0. It reads small files whole, and the files with more row groups cost more on every query. A Hilbert-ordered file with three row groups reads the same bytes as the tree-ordered one for spatial queries, so sort order does not change that. | [03](results/03-portolan-registry.md), [04](results/04-query-suite.md) |

### Schema proposals compared

Every schema the testbed measured, against the one under test. The number links to its full column list in [docs/schema.md](docs/schema.md). The question for the tree columns is the theme question from [page 02](results/02-comunidad-madrid.md): every collection anywhere under `demografia` in Madrid, 146 of them, two levels above the collections. The path, level-column and recursive designs were measured on the same kind of question, the subtree of one catalog, in a synthetic tree of 5 million collections, because no real catalog is large enough to separate them.

| Proposal | How it answers "everything under this node" | Measured cost | Verdict | Evidence |
|---|---|---|---|---|
| [1](docs/schema.md#1-proposed-parents-as-ids) `parents`, list of ancestor ids, the schema under test | `list_contains(parents, 'demografia')`, one predicate | 2 requests over HTTPS, the same as any other query on the file | Kept | [02](results/02-comunidad-madrid.md), [04](results/04-query-suite.md) |
| [2](docs/schema.md#2-links-only) STAC `links` only, no `parents` | The file holds only the direct parent, as a relative URL: the client fetches every ancestor catalog | 178 requests, 3.2 s with 16 threads, 30 s sequential | Rejected for a file of collections only | [06](results/06-links-only-variant.md) |
| [3](docs/schema.md#3-links-with-catalog-rows) STAC `links` plus one row per catalog | The client resolves each parent link against its row's `href` and climbs the tree in its own code | One file, about the time of `parents` | Works, but moves the tree walk into every client and adds the catalog rows | [08](results/08-follow-up-checks.md) |
| [6](docs/schema.md#6-tree-columns-synthetic) Materialized `path` string | Prefix `LIKE 'root/demografia/%'` | At 5 million rows, sorted in tree order, 8 times less CPU than `parents`; at real sizes the file is read whole and the column shape does not show | Not adopted: STAC ids may contain the separator, so it needs an escaping rule; `demografia/e-i` is a real id | [05](results/05-tree-designs.md) |
| [6](docs/schema.md#6-tree-columns-synthetic) Level columns `p1`, `p2`, `p3` | One equality per level | Fastest at 5 million rows, 5 to 14 ms | Not adopted: fixes the depth of the tree | [05](results/05-tree-designs.md) |
| [6](docs/schema.md#6-tree-columns-synthetic) `parent` only, recursive query over catalog rows | Recursive join from the node down | Slowest at 5 million rows: 0.21 to 0.52 s, against 0.04 to 0.07 s for `parents` | Not adopted: needs ids unique across the tree, which STAC does not guarantee | [05](results/05-tree-designs.md) |
| [4](docs/schema.md#4-parents-as-id-href) `parents` as a list of `{id, href}` | `list_contains(list_transform(parents, lambda p: p.id), 'demografia')` | Same requests, results and times as `parents`; the hrefs add 21 KB on the registry | Works; every filter needs a lambda or an unnest | [09](results/09-parent-hrefs.md) |
| [5](docs/schema.md#5-parents-with-parent_hrefs) `parents` plus `parent_hrefs` | `list_contains(parents, 'demografia')`, unchanged | Same requests, results and times as `parents`; the hrefs add 21 KB on the registry | Works; keeps the filter and lets the hrefs be optional. The one to propose if hrefs are needed | [09](results/09-parent-hrefs.md) |

Layouts of the same schema, measured on the registry: one row group in Hilbert order, the published file, against three and twelve row groups in tree order and three in Hilbert order. One row group reads the fewest bytes in the fewest requests for every query except the lookup of one full document, under DuckDB 2.0 ([03](results/03-portolan-registry.md), [08](results/08-follow-up-checks.md)). How a catalog points at the file, `rel: "data"` against `alternate` and an asset, is argued in [docs/discovery.md](docs/discovery.md).

The same findings, with the numbers behind them:

- **The index turns a cost that grows with the tree into a near constant.** Two to four requests at these sizes, against one request per document. Time follows only where the walk is large: with 6 requests in flight over reused connections, the whole registry took 2 min 14 s against 0.61 to 0.70 s for the index, while in an earlier session a walk of Berlin's `verkehr` group alone, 21 documents, took 0.87 s against 0.43 to 0.62 s for the index's group query. The bytes read still grow with the file: 312 KB on Berlin, 1.4 MB on Madrid, 1.0 MB of 6.5 MB on the registry. ([01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md), [03](results/03-portolan-registry.md))
- **Finding the group by name misses most of the topic.** A client that matches the titles of the root's child links walks `verkehr` and `mobilitaet` in Berlin, 15 of 65 transport collections, and `demografia` in Madrid, 129 of 461 population collections; `salud` alone holds 206. Matching every group's description reaches 34 in Berlin, at 37 extra requests. The index answers the whole topic, filtering title and keywords across every collection, in 2 requests and under a second, against 408 and 2,141 requests for the walks of the whole catalogs. ([01](results/01-berlin-geoportal.md), [02](results/02-comunidad-madrid.md))
- **`parents` answers the mid-tree case that the STAC links cannot.** In Madrid the `demografia` theme has 146 collections through `parents` and 0 through the direct parent, because every collection sits under a shard sub-catalog. A links-only file needs 178 requests for that question. ([02](results/02-comunidad-madrid.md), [06](results/06-links-only-variant.md))
- **The case for `parents` is simplicity, not speed.** At real sizes every tree column costs the same over HTTPS. `parents` answers the subtree question in one column, with ids rather than URLs to resolve, and without catalog rows in the file. At 5 million rows a materialized path is faster but needs an escaping rule, since STAC ids may contain any character. Level columns fix the depth. A recursive query is slowest. ([05](results/05-tree-designs.md), [07](results/07-list-shapes.md))
- **Ancestor hrefs cost nothing measurable.** For readers outside Portolan, who need to fetch the ancestors, the index can carry each one's href, as a list of `{id, href}` in `parents` or as a `parent_hrefs` list beside it. On all three indexes both shapes returned the same results in the same requests as the ids alone, and their times stayed within the noise of one session. DuckDB 2.0 reads about 1 MB from the first column a query needs, so on the registry the 21 KB of hrefs fall inside a read it makes anyway; its HTTP log shows the same byte ranges in all three shapes. Two columns keep the filter on `parents` a plain `list_contains` and let the hrefs be optional. ([09](results/09-parent-hrefs.md))
- **Federation works with `parents` plus `id` as the key.** 25 ids repeat across the 86 catalogs, and one more repeats under two parents inside one catalog. The pair is unique for all 5,852 rows. ([03](results/03-portolan-registry.md))
- **A bbox that crosses the antimeridian must be split.** 30 collections have west greater than east, and as plain envelopes 26 of them matched a point in Madrid. ([03](results/03-portolan-registry.md))
- **One row group is the right layout at this size, under DuckDB 2.0.** It coalesces nearby byte ranges into one request, and the files with 3 and 12 row groups read more bytes in more requests for every query. The one expensive shape, reading a full `original` document, costs the whole column chunk, 5.9 MB in 1.4 s on the registry; three row groups cut it to 3.3 MB in 0.9 s, and every other query pays for them. A three-group file in Hilbert order reads the same bytes in the same requests as the tree-ordered one for every spatial query, because every row group spans the globe ([08](results/08-follow-up-checks.md)). Under DuckDB 1.5.6 the opposite held. ([03](results/03-portolan-registry.md), [04](results/04-query-suite.md))

## Caveats

- **The walk is measured several ways.** At 1, 6 and 16 concurrent requests, with reused connections and with a new connection per document. With reused connections and 6 or more requests in flight, a walk of one small group, known or found by name, is close to the index in time; the index wins on requests there, on coverage of a topic, and on time once the walk is large or sequential. Concurrency means requests in flight, one thread each, not CPU cores. Measurements before 2026-10-25 opened a new connection per document, which made every walk slower.
- **The spatial filter selects almost nothing in the two city catalogs.** 1,960 of the 1,964 Comunidad de Madrid collections carry the whole-world bbox `[-180, -90, 180, 90]` as a placeholder, and 367 of 371 Berlin extents contain the test point. Those fixtures test the tree filter and the request count. Only the registry tests spatial selectivity.
- **Cold times are given two ways.** The `EXPLAIN ANALYZE` total leaves out any read DuckDB makes while planning, which is why one query shows 0.00 s; the wall clock of the same query in a fresh process includes it. Both leave out process start. Warm times are cache hits: one HEAD request, no data read.
- **Times depend on the network of the hour.** The headline table comes from one session on 2026-10-26, 18:41 to 19:02 UTC, where the medians of the index queries at its start and its end agreed within 0.1 s. The group walks on pages 01 to 03 come from an afternoon session, 13:30 to 15:40 UTC, where the same index query took up to almost twice as long at the start as at the end. The query suite on page 04 and the remote checks on page 08 come from a morning session, 08:20 to 09:47 UTC. The ancestor hrefs on page 09 come from one session on 2026-10-27, 17:51 to 18:07 UTC. Only times from the same session are compared. Pages 05 to 07 come from 2026-10-23. The request counts are the durable result.
- **The engine decides the layout result.** The row group conclusion holds for DuckDB 2.0 and reversed under 1.5.6. Other readers were not measured.
- **The sizes are small.** The largest file is 6.5 MB. Whether the request count stays flat for a federation of a hundred thousand collections was not measured.

KB and MB in these pages are KiB and MiB.

## Repository layout

| Path | Content |
|---|---|
| `docs/` | The schema under test, how a catalog advertises the file, and the method |
| `results/` | One page per measurement, numbered in reading order, with an index |
| `catalogs/` | Metadata mirrors: every `catalog.json` and `collection.json` of Berlin, Madrid, and the whole registry, no data assets, with a manifest for the registry |
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

Each writes `collections.jsonl` and `collections.parquet` in the output directory and runs `gpio check`. The index built from the Berlin mirror matched the committed one in every row. The crawl also records each ancestor catalog's URL, from which `scripts/parent_hrefs.sql` writes the two variants on [page 09](results/09-parent-hrefs.md), one with `parents` as a list of `{id, href}` and one with a `parent_hrefs` list beside `parents`:

```bash
duckdb -c "SET VARIABLE u='indexes/berlin-geoportal/collections.parquet'; SET VARIABLE j='work/berlin/collections.jsonl'; SET VARIABLE os='work/berlin/collections-parents-struct.parquet'; SET VARIABLE oc='work/berlin/collections-parent-hrefs.parquet';" -c ".read scripts/parent_hrefs.sql"
```

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
| Registry index, 3 row groups, Hilbert order | https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048-hilbert.parquet |
| Madrid, links with catalog rows | https://storage.googleapis.com/carto-open-catalogs/_testbed/comunidad-madrid/collections-links-catalogs.parquet |
| Berlin, `parents` as `{id, href}` | https://storage.googleapis.com/carto-open-catalogs/_testbed/berlin-geoportal/collections-parents-struct.parquet |
| Berlin, `parents` and `parent_hrefs` | https://storage.googleapis.com/carto-open-catalogs/_testbed/berlin-geoportal/collections-parent-hrefs.parquet |
| Madrid, `parents` as `{id, href}` | https://storage.googleapis.com/carto-open-catalogs/_testbed/comunidad-madrid/collections-parents-struct.parquet |
| Madrid, `parents` and `parent_hrefs` | https://storage.googleapis.com/carto-open-catalogs/_testbed/comunidad-madrid/collections-parent-hrefs.parquet |
| Registry, `parents` as `{id, href}` | https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-parents-struct.parquet |
| Registry, `parents` and `parent_hrefs` | https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-parent-hrefs.parquet |

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

Each thread keeps one connection alive per host. Add `fresh` to open a new connection for every document, as the measurements before 2026-10-25 did. `concurrency=1,6,16` sets how many requests each walk keeps in flight, one thread each; the default is `1,6,16`, as in the pages. Pass `whole` as the group to walk only the whole tree, and `topic=verkehr,mobilit` to count as hits only the collections whose title or a keyword contains a term, as the headline does:

```bash
python3 -I scripts/walk_timing.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json 13.405 52.52 whole topic=verkehr,mobilit
```

A client that has to find the group first, from the titles of the root's child links, then walks every group that matches, or the whole tree when none does. `describe:` also fetches each child catalog and matches its description. Terms match without case or accents:

```bash
python3 -I scripts/walk_timing.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json 13.405 52.52 find:verkehr,mobilit
python3 -I scripts/walk_timing.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/catalog.json 13.405 52.52 describe:verkehr,mobilit
```

How much of the topic, by the same terms on title and keywords, sits under the groups the walk chose:

```bash
duckdb -c "SET VARIABLE u='indexes/berlin-geoportal/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE terms=['verkehr','mobilit']; SET VARIABLE groups=['verkehr','mobilitaet'];" -c ".read scripts/topic_coverage.sql"
```

The same question against the index:

```bash
duckdb -c "SET VARIABLE u='https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE grp='verkehr';" -c ".read scripts/remote_queries.sql"
```

The sixteen-query suite, cold and warm, as a Markdown table. Cold time is given both as the `EXPLAIN ANALYZE` total and as the wall clock of the query in a fresh process, timed after the extensions load:

```bash
uv run python scripts/run_suite.py https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet --lon 13.405 --lat 52.52 --grp verkehr --kw Radverkehr --cat berlin-geoportal --id gruenflaechen/grillflaechen --runs 3
```

Add `--terms verkehr,mobilit` to run A6 as well, the topic query that `scripts/topic_coverage.sql` counts: collections at the point whose title or a keyword contains a term, across every group. Add `--parents-struct` on a file whose `parents` holds `{id, href}`, so the queries read the ids with `list_transform`. Add `--ranges` to list the byte ranges each query requests, from DuckDB's HTTP log, instead of timing it.

Measure against the published storage, not a local server. A mirror served with `python3 -m http.server` is fine for checking results, and useless for latency, for the reasons in [docs/method.md](docs/method.md).

### Synthetic benchmarks

Each folder under `benchmarks/` has a `build.sql` that writes a 5 million row file and a `queries.sql` that runs the comparison:

```bash
cd benchmarks/tree-designs && duckdb < build.sql && duckdb -c "SET VARIABLE f='tree_sorted.parquet';" -c ".read queries.sql"
```

## License

Apache-2.0 covers the code and the documentation. The metadata under `catalogs/`, and the copies of it in the `original` column of the files under `indexes/`, belong to the publishers of each catalog and stay under their terms. It is mirrored here so that the measurements can be reproduced after the published catalogs change.
