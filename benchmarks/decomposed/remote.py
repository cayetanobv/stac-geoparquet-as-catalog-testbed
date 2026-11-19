"""Time the same questions on schema 8 and on schema 9 over HTTPS, with DuckDB 2.0.

Each query runs cold, in a fresh process, RUNS times. Requests and bytes come from EXPLAIN ANALYZE, as in
scripts/run_suite.py. The wall time is measured inside the process after the extensions load.

Layouts:
  8   schema 8, catalog and collection rows with `original` and `parents`
  9   schema 9 as proposed: no search columns, the place filter reads `extent`
  9s  schema 9 plus geometry, bbox, start_datetime and end_datetime
  9f  schema 9s with links inside the file written as `#id=<id>`

usage: uv run python remote.py INDEX RUNS
INDEX is berlin, madrid or registry."""
import json, re, statistics, subprocess, sys

INDEX, RUNS = sys.argv[1], int(sys.argv[2])
BASE = "https://storage.googleapis.com/carto-open-catalogs/_testbed"
P = {"berlin": dict(dir="berlin-geoportal", lon=13.405, lat=52.52, terms=["verkehr", "mobilit"], grp="verkehr"),
     "madrid": dict(dir="comunidad-madrid", lon=-3.7038, lat=40.4168, terms=["demograf", "poblacion"], grp="demografia"),
     "registry": dict(dir="registry", lon=-3.7038, lat=40.4168, terms=None, grp=None)}[INDEX]
URL = {k: f"{BASE}/{P['dir']}/collections-{s}.parquet" for k, s in
       {"8": "catalog-rows", "9": "decomposed", "9s": "decomposed-search", "9f": "decomposed-fragments"}.items()}
lon, lat = P["lon"], P["lat"]

def topic(cols="title, keywords"):
    if not P["terms"]: return "true"
    return (f"len(list_filter({P['terms']}, lambda x: strip_accents(lower(title)) LIKE '%' || x || '%' "
            f"OR len(list_filter(keywords, lambda k: strip_accents(lower(k)) LIKE '%' || x || '%')) > 0)) > 0")
GEOM = f"ST_Intersects(geometry, ST_Point({lon}, {lat}))"
# schema 9 without search columns: any box of the extent contains the point, written as a client would at first
EXTENT = f"len(list_filter(extent.spatial.bbox, lambda b: b[1] <= {lon} AND b[3] >= {lon} AND b[2] <= {lat} AND b[4] >= {lat})) > 0"
# the same, with a box that crosses the antimeridian read as two boxes
EXTENT_AM = (f"len(list_filter(extent.spatial.bbox, lambda b: b[2] <= {lat} AND b[4] >= {lat} AND "
             f"(CASE WHEN b[1] <= b[3] THEN b[1] <= {lon} AND b[3] >= {lon} ELSE {lon} >= b[1] OR {lon} <= b[3] END))) > 0")
def src(k): return f"read_parquet('{URL[k]}')"

Q = [
    ("Q1 place and topic", {
        "8": f"SELECT count(*) FROM {src('8')} WHERE type = 'Collection' AND {GEOM} AND {topic()}",
        "9s": f"SELECT count(*) FROM {src('9s')} WHERE type = 'Collection' AND {GEOM} AND {topic()}",
        "9": f"SELECT count(*) FROM {src('9')} WHERE type = 'Collection' AND {EXTENT} AND {topic()}",
        "9 antimeridian": f"SELECT count(*) FROM {src('9')} WHERE type = 'Collection' AND {EXTENT_AM} AND {topic()}"}),
    ("Q2 list of id and title", {
        "8": f"SELECT id, title FROM {src('8')} WHERE type = 'Collection'",
        "9": f"SELECT id, title FROM {src('9')} WHERE type = 'Collection'"}),
    ("Q3 one full document", {
        "8": f"SELECT original FROM {src('8')} WHERE type = 'Collection' AND id = (SELECT id FROM {src('8')} WHERE type = 'Collection' ORDER BY id LIMIT 1 OFFSET 100)",
        "9": f"SELECT * FROM {src('9')} WHERE type = 'Collection' AND id = (SELECT id FROM {src('9')} WHERE type = 'Collection' ORDER BY id LIMIT 1 OFFSET 100)"}),
    ("Q4 a core nested field: first provider name", {
        "8": f"SELECT count(DISTINCT json_extract_string(original, '$.providers[0].name')) FROM {src('8')}",
        "9": f"SELECT count(DISTINCT providers[1].name) FROM {src('9')}"}),
    ("Q5 an extension field: total table:row_count", {
        "8": f"SELECT sum(json_extract(original, '$.\"table:row_count\"')::BIGINT) FROM {src('8')}",
        "9": f"SELECT sum(json_extract(extra_fields, '$.\"table:row_count\"')::BIGINT) FROM {src('9')}"}),
]
if P["grp"]:
    g = P["grp"]
    Q.append(("Q6 collections anywhere under one group", {
        "8": f"SELECT count(*) FROM {src('8')} WHERE type = 'Collection' AND list_contains(list_transform(parents, lambda p: p.id), '{g}')",
        "9f": (f"WITH RECURSIVE t AS MATERIALIZED (SELECT id, type, list_transform(list_filter(links, lambda l: l.rel = 'parent'), lambda l: l.href) AS up FROM {src('9f')}), "
               f"sub(id) AS (SELECT '{g}' UNION SELECT t.id FROM t JOIN sub ON list_contains(t.up, '#id=' || sub.id)) "
               f"SELECT count(*) FROM t JOIN sub USING (id) WHERE t.type = 'Collection'")}))

PRE = "LOAD spatial; LOAD httpfs;"
TIMED = ("import duckdb, json, sys, time; con = duckdb.connect(); con.execute(sys.argv[1]); con.execute('SET enable_progress_bar = false'); "
         "t = time.perf_counter(); rows = con.execute(sys.argv[2]).fetchall(); t = time.perf_counter() - t; "
         "print(json.dumps({'t': t, 'rows': [[str(v)[:40] for v in r] for r in rows]}))")
def cold(sql):
    out = subprocess.run(["duckdb", "-no-agent", "-c", f"{PRE} EXPLAIN ANALYZE {sql};"], capture_output=True, text=True).stdout + "\n"
    b = re.findall(r"in:\s*([\d.]+\s*\w+)", out); g = re.findall(r"#GET:\s*(\d+)", out)
    r = subprocess.run([sys.executable, "-I", "-c", TIMED, PRE, sql], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-600:])
    res = json.loads(r.stdout.splitlines()[-1])
    reqs = sum(int(x) for x in g) + 1 if g else None   # GETs, plus the HEAD
    return res["t"], reqs, " + ".join(x.replace(" ", "") for x in b) or "?", res["rows"]

print(f"Index `{INDEX}`, point {lon}, {lat}, {RUNS} cold runs per query\n")
print("| Query | Layout | Result | Requests | Bytes read | Wall, each run | Wall median |")
print("|---|---|---|---|---|---|---|")
for label, by in Q:
    for k, sql in by.items():
        runs = [cold(sql) for _ in range(RUNS)]
        rows = runs[0][3]
        res = rows[0][0] if len(rows) == 1 and len(rows[0]) == 1 else f"{len(rows)} rows"
        print(f"| {label} | {k} | {res} | {runs[0][1]} | {runs[0][2]} | {', '.join(f'{r[0]:.2f}' for r in runs)} s | {statistics.median(r[0] for r in runs):.2f} s |", flush=True)
