"""Walk every catalog in a registry mirror made by mirror_registry.py and write one JSON line per
collection, with the ancestor chain and the collection's public URL, for build_index.sql.
usage: crawl_registry.py MIRROR_DIR OUT_JSONL"""
import json, os, sys, urllib.parse
from collections import Counter

MIRROR, OUT = sys.argv[1], sys.argv[2]
manifest = json.load(open(os.path.join(MIRROR, "manifest.json")))

def load(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def walk(root_url, folder):
    """Breadth-first over the local files, resolving child hrefs against the public URL
    and mapping each public URL back to its local file the same way mirror_registry.py saved it."""
    base = root_url.rsplit("/", 1)[0] + "/"
    def local(url):
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
            doc = load(path)
            if doc.get("type") == "Collection":
                rows.append({"href": url, "parents": parents, "doc": doc}); continue
            chain = parents + [doc["id"]]
            for l in doc.get("links", []):
                if l.get("rel") == "child":
                    u = urllib.parse.urljoin(url, l["href"])
                    if u not in seen: nxt.append((u, chain))
        frontier = nxt
    return rows, missing

total, roots = 0, Counter()
with open(OUT, "w", encoding="utf-8") as out:
    for c in manifest["catalogs"]:
        rows, missing = walk(c["root"], os.path.join(MIRROR, c["id"]))
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        total += len(rows)
        if rows: roots[rows[0]["parents"][0]] += 1
        print(f"{c['id']:36s} collections={len(rows):5d} missing_docs={missing}", flush=True)
print(f"total collections={total}")
dups = {k: v for k, v in roots.items() if v > 1}
print("root ids shared by more than one registered catalog:", dups or "none")
