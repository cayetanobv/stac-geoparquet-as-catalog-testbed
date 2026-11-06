"""Walk a local mirror breadth-first and write one JSON line per catalog and per collection, for build.sql.
Each line holds the row type, the public href, the ancestors as a list of {id, href} from the root to the
direct parent, and the full document. The root catalog has an empty list.
usage: crawl_tree.py catalog MIRROR_DIR PUBLIC_ROOT_CATALOG_URL OUT_JSONL
       crawl_tree.py registry MIRROR_DIR OUT_JSONL
In registry mode MIRROR_DIR is a mirror made by mirror_registry.py, and every registered catalog is walked from its
root, as crawl_registry.py does. The registry export itself gets no row, so the first ancestor of a row is the
registered catalog, as in the other indexes."""
import json, os, sys, urllib.parse
from collections import Counter

def walk(root_url, folder):
    base = root_url.rsplit("/", 1)[0] + "/"
    def local(url):                               # the same mapping as mirror_catalog.py and mirror_registry.py
        if url.startswith(base): rel = url[len(base):]
        else:
            p = urllib.parse.urlparse(url); rel = os.path.join("_external", p.netloc, p.path.lstrip("/"))
        return os.path.join(folder, urllib.parse.unquote(rel))
    rows, missing, frontier, seen = [], 0, [(root_url, [])], set()
    while frontier:
        nxt = []
        for url, parents in frontier:
            seen.add(url); path = local(url)
            if not os.path.exists(path): missing += 1; continue
            with open(path, encoding="utf-8") as f: doc = json.load(f)
            kind = doc.get("type")
            if kind not in ("Catalog", "Collection"): continue
            rows.append({"type": kind, "href": url, "parents": parents, "doc": doc})
            if kind == "Collection": continue     # a Portolan collection has no child collections
            chain = parents + [{"id": doc["id"], "href": url}]
            for l in doc.get("links", []):
                if l.get("rel") == "child":
                    u = urllib.parse.urljoin(url, l["href"])
                    if u not in seen: nxt.append((u, chain))
        frontier = nxt
    return rows, missing

mode = sys.argv[1]
if mode == "catalog":
    _, _, MIRROR, PUBLIC, OUT = sys.argv
    roots = [(PUBLIC, MIRROR)]
elif mode == "registry":
    _, _, MIRROR, OUT = sys.argv
    manifest = json.load(open(os.path.join(MIRROR, "manifest.json")))
    roots = [(c["root"], os.path.join(MIRROR, c["id"])) for c in manifest["catalogs"]]
else:
    sys.exit(__doc__)

kinds, missing = Counter(), 0
with open(OUT, "w", encoding="utf-8") as out:
    for root, folder in roots:
        rows, m = walk(root, folder)
        missing += m
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            kinds[r["type"]] += 1
print(f"catalog rows={kinds['Catalog']} collection rows={kinds['Collection']} missing documents={missing}")
