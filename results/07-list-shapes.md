# How searchable a list is in DuckDB

Synthetic file with 5 million rows and 100,000 rows per row group, 50 row groups. The same parent fact is stored as a flat string column, a list of strings, and a list of link structs. Measured on 2026-10-23 with DuckDB 2.0.0, local file, best of two runs. Scripts: `benchmarks/list-shapes/`.

| Filter | Shape | Pushed into the scan | Row groups in range | Wall | CPU |
|---|---|---|---|---|---|
| `parent_root = 'cat017'` | flat string | yes | 2 of 50 | 0.007 s | 0.010 s |
| `parent = 'sub03'` | flat string | yes | 50 of 50 | 0.009 s | 0.027 s |
| `list_contains(parents, 'cat017')` | list of strings | yes | 50 of 50 | 0.016 s | 0.071 s |
| `parents[1] = 'cat017'` | list of strings | yes | 50 of 50 | 0.008 s | 0.017 s |
| `list_contains(parents, 'sub03')` | list of strings | yes | 50 of 50 | 0.050 s | 0.47 s |
| `list_filter(links, lambda l: l.rel = 'parent')[1].href = '../sub03/catalog.json'` | list of structs | no | 50 of 50 | 0.29 s | 3.2 s |
| `unnest(links)` then `l.rel = 'parent' AND l.href = '../sub03/catalog.json'` | list of structs | no | 50 of 50 | 0.32 s | 3.6 s |

What the numbers show:

- DuckDB pushes `list_contains` and a positional `parents[1]` on a list of strings into the Parquet scan. The positional form costs about the same as a flat column.
- The Parquet writer keeps min and max statistics for list elements, but one statistic covers every element in the list. A list that mixes levels of the tree spans the whole tree, so no row group is skipped. Row group 17 reported `cat017` to `sub19` for `parents`, and `cat017` falls inside that range in all 50 row groups.
- DuckDB does not push a filter on a list of structs into the scan. It reads every row and runs `list_filter` on each one, at about 120 times the CPU of a flat column that holds the same fact, `parent = 'sub03'`, and 300 times the CPU of `parent_root = 'cat017'`, which skips 48 row groups. Under DuckDB 1.5.6 the ratio was about 100.
- DuckDB writes a bloom filter on the elements of a list column. That is a second mechanism, besides statistics, that keeps an equality `list_contains` cheap.
- A real collection index holds hundreds to tens of thousands of rows, one or a few row groups. None of these times is visible over HTTP at that size.
