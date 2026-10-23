# Method

## The question

The headline measurement on every catalog page is one question: collections under one group of the tree whose extent contains a point. For the registry it is the point alone, across every catalog. It is what an SDI user asks, "what transport data is there for this place", and it is the smallest query that touches everything under test. The group filter exercises the `parents` column, the point debated upstream, and in Madrid it is a mid-tree case that a direct-parent column cannot answer. The point filter exercises the GeoParquet side, geometry and `bbox` covering. Because the extent lives inside each `collection.json`, a client without the index has to open every collection document to answer it, so the walk pays its real cost. Both methods return the same count, which is how an antimeridian defect was caught. The [query suite](../results/04-query-suite.md) adds sixteen more shapes and seven against real polygons, and the synthetic benchmarks compare designs at a scale no real catalog reaches.

## Why the measurements are remote

The cost under test is network round trips. A static catalog is a tree of small JSON documents on object storage, one request per document, and each request costs a fixed round trip. A Parquet reader asks for the footer and the column chunks the query needs, a fixed four or five requests whatever the row count. Locally both finish in milliseconds and the difference disappears. A local HTTP server distorts the ratio in both directions: Python's server is single threaded, has no keep-alive, and handles range requests badly. So every latency figure comes from the published catalog on its real storage, with the index uploaded beside it, both methods run from the same machine in the same session.

The local mirrors under `catalogs/` serve correctness and reproduction. They prove the index builder produces the same rows from the same documents and they keep working after the published catalogs change.

Times depend on where you measure from. The request counts do not, so they are the durable result.

## Two baselines

The JSON walk runs twice: sequential, one request at a time, which is what a browser or a plain script does, and with 16 threads, which is the best a careful client does. The index query runs cold, a fresh DuckDB process per run so nothing is cached, and warm, repeated in one process after a first run. Cold includes the TLS handshake. Warm is the range requests alone on an open connection.

## Environment

| Item | Value |
|---|---|
| Dates | 2026-10-22 and 2026-10-23 |
| DuckDB | 2.0.0 CLI with the `spatial` and `httpfs` extensions, released 2026-10-21 |
| Python | 3.14.9, with duckdb 2.0.0 and pyarrow 26.0.0 pinned in `pyproject.toml` and `uv.lock` |
| gpio | 1.7.0 |
| Round trip to Google Cloud Storage from the test machine | about 150 ms |

Every number in `results/` comes from one recompute on 2026-10-23 with this toolchain, after an earlier pass with DuckDB 1.5.6, Python 3.10, and gpio 1.0 on 2026-10-22. The indexes were rebuilt with the pinned toolchain and hold the same rows as before. Where the two engines disagree, the pages say so: DuckDB 2.0's prefetch cost model reads small files whole and penalises extra row groups, which 1.5.6 did not.

Cold runs vary by up to a factor of two between repeats on the same query. The suite tables list every run beside the median for that reason.

## Known pitfalls

- Source Cooperative and one Cloudflare R2 host answer HTTP 403 to Python's default User-Agent. The mirror scripts send a named one.
- Reading the `geo` key back through `parquet_kv_metadata()` with a cast to text escapes every quote. Use `decode(value)`, or the derived file opens with `geometry` as a plain blob.
- A rewrite through pyarrow drops the bloom filters DuckDB wrote. DuckDB still prunes on pyarrow's statistics, although `parquet_metadata()` does not display them.
- DuckDB writes row groups of at least 2,048 rows. pyarrow honours smaller sizes.
- DuckDB 2.0 rejects the `x -> expr` lambda syntax from its Python module and accepts it with a deprecation in the CLI. The scripts use `lambda x: expr`.
- The DuckDB 2.0 CLI switches to a JSON "agent mode" when it detects an agent environment variable and stdout is not a terminal. Pass `-no-agent` in that situation.
- An explicit `"crs": null` in the `geo` metadata means an unknown CRS. Omit the key to mean OGC:CRS84. gpio 1.7.0 warns about the null; gpio 1.0 did not.
- With the `spatial` extension loaded, DuckDB adds its own `geo` key when it writes a geometry column. A `KV_METADATA` `geo` key on top of it gives the file two `geo` keys, and readers pick different ones. Write the geometry as a WKB blob, with `ST_AsWKB`, when you pass the metadata yourself. gpio 1.7.0 fails a file with two keys; gpio 1.0 did not.
- A published GeoParquet file can carry the duplicate `geo` key too: the Madrid city catalog's `BARRIOS.parquet` has two. Readers that take the first key still work; validators flag it.
- A region file in a projected CRS, such as EPSG:25830, needs `ST_Transform(geom, 'EPSG:25830', 'EPSG:4326', always_xy := true)` before it meets OGC:CRS84 extents. Without `always_xy` DuckDB applies the EPSG axis order and swaps longitude and latitude.
- The geoparquet-io package pins duckdb below 1.6, so gpio lives in its own environment, installed with pipx, while the project environment carries duckdb 2.0.
