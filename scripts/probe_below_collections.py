"""Follow the child links of every Collection in the registry mirror, live, and count what lies below,
to check that stopping the crawl at the first Collection loses no Collection.
usage: probe_below_collections.py MIRROR_DIR OUT_JSON   (MIRROR_DIR as written by mirror_registry.py)"""
import json, os, sys, glob, urllib.request, urllib.parse, concurrent.futures as cf
from collections import Counter

MIRROR, OUT = sys.argv[1], sys.argv[2]
WORKERS = 24
UA = "Mozilla/5.0 (compatible; stac-geoparquet-as-catalog-testbed/0.1; +https://github.com/cayetanobv/stac-geoparquet-as-catalog-testbed)"
roots = {c["id"]: c["root"] for c in json.load(open(os.path.join(MIRROR, "manifest.json")))["catalogs"]}

def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)}

# the child links of every mirrored Collection, resolved against its public URL
starts = []
for path in glob.glob(os.path.join(MIRROR, "*", "**", "collection.json"), recursive=True):
    cat = os.path.relpath(path, MIRROR).split(os.sep)[0]
    kids = [l["href"] for l in json.load(open(path)).get("links", []) if l.get("rel") == "child"]
    if kids:
        url = roots[cat].rsplit("/", 1)[0] + "/" + os.path.relpath(path, os.path.join(MIRROR, cat)).replace(os.sep, "/")
        starts += [(cat, urllib.parse.urljoin(url, k), 1) for k in kids]

types, depth, per_cat, items, errors, nested, seen, frontier = Counter(), Counter(), Counter(), 0, [], [], set(), starts
with cf.ThreadPoolExecutor(WORKERS) as ex:
    while frontier:
        frontier = [t for t in frontier if t[1] not in seen]
        seen.update(t[1] for t in frontier)
        docs = list(ex.map(lambda t: (*t, fetch(t[1])), frontier))
        frontier = []
        for cat, url, d, doc in docs:
            if "_error" in doc:
                errors.append((url, doc["_error"])); continue
            types[doc.get("type")] += 1; depth[d] += 1; per_cat[cat] += 1
            if doc.get("type") == "Collection":
                nested.append(url)
            links = doc.get("links", [])
            items += sum(l.get("rel") == "item" for l in links)
            frontier += [(cat, urllib.parse.urljoin(url, l["href"]), d + 1) for l in links if l.get("rel") == "child"]
        print(f"level done, documents={sum(types.values())} next={len(frontier)}", flush=True)

json.dump({"start_links": len(starts), "types": types, "depth": depth, "documents_per_catalog": per_cat, "item_links": items,
           "errors": len(errors), "error_sample": errors[:10], "collections_below": len(nested), "collection_sample": nested[:50]},
          open(OUT, "w"), indent=1)
print(open(OUT).read())
