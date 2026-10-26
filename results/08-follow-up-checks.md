# Follow-up checks

Two variants built to close gaps that the earlier pages leave open. Built and measured locally on 2026-10-25. Measured over HTTPS on 2026-10-26 with DuckDB 2.0.0 and Python 3.14.9, in the same session as the query suite on page 04, 08:20 to 09:47 UTC, from the files under `_testbed/` listed in the [README](../README.md#3-upload).

## A links file with catalog rows

[Page 06](06-links-only-variant.md) measured a links-only file that holds only collections, where answering the theme question costs 178 requests. [Page 05](05-tree-designs.md) suggests catalog rows in the same file. This variant adds them: the Comunidad de Madrid links-only file plus one row for each of the 177 catalogs, with a `type` column, its public `href`, and its `links`. Scripts: `benchmarks/links-catalog-rows/`.

| File | Rows | Size |
|---|---|---|
| links only, `collections-links.parquet` | 1,964 | 1.50 MB |
| links with catalog rows, `collections-links-catalogs.parquet` | 2,141 | 1.56 MB |

The client reads `type`, `id`, `href`, and the parent link of every row in one query, resolves each parent link against its row's `href`, and climbs to the root in memory. It finds the 146 collections under `demografia`, the same answer as `list_contains(parents, 'demografia')`, with no request beyond the file. On the local file the whole client takes 0.08 to 0.11 s, of which the read is 0.06 to 0.10 s.

Over HTTPS, three runs, each with a new DuckDB connection so the file is read cold:

| Client | Requests | Time |
|---|---|---|
| Links with catalog rows, climb in memory | one file | 0.68 s, 0.67 s, 0.61 s, connection, extension load, read, and climb |
| `parents`, `list_contains(parents, 'demografia')`, T1 of the [query suite](04-query-suite.md) | 2 | 0.55 s, 0.57 s, 0.57 s, `EXPLAIN ANALYZE`; wall-clock median 0.56 s |

The two clients time slightly different spans, so the comparison is approximate: both read one file of about 1.5 MB, and the time is that read.

So catalog rows remove the extra fetches, and the links shape then costs about what `parents` costs. What remains against `parents` is the work the client does: it resolves relative URLs and climbs a tree in its own code, where `parents` is one SQL predicate, and the file has to carry the catalog rows. The file passes `gpio check` with 30 checks.

## Row groups without the confounds

[Page 03](03-portolan-registry.md) compared one row group in Hilbert order with three and twelve row groups in tree order, the twelve written by pyarrow. This variant keeps the Hilbert order and the DuckDB writer and changes only the row group size, to 2,048 rows: `collections-rg2048-hilbert.parquet`, 6.5 MB, three row groups. Script: `benchmarks/row-groups/build_hilbert.sql`.

| Row group | Rows | `bbox` statistics |
|---|---|---|
| 0 | 2,048 | -180 to 180, -90 to 90 |
| 1 | 2,048 | -180 to 180, -90 to 90 |
| 2 | 1,756 | -180 to 180, -90 to 90 |

Every row group still spans the globe, because each holds some global datasets. No spatial filter can skip a row group on this file either, which confirms that the lack of pruning on page 04 comes from the data and not from the sort order. The point query gives 2,254 on both files. gpio flags the file for its small row groups and its spatial overlap.

Over HTTPS, cold medians of 3 from the full suite, against the tree-order file with the same row group size, in the same session:

| Query | Hilbert order: requests, bytes, time | Tree order: requests, bytes, time |
|---|---|---|
| S1 point in extent, whole file | 8, 2.8 MB, 0.94 s | 8, 2.8 MB, 1.11 s |
| S2 point in extent, under one group | 8, 2.8 MB, 0.91 s | 8, 2.8 MB, 0.90 s |
| S3 box on the `bbox` struct | 5, 121 KB, 0.46 s | 5, 117 KB, 0.48 s |
| T1 everything under one group | 11, 3.0 MB, 1.05 s | 11, 3.0 MB, 0.90 s |
| D1 one full document | 10, 5.3 MB, 1.86 s | 9, 3.3 MB, 0.93 s |

The spatial queries read the same bytes in the same requests in either order. The sort order changes only which row group holds a given document, and so how large a chunk of `original` the lookup reads. The full suite on the Hilbert-ordered file:

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048-hilbert.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 8 | 2.8MiB | 0.94, 0.89, 0.98 s | 0.94 s | 0.95 s | 0.05 s |
| S2 point in extent, under one group | 150 | 8 | 2.8MiB | 0.99, 0.87, 0.91 s | 0.91 s | 0.93 s | 0.05 s |
| S3 box intersects extent, bbox struct only | 2254 | 5 | 120.7KiB | 0.47, 0.46, 0.45 s | 0.46 s | 0.46 s | 0.06 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 8 | 2.9MiB | 1.01, 1.20, 0.90 s | 1.01 s | 0.96 s | 0.08 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 12 | 3.0MiB | 1.16, 1.17, 1.23 s | 1.17 s | 1.14 s | 0.07 s |
| T1 everything under one group, id and title | 162 | 11 | 3.0MiB | 1.14, 0.97, 1.05 s | 1.05 s | 1.00 s | 0.06 s |
| T2 collections per direct parent | 790 | 8 | 2.8MiB | 0.89, 1.03, 0.98 s | 0.98 s | 0.97 s | 0.06 s |
| T3 one catalog by root id, one group | 146 | 8 | 2.8MiB | 0.84, 0.93, 2.84 s | 0.93 s | 0.94 s | 0.06 s |
| A1 keyword equality | 261 | 8 | 1.9MiB | 0.84, 0.84, 0.79 s | 0.84 s | 0.81 s | 0.09 s |
| A2 title substring, case-insensitive | 50 | 5 | 120.7KiB | 0.62, 0.48, 0.45 s | 0.48 s | 0.45 s | 0.06 s |
| A3 description substring | 186 | 5 | 496.7KiB | 0.58, 0.62, 0.59 s | 0.59 s | 0.57 s | 0.07 s |
| A4 license equality | 3 | 5 | 28.7KiB | 0.49, 0.41, 0.44 s | 0.44 s | 0.40 s | 0.06 s |
| A5 temporal: end open or after 2024 | 5671 | 5 | 28.7KiB | 0.47, 0.44, 0.43 s | 0.44 s | 0.40 s | 0.06 s |
| D1 one full document by catalog and id | 1 | 10 | 5.3MiB | 1.86, 2.01, 1.28 s | 1.86 s | 2.12 s | 0.07 s |
| D2 field inside the JSON document for a group: providers | 20 | 12 | 5.9MiB | 1.42, 1.42, 1.62 s | 1.42 s | 1.52 s | 0.09 s |
| C1 combined: group, point, keyword, title returned | 42 | 13 | 3.1MiB | 1.03, 1.01, 1.09 s | 1.03 s | 1.20 s | 0.09 s |

## Reproduce

The files are served from the URLs in the README. Run:

```bash
uv run python benchmarks/links-catalog-rows/theme.py https://storage.googleapis.com/carto-open-catalogs/_testbed/comunidad-madrid/collections-links-catalogs.parquet demografia 3
uv run python scripts/run_suite.py https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048-hilbert.parquet --lon -3.7038 --lat 40.4168 --grp demografia --kw Total --cat comunidad-madrid-datos-abiertos --id demografia/a-c/adquisiciones-de-nacionalidad-espanola-por-sexo-y-grupo-de-edad --runs 3
```

The second compares directly with the one-row-group table on [page 04](04-query-suite.md).
