"""Time what a client does today: walk catalog JSONs over HTTPS, any depth, to find collections
under one group whose bbox contains a point.  usage: walk_timing.py ROOT_URL LON LAT GROUP_ID [fresh]
Each thread keeps one connection alive per host. Pass `fresh` to open a new connection for every
document instead, as urllib does and as the measurements before 2026-10-25 did."""
import http.client, json, sys, threading, time, urllib.request, urllib.parse, concurrent.futures as cf
ROOT, QX, QY, GROUP = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
FRESH = len(sys.argv) > 5 and sys.argv[5] == "fresh"
UA = "Mozilla/5.0 (compatible; stac-geoparquet-as-catalog-testbed/0.1)"
local = threading.local()
def get_keepalive(url):
    """GET over a per-thread, per-host connection, following redirects."""
    for _ in range(5):
        p = urllib.parse.urlsplit(url)
        conns = local.__dict__.setdefault("conns", {})
        if p.netloc not in conns:
            cls = http.client.HTTPSConnection if p.scheme == "https" else http.client.HTTPConnection
            conns[p.netloc] = cls(p.netloc, timeout=60)
        c = conns[p.netloc]
        try:
            c.request("GET", p.path + ("?" + p.query if p.query else ""), headers={"User-Agent": UA})
            r = c.getresponse(); body = r.read()
        except Exception:
            c.close(); del conns[p.netloc]; raise
        if r.status in (301, 302, 303, 307, 308):
            url = urllib.parse.urljoin(url, r.getheader("Location")); continue
        if r.status != 200: raise OSError(f"HTTP {r.status} for {url}")
        return json.loads(body)
    raise OSError(f"too many redirects for {url}")
def get_fresh(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r: return json.load(r)
def fetch(url):
    for a in range(5):
        try: return (get_fresh if FRESH else get_keepalive)(url)
        except Exception:
            if a == 4: raise
            time.sleep(0.5 * 2 ** a)
def contains(b, x, y):
    # a bbox with west > east crosses the antimeridian, as in scripts/build_index.sql
    in_x = b[0] <= x <= b[2] if b[0] <= b[2] else (x >= b[0] or x <= b[2])
    return in_x and b[1] <= y <= b[3]
def run(workers, group):
    t0 =time.perf_counter(); reqs = 0; hits = 0
    frontier = [ROOT]
    with cf.ThreadPoolExecutor(workers) as ex:
        while frontier:
            docs = list(zip(frontier, ex.map(fetch, frontier))); reqs += len(frontier); frontier = []
            for url, d in docs:
                if d.get("type") == "Collection":
                    hits += contains(d["extent"]["spatial"]["bbox"][0], QX, QY)
                    continue
                for l in d["links"]:
                    if l["rel"] != "child": continue
                    # when a group is requested, prune at the root to that group's subtree only
                    if group and url == ROOT and l["href"].strip("./").split("/")[0] != group \
                            and l.get("portolan_registry:id") != group: continue
                    frontier.append(urllib.parse.urljoin(url, l["href"]))
    return time.perf_counter() - t0, reqs, hits
mode = "fresh connections" if FRESH else "keep-alive"
for label, w, g in [(f"one group ({GROUP}), sequential", 1, GROUP), (f"one group ({GROUP}), 16 threads", 16, GROUP),
                    ("whole tree, 16 threads", 16, None), ("whole tree, sequential", 1, None)]:
    t, n, h = run(w, g); print(f"{label:36s} {mode} requests={n:5d} hits={h:5d} time={t:7.2f} s", flush=True)
