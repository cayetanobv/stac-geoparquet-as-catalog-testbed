"""Mirror the metadata of a static STAC catalog: every catalog.json and collection.json
reachable through child links, saved under OUT_DIR with the same relative paths as on the server.
Data assets are not downloaded.  usage: mirror_catalog.py ROOT_CATALOG_URL OUT_DIR"""
import json, os, sys, time, urllib.request, urllib.parse, concurrent.futures as cf
from collections import Counter

ROOT, OUT = sys.argv[1], sys.argv[2]
WORKERS = 12
BASE = ROOT.rsplit("/", 1)[0] + "/"            # directory of the root catalog

def fetch(url):
    for a in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if a == 4: raise
            time.sleep(0.5 * 2 ** a)

def save(url, raw):
    if not url.startswith(BASE):
        raise SystemExit(f"{url} is outside the root directory {BASE}; the mirror keeps one tree")
    path = os.path.join(OUT, urllib.parse.unquote(url[len(BASE):]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(raw)

counts, frontier, seen = Counter(), [ROOT], set()
with cf.ThreadPoolExecutor(WORKERS) as ex:
    while frontier:
        docs = list(zip(frontier, ex.map(fetch, frontier)))
        frontier = []
        for url, raw in docs:
            seen.add(url); save(url, raw)
            doc = json.loads(raw); counts[doc.get("type")] += 1
            if doc.get("type") == "Collection":
                continue
            for l in doc["links"]:
                if l["rel"] == "child":
                    u = urllib.parse.urljoin(url, l["href"])
                    if u not in seen: frontier.append(u)
print(f"mirrored into {OUT}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
