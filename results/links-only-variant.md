# A file with STAC links instead of `parents`

The upstream comment on 2026-10-21 noted that `parents` repeats what the `parent` and `root` links already carry, and asked how searchable those links are inside a list. This experiment builds the Comunidad de Madrid index without `parents` and with a `links` column, a list of link structs as in the stac-geoparquet items table, and asks both questions against both files.

Files: `indexes/comunidad-madrid-datos-abiertos/collections.parquet` and `collections-links.parquet`. Scripts: `benchmarks/links-only/`.

Every `parent` link in this catalog is the same string, `../catalog.json`. A query has to resolve it against the row's own `href` before it can compare anything.

## Direct parent: collections under the shard `demografia/e-i`

Both files give 18. Over HTTPS, cold process, 3 runs:

| File | Filter | Requests | Bytes read | Time |
|---|---|---|---|---|
| `parents` | `parents[-1] = 'demografia/e-i'` | 3 | 17 KB | 0.45 to 0.48 s |
| links only | pick `rel = 'parent'`, resolve `../catalog.json` against `href`, compare the URL | 4 | 59 KB | 0.56 to 0.62 s |

## Theme: collections anywhere under `demografia`

The answer is 146.

| File | How | Requests | Time |
|---|---|---|---|
| `parents` | `list_contains(parents, 'demografia')` | 3 | 0.16 to 0.21 s |
| links only, path shortcut | resolved parent URL `LIKE '%/main/demografia/%'` | 4 | 0.16 to 0.17 s |
| links only, done properly, 16 threads | read the index, fetch 177 catalog documents upward in 2 rounds, walk each chain | 181 | 3.3 s |
| links only, done properly, sequential | same | 181 | 73 s |

The path shortcut is as fast as `parents`, but it is a URL naming convention, not a links query. The honest links-only client has to fetch every parent catalog, then their parents, up to the root, because the links in the file name locations and not ids, and name only one level up.

## Local CPU, same queries, 1,964 rows

| Query | `parents` | links only |
|---|---|---|
| Direct parent | 1 ms | 4 ms |
| Theme | 1 ms | 3 ms, path shortcut |
