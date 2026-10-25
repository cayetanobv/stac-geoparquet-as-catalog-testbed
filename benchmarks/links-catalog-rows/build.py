"""Add one row per catalog to the links-only variant, so that every parent link resolves inside the file.
usage: uv run python build.py MIRROR_DIR PUBLIC_ROOT_CATALOG_URL LINKS_PARQUET
Writes collections-links-catalogs.parquet in the cwd: the rows of LINKS_PARQUET with type 'Collection',
plus every catalog.json reachable from the mirror's root with type 'Catalog', its public href and its links."""
import json, os, sys, urllib.parse, duckdb, pyarrow as pa
MIRROR, PUBLIC, LINKS = sys.argv[1], sys.argv[2], sys.argv[3]
base = PUBLIC.rsplit("/", 1)[0] + "/"
rows, frontier = [], [PUBLIC]
while frontier:                                   # breadth-first over the local files, by public URL
    nxt = []
    for url in frontier:
        d = json.load(open(os.path.join(MIRROR, urllib.parse.unquote(url[len(base):])), encoding="utf-8"))
        if d.get("type") != "Catalog": continue
        rows.append({"type": "Catalog", "id": d["id"], "href": url,
                     "links": [{k: l.get(k) for k in ("href", "rel", "type", "title")} for l in d["links"]]})
        nxt += [urllib.parse.urljoin(url, l["href"]) for l in d["links"] if l["rel"] == "child"]
    frontier = nxt
cats = pa.Table.from_pylist(rows)
con = duckdb.connect(); con.execute("LOAD spatial")
geo = con.execute(f"SELECT decode(value) FROM parquet_kv_metadata('{LINKS}') WHERE decode(key) = 'geo'").fetchone()[0]
con.execute(f"""COPY (SELECT 'Collection' AS type, * REPLACE (ST_AsWKB(geometry)::BLOB AS geometry) FROM read_parquet('{LINKS}')
                      UNION ALL BY NAME SELECT * FROM cats)
                TO 'collections-links-catalogs.parquet' (FORMAT PARQUET, COMPRESSION ZSTD, KV_METADATA {{geo: $geo}})""".replace("$geo", "'" + geo.replace("'", "''") + "'"))
print(con.execute("SELECT type, count(*) FROM 'collections-links-catalogs.parquet' GROUP BY 1 ORDER BY 1").fetchall())
