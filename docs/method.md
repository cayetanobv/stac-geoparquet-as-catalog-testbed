# Method

## The question

The headline measurement on every catalog page is one question: collections under one group of the tree whose extent contains a point. For the registry it is the point alone, across every catalog. It is what an SDI user asks, "what transport data is there for this place", and it is the smallest query that touches everything under test. The group filter exercises the `parents` column, the point debated upstream, and in Madrid it is a mid-tree case that a direct-parent column cannot answer. The point filter exercises the GeoParquet side, geometry and `bbox` covering. Because the extent lives inside each `collection.json`, a client without the index has to open every collection document to answer it, so the walk pays its real cost. Both methods return the same count, which is how an antimeridian defect was caught. The [query suite](../results/04-query-suite.md) adds sixteen more shapes and seven against real polygons, and the synthetic benchmarks compare designs at a scale no real catalog reaches.

## Why the measurements are remote

The cost under test is network round trips. A static catalog is a tree of small JSON documents on object storage, one request per document, and each request costs a fixed round trip. A Parquet reader asks for the footer and the column chunks the query needs, a few requests that do not grow with the row count. DuckDB 2.0 goes further on small files: when the gaps between the byte ranges it needs are small, it reads the whole file in one request. Locally both finish in milliseconds and the difference disappears. A local HTTP server distorts the ratio in both directions: Python's server is single threaded, has no keep-alive, and handles range requests badly. So every latency figure comes from the published catalog on its real storage, with the index uploaded beside it, both methods run from the same machine in the same session.

The local mirrors under `catalogs/` serve correctness and reproduction. They prove the index builder produces the same rows from the same documents and they keep working after the published catalogs change.

Times depend on where you measure from. The request counts do not, so they are the durable result.

## Two baselines

The JSON walk runs at three levels of concurrency: 1, one request at a time, which is what a plain script does; 6, what a browser keeps in flight per host over HTTP/1.1; and 16, a client tuned for the task. Concurrency is the number of requests in flight, one thread each. The threads wait on the network, so the number is not tied to CPU cores. Each level runs in two connection modes. By default each thread keeps one connection alive per host, as a well-written client does. With `fresh` it opens a new connection for every document, as `urllib` does and as the measurements before 2026-10-25 did, so every request pays TCP and TLS setup. The request counts are the same in both modes. The walk times are wall clock for the whole walk.

The walk of a group either knows the group in advance, as the client would if a person had picked it, or finds it. A client that finds it fetches the root and keeps every child whose link title contains a term, without case or accents, or with `describe:` also fetches every child catalog and matches its title and description. `scripts/topic_coverage.sql` then counts how many collections about the same terms, by title and keywords, sit under the chosen groups.

The index query runs cold, a fresh DuckDB process per run so nothing is cached, and warm, repeated in one process after a first run. Both are reported as the Total Time of `EXPLAIN ANALYZE`, which gives the request count and bytes read as well. It includes the TLS handshake and the reads made while the query runs, and leaves out process start, extension loading, and any read DuckDB makes while planning. A box test on the `bbox` struct shows 0.00 s for that reason: DuckDB answers it from the footer while planning. So cold time is also measured as wall clock: the plain query in a fresh Python process, timed from after the extensions load until the rows are fetched. That includes planning and leaves out process start. The two come from separate cold runs, so they differ by the noise between runs, up to 0.2 s on most queries and up to 0.6 s where one run was slow, and neither is consistently higher. The exception is that box test, where only the wall clock shows the file read, at the same cost as the other queries. Warm is a cache hit: DuckDB sends one HEAD request to check the file and reads no data.

## Environment

| Item | Value |
|---|---|
| Dates | Mirrors and indexes 2026-10-22 and 2026-10-23; remote timings on 2026-10-26 in two sessions: the query suite on page 04 and the checks on page 08 from 08:20 to 09:47 UTC, the walks and the headline index queries on pages 01 to 03 from 13:30 to 15:40 UTC |
| DuckDB | 2.0.0 CLI with the `spatial` and `httpfs` extensions, released 2026-10-21 |
| Python | 3.14.9, with duckdb 2.0.0 and pyarrow 26.0.0 pinned in `pyproject.toml` and `uv.lock` |
| gpio | 1.7.0 |
| Round trip to Google Cloud Storage from the test machine | 60 to 75 ms, measured with curl at the start of each session: TCP connect took 0.062 s and TLS setup ended at 0.144 s in the morning, 0.073 s and 0.162 s in the afternoon |

The remote timings come from two sessions on 2026-10-26, both run with the machine kept from sleeping. The morning session ran the query suite, the checks on page 08, and the walks, whose times the afternoon session replaces. The afternoon session reran the walks at three levels of concurrency, added the walks that find their group, and ran the headline index query of each fixture at its start and its end; those are the numbers on pages 01 to 03 and in the README. The same index query took up to almost twice as long at the start of the afternoon session as at its end, so times within one session also carry that much noise. Every result count, request count, and byte count matches the recompute of 2026-10-23, except where a page says otherwise. Times from different sessions are not compared in these pages. Pages 05 to 07 come from the recompute of 2026-10-23, which followed an earlier pass with DuckDB 1.5.6, Python 3.10, and gpio 1.0 on 2026-10-22 and early on 2026-10-23. The indexes were rebuilt with the pinned toolchain and hold the same rows as before. Where the two engines disagree, the pages say so: DuckDB 2.0's prefetch cost model reads small files whole and penalises extra row groups, which 1.5.6 did not.

Cold runs vary by up to a factor of four between repeats on the same query. The suite tables list every run beside the median for that reason.

KB and MB in these pages are KiB and MiB.

## Known pitfalls

- Source Cooperative and one Cloudflare R2 host answer HTTP 403 to Python's default User-Agent. The mirror scripts send a named one.
- Reading the `geo` key back through `parquet_kv_metadata()` with a cast to text escapes every quote. Use `decode(value)`, or the derived file opens with `geometry` as a plain blob.
- A rewrite through pyarrow drops the bloom filters DuckDB wrote. DuckDB still prunes on pyarrow's statistics, although `parquet_metadata()` does not display them.
- DuckDB writes row groups of at least 2,048 rows. pyarrow honours smaller sizes.
- DuckDB 2.0 rejects the `x -> expr` lambda syntax from its Python module and accepts it with a deprecation in the CLI. The scripts use `lambda x: expr`.
- The DuckDB 2.0 CLI switches to a JSON "agent mode" when it detects an agent environment variable and stdout is not a terminal. Pass `-no-agent` in that situation.
- The DuckDB Python module prints a progress bar to stdout on a query that runs for more than about two seconds. `SET enable_progress_bar = false` before parsing its output.
- An explicit `"crs": null` in the `geo` metadata means an unknown CRS. Omit the key to mean OGC:CRS84. gpio 1.7.0 warns about the null; gpio 1.0 did not.
- With the `spatial` extension loaded, DuckDB adds its own `geo` key when it writes a geometry column. A `KV_METADATA` `geo` key on top of it gives the file two `geo` keys, and readers pick different ones. Write the geometry as a WKB blob, with `ST_AsWKB`, when you pass the metadata yourself. gpio 1.7.0 fails a file with two keys; gpio 1.0 did not.
- A published GeoParquet file can carry the duplicate `geo` key too: the Madrid city catalog's `BARRIOS.parquet` has two. Readers that take the first key still work; validators flag it.
- A region file in a projected CRS, such as EPSG:25830, needs `ST_Transform(geom, 'EPSG:25830', 'EPSG:4326', always_xy := true)` before it meets OGC:CRS84 extents. Without `always_xy` DuckDB applies the EPSG axis order and swaps longitude and latitude.
- The geoparquet-io package pins duckdb below 1.6, so gpio lives in its own environment, installed with pipx, while the project environment carries duckdb 2.0.
