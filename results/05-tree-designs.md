# Alternatives for the tree column

Which column shape answers "every collection under this node" fastest in one flat file, for static catalogs that are published and updated independently. Synthetic tree with 5 million collections under root, 50 catalogs, 20 sub-catalogs each, 5 shards each, plus 6,050 catalog rows in the same file. Written twice, once sorted in tree order and once in random order, 100,000 rows per row group. Measured on 2026-10-23 with DuckDB 2.0.0, local files, best of two runs. Scripts: `benchmarks/tree-designs/`.

The question is the subtree of one level-1 catalog, 100,000 rows.

| Design | Sorted by tree | Random order | Generic STAC safe |
|---|---|---|---|
| `parents` list, `list_contains` | 35 ms, 0.25 s CPU | 71 ms, 0.55 s CPU | yes |
| Materialized `path` string, prefix `LIKE` | 14 ms, 0.03 s CPU | 106 ms, 0.87 s CPU | needs an escaping rule |
| Flat per-level columns `p1`, `p2`, `p3` | 5 ms, 0.02 s CPU | 14 ms, 0.09 s CPU | no, fixed depth |
| `parent` only, recursive CTE over catalog rows | 519 ms, 1.18 s CPU | 210 ms, 1.38 s CPU | only with a unique key for every catalog row; ids are unique only among siblings |

File size: 89 MB sorted in tree order, 183 MB in random order.

The recursive CTE joins on the materialized path, so it inherits the path's escaping problem; a version that joins on ids needs globally unique ids, which STAC does not guarantee. Its wall time is lower on the random-order file than on the sorted one while its CPU time is higher. That was not investigated.

Rejected without measurement:

- Nested-set intervals. Fastest subtree query, but every insertion renumbers the whole tree. Catalogs published independently cannot do that.
- A separate closure table. Two files and a join.

## Assessment

The materialized path is the only serious rival to `parents`. It is eight times cheaper in CPU when the file is sorted in tree order, because prefix matches prune row groups, and the sort halves the file. But it needs a separator that cannot appear in an id, and STAC does not restrict ids. In the Comunidad de Madrid catalog the shard id `demografia/e-i` contains a slash. A slash-joined path has a false-positive case for a sibling whose id starts with `demografia/`. A spec would have to define an escaping rule for every writer and reader, for a gain measured at 5 million rows, three orders of magnitude above the largest real catalog here. Sizes between were not measured.

Every real catalog in the registry fits in one row group. There the whole file is one to four HTTP round trips and the shape of the tree column is invisible. The Comunidad de Madrid remote queries show it: the `parents` filter and the plain point filter cost the same.

Two changes that do help, independent of the tree column:

- Catalog rows in the same file, with a `type` column. A client can then render the tree and resolve every element of `parents` without fetching catalog JSON. The rows are few and the tree query is unchanged.
- For a federated index that grows large, partition by root catalog, one file per registered catalog. Pruning then happens at file level before any row is read, with the same schema in every file.
