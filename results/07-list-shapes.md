# How searchable a list is in DuckDB

Synthetic file with 5 million rows and 100,000 rows per row group, 50 row groups. The same parent fact is stored as a flat string column, a list of strings, and a list of link structs. DuckDB 1.5.6, local file, second run. Scripts: `benchmarks/list-shapes/`.

| Filter | Shape | Pushed into the scan | Row groups in range | Wall | CPU |
|---|---|---|---|---|---|
| `parent_root = 'cat017'` | flat string | yes | 2 of 50 | 0.003 s | 0.011 s |
| `parent = 'sub03'` | flat string | yes | 50 of 50 | 0.002 s | 0.015 s |
| `list_contains(parents, 'cat017')` | list of strings | yes | 50 of 50 | 0.015 s | 0.18 s |
| `parents[1] = 'cat017'` | list of strings | yes | 50 of 50 | 0.015 s | 0.17 s |
| `list_filter(links, l -> l.rel = 'parent')[1].href = '../sub03/catalog.json'` | list of structs | no | 50 of 50 | 0.150 s | 1.9 s |
| `unnest(links)` then `l.rel = 'parent' AND l.href = '../sub03/catalog.json'` | list of structs | no | 50 of 50 | 0.104 s | 1.3 s |

What the numbers show:

- DuckDB pushes `list_contains` on a list of strings into the Parquet scan. The Parquet writer keeps min and max statistics for list elements, but one statistic covers every element in the list. A list that mixes levels of the tree spans the whole tree, so no row group is skipped. Row group 17 reported `cat017` to `sub19` for `parents`, and `cat017` falls inside that range in all 50 row groups.
- DuckDB does not push a filter on a list of structs into the scan. It reads every row and runs `list_filter` on each one, at about 100 times the CPU of the flat column.
- The flat column stays fast when no row group is skipped. The filter on `parent` touched all 50 row groups and cost 0.015 s of CPU. The list shape itself costs the time, not the lost statistics.
- DuckDB writes a bloom filter on the elements of a list column. That is a second mechanism, besides statistics, that keeps an equality `list_contains` cheap.
- A real collection index holds hundreds to tens of thousands of rows, one or a few row groups. None of these times is visible over HTTP at that size.
