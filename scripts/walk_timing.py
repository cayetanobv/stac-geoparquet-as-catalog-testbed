"""Time what a client does today: walk catalog JSONs over HTTPS, any depth, to find collections
under one group whose bbox contains a point.  usage: walk_timing.py ROOT_URL LON LAT GROUP_ID"""
import json, sys, time, urllib.request, urllib.parse, concurrent.futures as cf
ROOT, QX, QY, GROUP = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
def fetch(url):
    for a in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: return json.load(r)
        except Exception:
            if a == 4: raise
            time.sleep(0.5 * 2 ** a)
def run(workers, group):
    t0 = time.perf_counter(); reqs = 0; hits = 0
    frontier = [ROOT]
    with cf.ThreadPoolExecutor(workers) as ex:
        while frontier:
            docs = list(zip(frontier, ex.map(fetch, frontier))); reqs += len(frontier); frontier = []
            for url, d in docs:
                if d.get("type") == "Collection":
                    b = d["extent"]["spatial"]["bbox"][0]
                    hits += b[0] <= QX <= b[2] and b[1] <= QY <= b[3]
                    continue
                for l in d["links"]:
                    if l["rel"] != "child": continue
                    # when a group is requested, prune at the root to that group's subtree only
                    if group and url == ROOT and l["href"].strip("./").split("/")[0] != group: continue
                    frontier.append(urllib.parse.urljoin(url, l["href"]))
    return time.perf_counter() - t0, reqs, hits
for label, w, g in [(f"one group ({GROUP}), sequential", 1, GROUP), (f"one group ({GROUP}), 16 threads", 16, GROUP),
                    ("whole tree, 16 threads", 16, None), ("whole tree, sequential", 1, None)]:
    t, n, h = run(w, g); print(f"{label:36s} requests={n:5d} hits={h:5d} time={t:7.2f} s", flush=True)
