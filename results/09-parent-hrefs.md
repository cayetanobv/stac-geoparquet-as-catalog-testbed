# Ancestor hrefs in the index

In radiantearth/stac-geoparquet-spec#17 the question came up of how a reader outside Portolan learns the `href` of each ancestor in `parents`, and whether `parents` should become a list of `{id, href}`. This page measures what carrying the hrefs costs, in two shapes, against the published index, which holds ids only.

| Shape | Columns | File name |
|---|---|---|
| Ids | `parents`: list of ancestor ids, as on every other page | `collections.parquet` |
| Struct | `parents`: list of `{id, href}` | `collections-parents-struct.parquet` |
| Two columns | `parents`: list of ids, as published, and `parent_hrefs`: list of hrefs, the href of `parents[i]` at `parent_hrefs[i]` | `collections-parent-hrefs.parquet` |

## The files

Built on 2026-10-27 from the committed indexes and the committed mirrors. `scripts/crawl.py` and `scripts/crawl_registry.py` now also record the public URL of each ancestor catalog, and `scripts/parent_hrefs.sql` writes both variants from an index and that crawl. Every other column, the row order, and the geo metadata are copied from the committed index. The hrefs are absolute and always filled.

| Index | Rows | Ids | Struct | Two columns | `href` leaf, compressed |
|---|---|---|---|---|---|
| Berlin | 371 | 312.5 KB | 313.9 KB | 313.9 KB | 0.9 KB |
| Madrid | 1,964 | 1.48 MB | 1.48 MB | 1.48 MB | 1.6 KB |
| Registry | 5,852 | 6.47 MB | 6.49 MB | 6.49 MB | 21.4 KB |

Checked in every row of all three indexes: each collection found its crawl line with the same chain of ids, the two-column file equals the published one in every column, `parents` included, `parent_hrefs` has the length of `parents`, and zipping the two gives exactly the struct file's `parents`. All six files have one row group and pass the 30 checks of `gpio check`. In both shapes the ids and the hrefs are separate column chunks, each with a bloom filter, of the same size, so the two shapes store the same bytes; the files differ by 23 bytes of schema.

## The queries

Every query of the [suite](04-query-suite.md) that reads `parents`, S2, T1, T2, T3, D1, D2 and C1, and S1, which does not, as a control. On the struct file `scripts/run_suite.py --parents-struct` reads the ids with `list_transform(parents, lambda p: p.id)`. All three shapes returned the same results for every query on every index.

One session on 2026-10-27, 17:51 to 18:07 UTC, from the test machine in [docs/method.md](../docs/method.md). Each file ran the suite at the start and at the end of the session, the shapes in the order ids, struct, two columns at the start and in reverse at the end, so a change in the network does not favour one shape. Cells are the cold wall-clock median of 3 runs in a fresh process, start / end.

**Berlin**, 2 requests (1 HEAD, 1 GET) for every query in every shape, the whole file.

| Query | Result | Ids | Struct | Two columns |
|---|---|---|---|---|
| S1 control | 367 | 0.41 / 0.56 s | 0.40 / 0.44 s | 0.40 / 0.42 s |
| S2 point under one group | 19 | 0.42 / 0.63 s | 0.40 / 0.39 s | 0.41 / 0.48 s |
| T1 everything under one group | 19 | 0.45 / 0.62 s | 0.39 / 0.44 s | 0.44 / 0.40 s |
| T2 collections per direct parent | 36 | 0.38 / 0.50 s | 0.40 / 0.47 s | 0.41 / 0.41 s |
| T3 root id and group | 19 | 0.43 / 0.80 s | 0.41 / 0.45 s | 0.40 / 0.45 s |
| D1 one document | 1 | 0.43 / 0.43 s | 0.40 / 0.41 s | 0.41 / 0.43 s |
| D2 JSON field for a group | 19 | 0.42 / 0.50 s | 0.41 / 0.42 s | 0.40 / 0.42 s |
| C1 combined | 3 | 0.39 / 0.47 s | 0.44 / 0.49 s | 0.39 / 0.43 s |

**Madrid**, 2 requests for every query in every shape, the whole file.

| Query | Result | Ids | Struct | Two columns |
|---|---|---|---|---|
| S1 control | 1,964 | 0.56 / 0.67 s | 0.66 / 0.52 s | 0.70 / 0.52 s |
| S2 point under one group | 146 | 0.56 / 0.69 s | 0.69 / 0.58 s | 0.59 / 0.55 s |
| T1 everything under one group | 146 | 0.56 / 0.68 s | 0.69 / 0.56 s | 0.60 / 0.51 s |
| T2 collections per direct parent | 159 | 0.57 / 0.67 s | 0.64 / 0.56 s | 0.67 / 0.69 s |
| T3 root id and group | 146 | 0.56 / 0.57 s | 0.68 / 0.68 s | 0.71 / 0.63 s |
| D1 one document | 1 | 0.59 / 0.57 s | 0.67 / 0.55 s | 0.68 / 0.55 s |
| D2 JSON field for a group | 20 | 0.56 / 0.55 s | 0.67 / 0.68 s | 0.69 / 0.56 s |
| C1 combined | 42 | 0.57 / 0.57 s | 0.60 / 0.65 s | 0.67 / 0.59 s |

**Registry**, the same requests in every shape: 4 for S1, S2, T2 and T3, 5 for T1, 7 for D1, D2 and C1. The bytes are in the next section.

| Query | Result | Ids | Struct | Two columns |
|---|---|---|---|---|
| S1 control | 2,254 | 0.60 / 0.66 s | 0.61 / 0.71 s | 0.66 / 0.61 s |
| S2 point under one group | 150 | 0.66 / 0.65 s | 0.62 / 0.62 s | 0.75 / 0.61 s |
| T1 everything under one group | 162 | 0.74 / 0.84 s | 0.77 / 0.74 s | 0.75 / 0.72 s |
| T2 collections per direct parent | 790 | 0.62 / 0.64 s | 0.66 / 0.69 s | 0.68 / 0.60 s |
| T3 root id and group | 146 | 0.60 / 0.63 s | 0.65 / 0.60 s | 0.67 / 0.61 s |
| D1 one document | 1 | 1.28 / 1.40 s | 1.37 / 1.24 s | 1.48 / 1.66 s |
| D2 JSON field for a group | 20 | 1.27 / 1.53 s | 1.43 / 1.37 s | 1.66 / 1.34 s |
| C1 combined | 42 | 0.93 / 1.01 s | 0.88 / 0.97 s | 0.91 / 0.94 s |

Warm medians were 0.05 to 0.10 s in every shape. Which shape is fastest changes between the start and the end of the session and from query to query, the control S1 included, so the differences are the network, not the shape. In Madrid the ids ran first at the start and were the fastest on every query there, and ran last at the end and were the slowest on four.

## Does the reader skip the hrefs?

A query that needs only the ids does not need the hrefs, and a Parquet reader can leave their column chunk out. DuckDB 2.0 fetches it anyway at these sizes, inside a read it makes for other columns. Berlin and Madrid are read whole in every shape, so only the registry can show it.

Where the columns sit in the registry files, in bytes from the start of the file. The other columns follow in the same order in all three, shifted by the hrefs.

| Column chunk | Ids | Struct | Two columns |
|---|---|---|---|
| `id` | 4 to 74,666 | 4 to 74,666 | 4 to 74,666 |
| `parents`, the ids | 74,666 to 92,527 | 74,666 to 92,527 | 74,666 to 92,527 |
| The ancestor hrefs | none | 92,527 to 114,449 | 92,527 to 114,449 |
| `href` of the collection | 92,527 to 192,187 | 114,449 to 214,109 | 114,449 to 214,109 |
| `geometry` | 192,187 to 301,165 | 214,109 to 323,087 | 214,109 to 323,087 |
| `bbox`, four chunks | 301,165 to 393,080 | 323,087 to 415,002 | 323,087 to 415,002 |
| `description` | 397,419 to 850,367 | 419,341 to 872,289 | 419,341 to 872,289 |
| `original` | 851,904 to 6,196,130 | 873,826 to 6,218,052 | 873,826 to 6,218,052 |

The byte ranges DuckDB requested, from its HTTP log, one fresh process per query, after a HEAD request for the file size. Every first range is the footer.

| Query | Ids | Struct | Two columns |
|---|---|---|---|
| S1 control, `geometry` | 6,766,592-6,784,578, 188,416-192,511, 192,512-1,196,031: 1,025,603 B | 6,791,168-6,808,981, 212,992-217,087, 217,088-1,216,511: 1,021,334 B | 6,791,168-6,809,004, 212,992-217,087, 217,088-1,216,511: 1,021,357 B |
| S2, T2, T3: `parents` and `geometry` | 6,766,592-6,784,578, 73,728-77,823, 77,824-1,077,247: 1,021,507 B | 6,791,168-6,808,981, 73,728-77,823, 77,824-1,077,247: 1,021,334 B | 6,791,168-6,809,004, 73,728-77,823, 77,824-1,077,247: 1,021,357 B |
| T1, also `id` and `title` | 4 ranges, 1,189,443 B | 4 ranges, 1,185,174 B | 4 ranges, 1,185,197 B |
| C1, also `keywords` | 6 ranges, 1,771,075 B | 6 ranges, 1,774,998 B | 6 ranges, 1,775,021 B |
| D1, D2, `original` | 6 ranges, 6,215,235 B | 6 ranges, 6,239,638 B | 6 ranges, 6,239,661 B |

Logged on 2026-10-27, 19:30 to 19:31 UTC, with `scripts/run_suite.py --ranges`. The totals equal the bytes that `EXPLAIN ANALYZE` reported in the timed session, 997.5, 997.3 and 997.4 KB for S2.

Every range starts and ends on a multiple of 4,096 bytes. DuckDB fetches the 4 KB block where the first column it needs begins, then one range from the next block to the block that holds the point 1,000,000 bytes after that column's start. S2 needs `parents` from 74,666, so it reads 73,728 to 1,077,247, which holds `parents`, `geometry` and `bbox`, and also everything between them that it does not need. In the struct and two-column files that includes the ancestor hrefs; in all three it includes the collection `href` and part of `description`. Where the data a query needs starts at the same offset, the data ranges are the same in every shape. The totals differ only by the footer, which starts on a block boundary, so its length depends on where the file ends. S1 starts at `geometry`, which the hrefs move by 21,922 bytes, so its range moves with it; on the ids file the range happens to span one more block, 4,096 bytes.

The hrefs show in the bytes only where a query reads `original`, which spans most of the file: D1 and D2 read everything from the start of the file to the end of `original`, so the struct file costs 24,403 bytes more: the 21,922 bytes of hrefs, and block rounding and the footer. The 1,000,000-byte window is read from the log, not from DuckDB's documentation. Whether DuckDB, or another reader, leaves the hrefs out on a file whose columns are farther apart than that window was not measured.

## What it means for the schema

Carrying the hrefs costs nothing measurable at these sizes, in either shape, in DuckDB 2.0. The choice between the two shapes rests on other grounds:

- **Two columns** keep `parents` a list of strings, so the filter stays `list_contains(parents, 'transport')` in DuckDB and the equivalent in other engines, and `parent_hrefs` can be optional. A writer whose ancestors a reader can find otherwise leaves it out, and every file measured on the other pages stays valid. The spec has to say that the two lists have the same length and order.
- **A struct** keeps each id with its href and matches how `links` is stored. Every filter on the ids needs a lambda or an unnest, and an optional href becomes a nullable field.

Readers other than DuckDB were not measured. [Page 07](07-list-shapes.md) found that DuckDB does not push a filter on a list of structs into the scan; at 5,852 rows in one row group that costs nothing visible, but it may at the sizes on that page.
