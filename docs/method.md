# Method

## The question

The main question on every catalog page is the one a user brings to a catalog: which collections about a topic cover this place? Without the file, a client opens every `collection.json`, because the extent is only there. With the file, the client runs one query. Both methods return the same count, which is how the testbed found the antimeridian defect. Page 04 adds sixteen more query shapes and seven queries with real polygons. Pages 05 and 07 use synthetic files of 5 million rows, a size that no real catalog reaches.

## Why the measurements are remote

The cost under test is network round trips. A static catalog needs one request per JSON document. A Parquet reader needs a few requests for the footer and the column chunks, and that number does not grow with the rows. DuckDB 2.0 reads a file of a few MB whole, in one request. Locally, both methods finish in milliseconds. A local HTTP server distorts the ratio, because Python's server has one thread and no keep-alive. So every time comes from the published storage, from the same machine, with both methods in the same session.

Times depend on where you measure from. The request counts do not, so they are the durable result.

## How each method is timed

- **The JSON walk** keeps 1, 6 or 16 requests in flight. 1 is a plain script, 6 is a typical HTTP/1.1 client, 16 is a client tuned for the task. Each thread reuses one connection per host. With `fresh`, it opens a new connection per document, as the measurements before 2026-10-25 did. The walk of a group either knows the group or finds it from the link titles of the root.
- **The query on the file** runs cold, in a fresh DuckDB process, and warm, a second time in the same process. `EXPLAIN ANALYZE` gives the requests and the bytes. Its total time leaves out the reads that DuckDB makes while it plans, so the cold time is also the wall clock of the query in a fresh process, after the extensions load. A warm run is a cache hit: one HEAD request and no data read.

Cold runs of the same query vary by up to four times. The tables give every run beside the median.

## Environment

DuckDB 2.0.0 CLI with `spatial` and `httpfs`, Python 3.14.9 with duckdb 2.0.0 and pyarrow 26.0.0 as pinned in `uv.lock`, gpio 1.7.0. The round trip to Google Cloud Storage from the test machine was 40 to 75 ms.

| Pages | Measured |
|---|---|
| 01 to 03, the walks and the group queries | 2026-10-26, 13:30 to 15:40 UTC |
| README headline | 2026-10-26, 18:41 to 19:02 UTC |
| 04 and 08 | 2026-10-26, 08:20 to 09:47 UTC |
| 05 to 07 | 2026-10-23, local |
| 09 | 2026-10-27, 17:51 to 18:07 UTC |
| 10 | 2026-11-06, local |
| 11 | 2026-11-19, 23:12 to 23:16 UTC |

The pages compare only times from the same session. In one session the same query took up to twice as long at the start as at the end. Before 2026-10-23 the testbed used DuckDB 1.5.6. Where the two versions disagree, the pages say so.

KB and MB in these pages are KiB and MiB, except on pages 10 and 11, where MB is 10⁶ bytes.

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
- The geoparquet-io package pins duckdb below 1.6, so the indexes measured here were checked with gpio 1.7.0 in its own environment. The build scripts now run `scripts/check_index.sql` in DuckDB 2.0 instead, and every committed index with a `parents` column passes it.
