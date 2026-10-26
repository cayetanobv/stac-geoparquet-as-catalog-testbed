"""Run the query suite against a collection index and print a Markdown table.
Each query runs COLD (a fresh DuckDB process per run, so nothing is cached) and WARM (one process,
after a first run). HTTP request counts and bytes come from EXPLAIN ANALYZE on a remote file.
Cold time is reported twice: the EXPLAIN ANALYZE total, which leaves out reads made while planning, and the
wall clock of the plain query in a fresh process, measured inside that process after the extensions load,
so it includes planning and leaves out process start.
usage: run_suite.py INDEX_URL_OR_PATH --lon X --lat Y --grp GROUP --kw KEYWORD --cat ROOT_ID --id COLLECTION_ID [--runs 3]"""
import argparse, json, re, statistics, subprocess, sys, textwrap

ap = argparse.ArgumentParser()
ap.add_argument("index"); ap.add_argument("--lon", type=float, required=True); ap.add_argument("--lat", type=float, required=True)
ap.add_argument("--grp", required=True); ap.add_argument("--kw", required=True); ap.add_argument("--cat", required=True)
ap.add_argument("--id", required=True); ap.add_argument("--runs", type=int, default=3); ap.add_argument("--only", default=None, help="comma-separated label prefixes, for example G or S1,T3")
ap.add_argument("--region-url", help="GeoParquet file with real polygons, for the G queries")
ap.add_argument("--region-geom", default="geometry", help="its geometry column")
ap.add_argument("--region-name", default="name", help="its name column")
ap.add_argument("--region-crs", default=None, help="its CRS when not OGC:CRS84, for example EPSG:25830; transformed to EPSG:4326")
ap.add_argument("--region-where", default=None, help="SQL predicate that selects the one feature used as the region; default: the feature containing the point")
a = ap.parse_args()
dx, dy = 0.05, 0.03  # a box of about 5 x 3 km around the point

QUERIES = [
    ("S1 point in extent, whole file",
     "SELECT count(*) FROM t WHERE ST_Intersects(geometry, ST_Point({lon}, {lat}))"),
    ("S2 point in extent, under one group",
     "SELECT count(*) FROM t WHERE list_contains(parents, '{grp}') AND ST_Intersects(geometry, ST_Point({lon}, {lat}))"),
    ("S3 box intersects extent, bbox struct only",
     "SELECT count(*) FROM t WHERE bbox.xmin <= {lon}+{dx} AND bbox.xmax >= {lon}-{dx} AND bbox.ymin <= {lat}+{dy} AND bbox.ymax >= {lat}-{dy}"),
    ("S4 local datasets: extent narrower than 0.3 degrees containing the point",
     "SELECT count(*) FROM t WHERE bbox.xmax - bbox.xmin < 0.3 AND ST_Intersects(geometry, ST_Point({lon}, {lat}))"),
    ("S5 nearest 10 collections to the point by extent centre, with title",
     "SELECT id, title FROM t ORDER BY ST_Distance(ST_Centroid(geometry), ST_Point({lon}, {lat})) LIMIT 10"),
    ("T1 everything under one group, id and title",
     "SELECT id, title FROM t WHERE list_contains(parents, '{grp}') ORDER BY id"),
    ("T2 collections per direct parent",
     "SELECT parents, count(*) FROM t GROUP BY 1 ORDER BY 2 DESC"),
    ("T3 one catalog by root id, one group",
     "SELECT count(*) FROM t WHERE parents[1] = '{cat}' AND list_contains(parents, '{grp}')"),
    ("A1 keyword equality",
     "SELECT count(*) FROM t WHERE list_contains(keywords, '{kw}')"),
    ("A2 title substring, case-insensitive",
     "SELECT count(*) FROM t WHERE title ILIKE '%{kw}%'"),
    ("A3 description substring",
     "SELECT count(*) FROM t WHERE description ILIKE '%{kw}%'"),
    ("A4 license equality",
     "SELECT license, count(*) FROM t GROUP BY 1 ORDER BY 2 DESC LIMIT 3"),
    ("A5 temporal: end open or after 2024",
     "SELECT count(*) FROM t WHERE end_datetime IS NULL OR end_datetime >= TIMESTAMPTZ '2024-01-01'"),
    ("D1 one full document by catalog and id",
     "SELECT len(original) FROM t WHERE parents[1] = '{cat}' AND id = '{id}'"),
    ("D2 field inside the JSON document for a group: providers",
     "SELECT id, json_extract_string(original, '$.providers[0].name') FROM t WHERE list_contains(parents, '{grp}') LIMIT 20"),
    ("C1 combined: group, point, keyword, title returned",
     "SELECT id, title, href FROM t WHERE list_contains(parents, '{grp}') AND ST_Intersects(geometry, ST_Point({lon}, {lat})) AND list_contains(keywords, '{kw}')"),
]
# G: real-polygon queries. `region` is one feature from --region-url, `features` is the whole file. Both are remote GeoParquet.
GEO = [
    ("G1 extents that intersect a box of about 5 x 3 km",
     "SELECT count(*) FROM t WHERE ST_Intersects(geometry, ST_MakeEnvelope({lon}-{dx}, {lat}-{dy}, {lon}+{dx}, {lat}+{dy}))"),
    ("G2 extents that intersect the region polygon",
     "SELECT count(*) FROM t, region WHERE ST_Intersects(t.geometry, region.g)"),
    ("G3 extents that lie inside the region polygon",
     "SELECT count(*) FROM t, region WHERE ST_Within(t.geometry, region.g)"),
    ("G4 extents that contain the whole region polygon",
     "SELECT count(*) FROM t, region WHERE ST_Contains(t.geometry, region.g)"),
    ("G5 ten most local datasets for the region: share of the extent that falls inside it",
     "SELECT id, round(ST_Area(ST_Intersection(t.geometry, region.g)) / ST_Area(t.geometry), 3) AS share FROM t, region WHERE ST_Intersects(t.geometry, region.g) ORDER BY share DESC, id LIMIT 10"),
    ("G6 extents within 0.05 degrees of the point",
     "SELECT count(*) FROM t WHERE ST_DWithin(geometry, ST_Point({lon}, {lat}), 0.05)"),
    ("G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees",
     "SELECT f.n, count(*) FROM t JOIN features f ON ST_Intersects(t.geometry, f.g) WHERE t.bbox.xmax - t.bbox.xmin < 0.3 GROUP BY f.n ORDER BY 2 DESC LIMIT 5"),
]
if a.region_url:
    QUERIES += GEO
if a.only: QUERIES = [q for q in QUERIES if any(q[0].startswith(o) for o in a.only.split(","))]

def sql_for(q):
    body = q.format(lon=a.lon, lat=a.lat, dx=dx, dy=dy, grp=a.grp, kw=a.kw, cat=a.cat, id=a.id).replace(" FROM t", f" FROM read_parquet('{a.index}') t")
    if "region" not in body and "features" not in body:
        return body
    g = a.region_geom if not a.region_crs else f"ST_Transform({a.region_geom}, '{a.region_crs}', 'EPSG:4326', always_xy := true)"
    where = a.region_where or f"ST_Intersects({g}, ST_Point({a.lon}, {a.lat}))"
    ctes = (f"WITH features AS (SELECT {g} AS g, {a.region_name} AS n FROM read_parquet('{a.region_url}')), "
            f"region AS (SELECT {g} AS g FROM read_parquet('{a.region_url}') WHERE {where} LIMIT 1) ")
    return ctes + body

PRE = "LOAD spatial; LOAD httpfs;"
# a fresh Python process per run: load the extensions, then time the query and fetch its rows
TIMED = ("import duckdb, json, sys, time; con = duckdb.connect(); con.execute(sys.argv[1]); con.execute('SET enable_progress_bar = false'); "
         "t = time.perf_counter(); rows = con.execute(sys.argv[2]).fetchall(); t = time.perf_counter() - t; "
         "print(json.dumps({'t': t, 'rows': [[str(v) for v in r] for r in rows]}))")
def run_cold(sql):
    out = subprocess.run(["duckdb", "-no-agent", "-c", f"{PRE} EXPLAIN ANALYZE {sql};"], capture_output=True, text=True).stdout + "\n"
    t = re.search(r"Total Time:\s*([\d.]+)s", out); b = re.search(r"in:\s*([\d.]+\s*\w+)", out); g = re.search(r"#GET:\s*(\d+)", out)
    res = json.loads(subprocess.run([sys.executable, "-I", "-c", TIMED, PRE, sql], capture_output=True, text=True, check=True).stdout.splitlines()[-1])
    w, lines = res["t"], res["rows"]
    body = sql[sql.rfind(" SELECT ") + 1:] if sql.startswith("WITH ") else sql   # the main query after the region CTEs
    is_count = body.lstrip().startswith("SELECT count(*) FROM")
    rows = lines[0][0] if is_count and len(lines) == 1 else str(len(lines))   # a count, or the number of result rows
    return float(t.group(1)) if t else None, (b.group(1).replace(" ", "") if b else "local"), (int(g.group(1)) + 1 if g else None), rows, w

def run_warm(sql, n):
    cmds = ["-c", f"{PRE}"] + sum([["-c", f"EXPLAIN ANALYZE {sql};"] for _ in range(n + 1)], [])
    out = subprocess.run(["duckdb", "-no-agent"] + cmds, capture_output=True, text=True).stdout
    return [float(x) for x in re.findall(r"Total Time:\s*([\d.]+)s", out)][1:]

print(f"Index: `{a.index}`  point {a.lon},{a.lat}  group `{a.grp}`  keyword `{a.kw}`  runs {a.runs}" + (f"  region from `{a.region_url}`" if a.region_url else "") + "\n")
print("| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |")
print("|---|---|---|---|---|---|---|---|")
for label, q in QUERIES:
    sql = sql_for(q)
    cold = [run_cold(sql) for _ in range(a.runs)]
    times = [c[0] for c in cold if c[0] is not None]
    if not times:
        print(f"| {label} | error | | | | | | |"); print(subprocess.run(["duckdb", "-no-agent", "-c", f"{PRE} {sql};"], capture_output=True, text=True).stderr[:300], file=sys.stderr); continue
    warm = run_warm(sql, a.runs)
    print(f"| {label} | {cold[0][3]} | {cold[0][2] or ''} | {cold[0][1]} | {', '.join(f'{t:.2f}' for t in times)} s | {statistics.median(times):.2f} s | {statistics.median(c[4] for c in cold):.2f} s | {statistics.median(warm):.2f} s |", flush=True)
