"""Build the decomposed variant (schema 9 in docs/schema.md) from a schema 8 file.

Schema 9 is the layout proposed in stac-geoparquet-spec#17 on 2026-11-18: one column for each field that STAC 1.1
defines for a Catalog or a Collection, and one `extra_fields` column, JSON text, for every other top-level field.
It has no `original`, no `parents` and no `href`.

The input is the schema 8 file of the same index, so the rows, their order and the derived search columns are the same.
The nested columns take the Arrow type that pyarrow infers from the documents: a struct holds every key that occurs,
the way stac-geoparquet infers the item schema. A key that one document does not have is null in that row.

Three files are written next to OUT_PREFIX:
  OUT_PREFIX-decomposed.parquet            the proposal as written
  OUT_PREFIX-decomposed-search.parquet     the same, plus geometry, bbox, start_datetime and end_datetime from schema 8
  OUT_PREFIX-decomposed-fragments.parquet  the search file, with each link to a row of the same file written as
                                           `#id=<id>`; only when every id in the file is unique

usage: uv run python build.py SCHEMA8_FILE OUT_PREFIX"""
import json, sys, urllib.parse
import duckdb, pyarrow as pa, pyarrow.parquet as pq

SRC, OUT = sys.argv[1], sys.argv[2]
# the fields STAC 1.1 defines for a Catalog or a Collection, each one a column of its own
CORE = ["type", "stac_version", "stac_extensions", "id", "title", "description", "keywords", "license",
        "providers", "extent", "summaries", "item_assets", "assets", "links"]
SEARCH = ["geometry", "bbox", "start_datetime", "end_datetime"]
IN_FILE_RELS = {"child", "parent", "root", "collection"}

src = pq.read_table(SRC)
geo = pq.read_metadata(SRC).metadata[b"geo"].decode()
docs = [json.loads(s) for s in src.column("original").to_pylist()]
hrefs = src.column("href").to_pylist()

def columns(docs):
    cols = {}
    for k in CORE:
        vals = [d.get(k) for d in docs]
        if k == "summaries":                       # values of any type: JSON text
            cols[k] = pa.array([None if v is None else json.dumps(v, ensure_ascii=False) for v in vals], pa.string())
        elif k == "extent":                        # keep every box and every interval, intervals as timestamps
            t = pa.struct([("spatial", pa.struct([("bbox", pa.list_(pa.list_(pa.float64())))])),
                           ("temporal", pa.struct([("interval", pa.list_(pa.list_(pa.timestamp("us", "UTC"))))]))])
            from datetime import datetime
            def p(s): return None if s is None else datetime.fromisoformat(s.replace("Z", "+00:00"))
            cols[k] = pa.array([None if v is None else {"spatial": {"bbox": v["spatial"]["bbox"]},
                                "temporal": {"interval": [[p(x) for x in i] for i in v["temporal"]["interval"]]}}
                                for v in vals], t)
        elif k in ("assets", "item_assets"):       # a map of asset key to a struct inferred from every asset
            inner = pa.array([a for v in vals if v for a in v.values()]).type
            cols[k] = pa.array([None if v is None else list(v.items()) for v in vals], pa.map_(pa.string(), inner))
        else:
            cols[k] = pa.array(vals)
    extra = []
    for d in docs:
        rest = {k: v for k, v in d.items() if k not in CORE}
        extra.append(json.dumps(rest, ensure_ascii=False) if rest else None)
    cols["extra_fields"] = pa.array(extra, pa.string())
    return cols

def write(cols, names, path, with_geo):
    t = pa.table({n: cols[n] for n in names})
    con = duckdb.connect(); con.register("t", t)
    kv = "KV_METADATA {geo: '" + geo.replace("'", "''") + "'}, " if with_geo else ""
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD, {kv}ROW_GROUP_SIZE 1000000)")
    print(f"{path}: {pq.read_metadata(path).num_rows} rows, types:")
    for f in pq.read_schema(path):
        print(f"  {f.name}: {str(f.type)[:160]}")

cols = columns(docs)
for c in SEARCH:
    cols[c] = src.column(c)
# heavy nested columns last, as schema 8 does with links
base = ["type", "stac_version", "stac_extensions", "id", "title", "description", "keywords", "license", "providers",
        "extent", "summaries", "item_assets", "assets", "extra_fields", "links"]
write(cols, base, f"{OUT}-decomposed.parquet", False)
search = base[:4] + SEARCH + base[4:]
write(cols, search, f"{OUT}-decomposed-search.parquet", True)

ids = [d["id"] for d in docs]
dups = len(ids) - len(set(ids))
if dups:
    print(f"fragments: not written, {dups} rows repeat an id that another row has")
    sys.exit()
row_of = {h: i for h, i in zip(hrefs, ids)}
rewritten, kept = 0, 0
frag_docs = []
for d, h in zip(docs, hrefs):
    links = []
    for l in d.get("links", []):
        target = row_of.get(urllib.parse.urljoin(h, l["href"])) if l.get("rel") in IN_FILE_RELS else None
        if target is not None:
            l = {**l, "href": f"#id={target}"}; rewritten += 1
        elif l.get("rel") in IN_FILE_RELS:
            kept += 1
        links.append(l)
    frag_docs.append({**d, "links": links})
cols["links"] = pa.array([d["links"] for d in frag_docs])
print(f"fragments: {rewritten} links point into the file, {kept} child, parent, root or collection links point outside it")
write(cols, search, f"{OUT}-decomposed-fragments.parquet", True)
