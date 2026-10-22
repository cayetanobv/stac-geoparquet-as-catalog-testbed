"""Walk a static STAC catalog breadth-first and write one JSON line per collection with its ancestor chain.
usage: crawl.py ROOT_CATALOG OUT_JSONL [PUBLIC_ROOT_CATALOG_URL]
ROOT_CATALOG is an https URL or a local path to catalog.json (for example a mirror made by mirror_catalog.py).
With a local root, pass the catalog's public URL as the third argument so the href column holds canonical URLs."""
import json, os, sys, time, urllib.request, urllib.parse, concurrent.futures as cf
from collections import Counter

ROOT, OUT = sys.argv[1], sys.argv[2]
PUBLIC = sys.argv[3] if len(sys.argv) > 3 else None
if "://" not in ROOT:
    ROOT = "file://" + os.path.abspath(ROOT)
WORKERS = 12

def public_href(url):
    if PUBLIC and url.startswith(ROOT.rsplit("/", 1)[0] + "/"):
        return PUBLIC.rsplit("/", 1)[0] + "/" + url[len(ROOT.rsplit("/", 1)[0]) + 1:]
    return url

def fetch(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 4: raise
            time.sleep(0.5 * 2 ** attempt)

rows, catalogs = [], 0
frontier = [(ROOT, [])]                       # (url, parents)
with cf.ThreadPoolExecutor(WORKERS) as ex:
    while frontier:
        docs = list(ex.map(lambda t: (t[0], t[1], fetch(t[0])), frontier))
        frontier = []
        for url, parents, doc in docs:
            if doc.get("type") == "Collection":
                rows.append({"href": public_href(url), "parents": parents, "doc": doc})
                continue
            catalogs += 1
            chain = parents + [doc["id"]]
            frontier += [(urllib.parse.urljoin(url, l["href"]), chain) for l in doc["links"] if l["rel"] == "child"]

with open(OUT, "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"catalogs={catalogs} collections={len(rows)}")
print("depth of parents:", Counter(len(r["parents"]) for r in rows))
