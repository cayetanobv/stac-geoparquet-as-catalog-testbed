"""Links-only client with catalog rows in the file: answer 'collections anywhere under THEME_ID' from the
file alone. One read of id, type, href and the parent link, then every parent URL is resolved in memory.
usage: uv run python theme.py FILE_PATH_OR_URL THEME_ID [RUNS]"""
import sys, time, statistics, urllib.parse, duckdb
SRC, THEME = sys.argv[1], sys.argv[2]
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
def once():
    t0 = time.perf_counter()
    con = duckdb.connect(); con.execute("LOAD httpfs")
    rows = con.execute(f"""SELECT type, id, href, list_filter(links, lambda l: l.rel = 'parent')[1].href
                           FROM read_parquet('{SRC}')""").fetchall()
    t_read = time.perf_counter() - t0
    cat_id = {h: i for t, i, h, p in rows if t == "Catalog"}
    parent = {h: urllib.parse.urljoin(h, p) if p else None for t, i, h, p in rows}
    def ancestors(href):
        out, u = [], parent[href]
        while u in cat_id: out.append(cat_id[u]); u = parent[u]
        return out
    hits = sum(THEME in ancestors(h) for t, i, h, p in rows if t == "Collection")
    return t_read, time.perf_counter() - t0, hits, len(rows)
res = [once() for _ in range(RUNS)]               # each run opens a new connection, so a remote file is read cold
print(f"rows={res[0][3]} hits={res[0][2]} read={', '.join(f'{r[0]:.3f}' for r in res)} s "
      f"total={', '.join(f'{r[1]:.3f}' for r in res)} s median={statistics.median(r[1] for r in res):.3f} s")
