CREATE TABLE c AS
SELECT
  'cat' || lpad((i // 100000)::VARCHAR, 3, '0')                                  AS parent_root,
  'sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0')                              AS parent,
  'col-' || i                                                                      AS id,
  ['cat' || lpad((i // 100000)::VARCHAR, 3, '0'), 'sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0')] AS parents,
  [ {'href': '../../catalog.json', 'rel': 'root', 'type': 'application/json', 'title': NULL},
    {'href': '../' || 'sub' || lpad(((i // 5000) % 20)::VARCHAR, 2, '0') || '/catalog.json', 'rel': 'parent', 'type': 'application/json', 'title': NULL},
    {'href': './collection.json',  'rel': 'self', 'type': 'application/json', 'title': NULL} ] AS links
FROM range(5000000) t(i);
COPY c TO 'big.parquet' (FORMAT PARQUET, ROW_GROUP_SIZE 100000);
