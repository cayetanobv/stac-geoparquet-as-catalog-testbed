"""Links-only client answering 'collections under theme demografia' honestly:
read the index, resolve each row's parent link, fetch every distinct parent catalog,
read ITS parent link, and keep rows whose grandparent (or parent) is the demografia catalog."""
import json, time, urllib.request, urllib.parse, concurrent.futures as cf, duckdb, sys
B = "https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main"
def fetch(url):
    for a in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: return json.load(r)
        except Exception:
            if a == 4: raise
            time.sleep(0.5 * 2 ** a)
for workers in (16, 1):
    t0 = time.perf_counter()
    con = duckdb.connect(); con.execute("LOAD httpfs")
    rows = con.execute(f"""SELECT id, href, list_filter(links, lambda l: l.rel = 'parent')[1].href AS p
                           FROM read_parquet('{B}/collections-links.parquet')""").fetchall()
    t_index = time.perf_counter() - t0
    parent_url = {cid: urllib.parse.urljoin(h, p) for cid, h, p in rows}
    distinct = sorted(set(parent_url.values()))
    docs = {}
    rounds = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        todo = distinct
        while todo:                                   # fetch parents, then their parents, until the root
            rounds += 1
            docs.update(zip(todo, ex.map(fetch, todo)))
            nxt = set()
            for u in todo:
                pl = next((l["href"] for l in docs[u]["links"] if l["rel"] == "parent"), None)
                if pl:
                    pu = urllib.parse.urljoin(u, pl)
                    if pu not in docs: nxt.add(pu)
            todo = sorted(nxt)
    def ancestors(url):
        out = []
        while url in docs:
            d = docs[url]; out.append(d["id"])
            pl = next((l["href"] for l in d["links"] if l["rel"] == "parent"), None)
            url = urllib.parse.urljoin(url, pl) if pl else None
        return out
    hits = sum("demografia" in ancestors(u) for u in parent_url.values())
    print(f"workers={workers:2d} index_read={t_index:5.2f}s catalog_fetches={len(docs)} rounds={rounds} hits={hits} total={time.perf_counter()-t0:6.2f}s", flush=True)
