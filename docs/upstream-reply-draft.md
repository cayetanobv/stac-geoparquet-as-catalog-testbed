@gadomski Two points. My comment from 31 August no longer describes the proposal. I also measured how DuckDB handles each column shape.

## The current proposal

The proposal now lives in portolan-sdi/portolan-spec#44. A `parents` column replaces the single `catalog` column. The column is a list of ancestor ids. The list runs from the root to the direct parent. The column is optional in one catalog. A federated index requires it, because ids are unique only within their own catalog. In generic STAC an ancestor can be a catalog or a collection. The name does not state the type, as @m-mohr suggested.

## Why the links do not replace the column

You are right about the overlap. The row already carries the `parent` and `root` links. They sit in a `links` column or inside the JSON text. Three gaps stay.

The links hold hrefs. The column holds ids. A reader needs a fetch of the parent document to get its id.

A relative parent href resolves against the collection document. It does not resolve against the index. A federated index has to resolve it per row.

The links name the direct parent and the root only. A filter on a catalog in the middle of the tree needs the full chain. The filter `list_contains(parents, 'transport')` matches at any depth.

## How searchable a list is in DuckDB

I built a Parquet file with 5 million rows and 100 000 rows per row group. It stores the same fact in three shapes. The shapes are a flat string column, a list of strings, and a list of link structs. The engine is DuckDB 1.5.6 on a local file. The times are from the second run.

| Filter | Shape | Pushed into the scan | Row groups in range | Wall | CPU |
|---|---|---|---|---|---|
| `parent_root = 'cat017'` | flat string | yes | 2 of 50 | 0.003 s | 0.011 s |
| `parent = 'sub03'` | flat string | yes | 50 of 50 | 0.002 s | 0.015 s |
| `list_contains(parents, 'cat017')` | list of strings | yes | 50 of 50 | 0.015 s | 0.18 s |
| `parents[1] = 'cat017'` | list of strings | yes | 50 of 50 | 0.015 s | 0.17 s |
| `list_filter(links, l -> l.rel = 'parent')[1].href = '../sub03/catalog.json'` | list of structs | no | 50 of 50 | 0.150 s | 1.9 s |
| `unnest(links)` then `l.rel = 'parent' AND l.href = '../sub03/catalog.json'` | list of structs | no | 50 of 50 | 0.104 s | 1.3 s |

The SQL is at the end of this comment.

What the numbers show.

DuckDB pushes `list_contains` on a list of strings into the Parquet scan. The Parquet writer keeps min and max statistics for list elements. But one statistic covers every element in the list. The list mixes levels of the tree. Thus the range spans the whole tree and the scan skips no row group. Row group 17 reported `cat017` to `sub19` for the `parents` column. The value `cat017` falls inside that range in all 50 row groups.

DuckDB does not push a filter on a list of structs into the scan. It reads every row and runs `list_filter` on each one. The CPU cost is about 100 times the flat column.

The flat column stays fast when the scan skips no row group. The filter on `parent` touched all 50 row groups and cost 0.015 s of CPU. So the list shape itself costs the time, not the lost statistics.

A real collection index holds hundreds to tens of thousands of rows. That is one or a few row groups. None of these times matters at that size. The gaps above and the query ergonomics decide, not the speed.

A flat `parent` column with the direct parent gives the cheap filter for the common case. It can sit beside the `parents` list. That compromise works for me.

<details>
<summary>SQL for the test</summary>

```sql
CREATE TABLE c AS
SELECT
  'cat' || lpad((i // 100000)::VARCHAR, 3, '0') AS parent_root,
  'sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0') AS parent,
  'col-' || i AS id,
  ['cat' || lpad((i // 100000)::VARCHAR, 3, '0'),
   'sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0')] AS parents,
  [ {'href': '../../catalog.json', 'rel': 'root', 'type': 'application/json', 'title': NULL},
    {'href': '../sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0') || '/catalog.json',
     'rel': 'parent', 'type': 'application/json', 'title': NULL},
    {'href': './collection.json', 'rel': 'self', 'type': 'application/json', 'title': NULL} ] AS links
FROM range(5000000) t(i);
COPY c TO 'big.parquet' (FORMAT PARQUET, ROW_GROUP_SIZE 100000);

.timer on
SELECT count(*) FROM 'big.parquet' WHERE parent_root = 'cat017';
SELECT count(*) FROM 'big.parquet' WHERE parent = 'sub03';
SELECT count(*) FROM 'big.parquet' WHERE list_contains(parents, 'cat017');
SELECT count(*) FROM 'big.parquet' WHERE parents[1] = 'cat017';
SELECT count(*) FROM 'big.parquet'
  WHERE list_filter(links, l -> l.rel = 'parent')[1].href = '../sub03/catalog.json';
SELECT count(*) FROM (SELECT unnest(links) AS l FROM 'big.parquet')
  WHERE l.rel = 'parent' AND l.href = '../sub03/catalog.json';

SELECT path_in_schema, stats_min, stats_max FROM parquet_metadata('big.parquet')
  WHERE row_group_id = 17 AND path_in_schema IN ('parent_root', 'parent', 'parents, list, element');
```

</details>
