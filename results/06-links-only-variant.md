# A file with STAC links instead of `parents`

The upstream comment on 2026-10-21 noted that `parents` repeats what the `parent` and `root` links already carry, and asked how searchable those links are inside a list. This experiment builds the Comunidad de Madrid index without `parents` and with a `links` column, a list of link structs as in the stac-geoparquet items table, and asks both questions against both files. Measured on 2026-10-23 with DuckDB 2.0.0 and Python 3.14.9.

Files: `indexes/comunidad-madrid-datos-abiertos/collections.parquet` and `collections-links.parquet`. Scripts: `benchmarks/links-only/`.

Every `parent` link in this catalog is the same string, `../catalog.json`. A query has to resolve it against the row's own `href` before it can compare anything.

## Direct parent: collections under the shard `demografia/e-i`

Both files give 18. Over HTTPS, cold process, 3 runs. DuckDB 2.0 reads either file whole, 1.4 MB in one request, so the two shapes cost the same on the network.

| File | Filter | Requests | Bytes read | Time |
|---|---|---|---|---|
| `parents` | `parents[-1] = 'demografia/e-i'` | 2 | 1.4 MB | 0.76 to 1.00 s |
| links only | pick `rel = 'parent'`, resolve `../catalog.json` against `href`, compare the URL | 2 | 1.4 MB | 0.80 to 0.94 s |

## Theme: collections anywhere under `demografia`

The answer is 146.

| File | How | Requests | Time |
|---|---|---|---|
| `parents` | `list_contains(parents, 'demografia')` | 2 | 0.79 to 0.92 s |
| links only, path shortcut | resolved parent URL `LIKE '%/main/demografia/%'` | 2 | 0.87 to 1.26 s |
| links only, done properly, 16 threads | read the index, fetch 177 catalog documents upward in 2 rounds, walk each chain | 178 | 3.2 s |
| links only, done properly, sequential | same | 178 | 30 s |

The path shortcut is a URL naming convention, not a links query. A links-only client that reads only this file has to fetch every parent catalog, then their parents, up to the root, because the links in the file name locations and not ids, and name only one level up.

## What this does not test

A links file that also held one row per catalog, as [page 05](05-tree-designs.md) suggests, could resolve every parent link inside the file, with a recursive query and no extra fetches. [Page 08](08-follow-up-checks.md) builds that variant: it answers the theme question from the file alone, with a client that climbs the tree in memory, in about the time of the `parents` query. So the case for `parents` over it is not speed. It is that one column of ids answers the subtree question without catalog rows, without resolving relative URLs, and with the ids a federated index needs for its key.

## Local CPU, same queries, 1,964 rows

| Query | `parents` | links only |
|---|---|---|
| Direct parent | 2 ms | 8 ms |
| Theme | 2 ms | 6 ms, path shortcut |

Both are below the noise of a single HTTP request. The cost of the links shape is in the extra fetches, not in the list.
