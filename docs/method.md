# Method

## The question

Every per-catalog results page asks the same question: collections under one group of the tree whose extent contains a point. It is what an SDI user asks, "what transport data is there for this place", and it is the smallest query that touches everything under test. The group filter exercises the `parents` column, the point debated upstream, and in Madrid it is a mid-tree case that a direct-parent column cannot answer. The point filter exercises the GeoParquet side, geometry and `bbox` covering. Because the extent lives inside each `collection.json`, a client without the index has to open every collection document to answer it, so the walk pays its real cost. Both methods return the same count, which is how an antimeridian defect was caught. The [query suite](../results/04-query-suite.md) adds fifteen more shapes.

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
| DuckDB | 1.5.6 CLI with the `spatial` and `httpfs` extensions |
| gpio | 1.1.0b1 |
| Python | 3.10 |
| Round trip to Google Cloud Storage from the test machine | about 150 ms |

Two outlier runs of 5 and 10 s occurred while a background walk competed for the network. They are reported on the registry page and excluded from its tables.

## Known pitfalls

- Source Cooperative and one Cloudflare R2 host answer HTTP 403 to Python's default User-Agent. The mirror scripts send a named one.
- Reading the `geo` key back through `parquet_kv_metadata()` with a cast to text escapes every quote. Use `decode(value)`, or the derived file opens with `geometry` as a plain blob.
- A rewrite through pyarrow drops the bloom filters DuckDB wrote. DuckDB still prunes on pyarrow's statistics, although `parquet_metadata()` does not display them.
- DuckDB writes row groups of at least 2,048 rows. pyarrow honours smaller sizes.
