# Alternatives for the tree column

Which column shape answers "every collection under this node" fastest in one flat file, for static catalogs that are published and updated independently. Synthetic tree with 5 million collections under root, 50 catalogs, 20 sub-catalogs each, 5 shards each, plus 6,050 catalog rows in the same file. Written twice, once sorted in tree order and once in random order, 100,000 rows per row group. DuckDB 1.5.6, local. Scripts: `benchmarks/tree-designs/`.

The question is the subtree of one level-1 catalog, 100,000 rows.

| Design | Sorted by tree | Random order | Generic STAC safe |
|---|---|---|---|
| `parents` list, `list_contains` | 44 ms, 0.55 s CPU | 28 ms, 0.30 s CPU | yes |
| Materialized `path` string, prefix `LIKE` | 5 ms, 7 ms CPU | 33 ms, 0.35 s CPU | needs an escaping rule |
| Flat per-level columns `p1`, `p2`, `p3` | 2 ms, 6 ms CPU | 4 ms, 42 ms CPU | no, fixed depth |
| `parent` only, recursive CTE over catalog rows | 75 ms, 0.60 s CPU | 82 ms, 0.53 s CPU | yes, ids must be globally unique |

File size: 90 MB sorted in tree order, 184 MB in random order.

Rejected without measurement:

- Nested-set intervals. Fastest subtree query, but every insertion renumbers the whole tree. Catalogs published independently cannot do that.
- A separate closure table. Two files and a join.

## Assessment

The materialized path is the only serious rival to `parents`. It is ten times cheaper in CPU when the file is sorted in tree order, because prefix matches prune row groups, and the sort halves the file. But it needs a separator that cannot appear in an id, and STAC does not restrict ids. In the Comunidad de Madrid catalog the shard id `demografia/e-i` contains a slash. A slash-joined path has a false-positive case for a sibling whose id starts with `demografia/`. A spec would have to define an escaping rule for every writer and reader, for a gain that appears above roughly a million rows.

Every real catalog in the registry fits in one row group. There the whole file is three to five HTTP round trips and the shape of the tree column is invisible. The Comunidad de Madrid remote queries show it: 0.16 s for the subtree count, the same as any other filter.

Two changes that do help, independent of the tree column:

- Catalog rows in the same file, with a `type` column. A client can then render the tree and resolve every element of `parents` without fetching catalog JSON. The rows are few and the tree query is unchanged.
- For a federated index that grows large, partition by root catalog, one file per registered catalog. Pruning then happens at file level before any row is read, with the same schema in every file.
