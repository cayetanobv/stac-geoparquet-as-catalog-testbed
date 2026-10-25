# Follow-up checks

Two variants built to close gaps that the earlier pages leave open. Measured on 2026-10-25 with DuckDB 2.0.0 and Python 3.14.9, on local files. The remote measurements are still to do; the commands are at the end.

## A links file with catalog rows

[Page 06](06-links-only-variant.md) measured a links-only file that holds only collections, where answering the theme question costs 178 requests. [Page 05](05-tree-designs.md) suggests catalog rows in the same file. This variant adds them: the Comunidad de Madrid links-only file plus one row for each of the 177 catalogs, with a `type` column, its public `href`, and its `links`. Scripts: `benchmarks/links-catalog-rows/`.

| File | Rows | Size |
|---|---|---|
| links only, `collections-links.parquet` | 1,964 | 1.50 MB |
| links with catalog rows, `collections-links-catalogs.parquet` | 2,141 | 1.56 MB |

The client reads `type`, `id`, `href`, and the parent link of every row in one query, resolves each parent link against its row's `href`, and climbs to the root in memory. It finds the 146 collections under `demografia`, the same answer as `list_contains(parents, 'demografia')`, with no request beyond the file. On the local file the whole client takes 0.08 to 0.11 s, of which the read is 0.06 to 0.10 s.

So catalog rows remove the extra fetches. What remains against `parents` is the work the client does: it resolves relative URLs and climbs a tree in its own code, where `parents` is one SQL predicate, and the file has to carry the catalog rows. The file passes `gpio check` with 30 checks.

## Row groups without the confounds

[Page 03](03-portolan-registry.md) compared one row group in Hilbert order with three and twelve row groups in tree order, the twelve written by pyarrow. This variant keeps the Hilbert order and the DuckDB writer and changes only the row group size, to 2,048 rows: `collections-rg2048-hilbert.parquet`, 6.5 MB, three row groups. Script: `benchmarks/row-groups/build_hilbert.sql`.

| Row group | Rows | `bbox` statistics |
|---|---|---|
| 0 | 2,048 | -180 to 180, -90 to 90 |
| 1 | 2,048 | -180 to 180, -90 to 90 |
| 2 | 1,756 | -180 to 180, -90 to 90 |

Every row group still spans the globe, because each holds some global datasets. No spatial filter can skip a row group on this file either, which confirms that the lack of pruning on page 04 comes from the data and not from the sort order. The point query gives 2,254 on both files. gpio flags the file for its small row groups and its spatial overlap.

## Remote measurements to do

Upload both files with the Parquet content type next to the other test files, then run:

```bash
uv run python benchmarks/links-catalog-rows/theme.py <URL of collections-links-catalogs.parquet> demografia 3
uv run python scripts/run_suite.py <URL of collections-rg2048-hilbert.parquet> --lon -3.7038 --lat 40.4168 --grp demografia --kw Total --cat comunidad-madrid-datos-abiertos --id <collection id> --runs 3
```

The second compares directly with the one-row-group table on [page 04](04-query-suite.md).
