"""Mirror the metadata of every catalog in a Portolan registry export.
For each child of the registry, save every catalog.json and collection.json reachable through
child links under OUT_DIR/<portolan_registry:id>/, at the document's path relative to the root.
A document outside the root's directory is saved under OUT_DIR/<id>/_external/<host>/<path>.
Writes OUT_DIR/manifest.json with counts and failures.
usage: mirror_registry.py REGISTRY_CATALOGS_JSON_URL OUT_DIR [retry]
With "retry", only the catalogs that recorded failures in OUT_DIR/manifest.json are mirrored again."""
import json, os, sys, time, urllib.request, urllib.parse, concurrent.futures as cf
from collections import Counter

REGISTRY, OUT = sys.argv[1], sys.argv[2]
RETRY = len(sys.argv) > 3 and sys.argv[3] == "retry"
WORKERS = 12
UA = "Mozilla/5.0 (compatible; stac-geoparquet-as-catalog-testbed/0.1; +https://github.com/cayetanobv/stac-geoparquet-as-catalog-testbed)"

def fetch(url):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return r.read()
        except Exception as e:
            if a == 3: raise
            time.sleep(0.5 * 2 ** a)

def local_path(root_url, url, folder):
    base = root_url.rsplit("/", 1)[0] + "/"
    if url.startswith(base):
        rel = url[len(base):]
    else:
        p = urllib.parse.urlparse(url)
        rel = os.path.join("_external", p.netloc, p.path.lstrip("/"))
    return os.path.join(folder, urllib.parse.unquote(rel))

def mirror(root_url, folder):
    counts, failures, frontier, seen = Counter(), [], [root_url], set()
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        while frontier:
            def get(u):
                try: return fetch(u)
                except Exception as e: return e
            docs = list(zip(frontier, ex.map(get, frontier)))
            frontier = []
            for url, raw in docs:
                seen.add(url)
                if isinstance(raw, Exception):
                    failures.append({"url": url, "error": str(raw)}); continue
                try:
                    doc = json.loads(raw)
                except Exception as e:
                    failures.append({"url": url, "error": f"not JSON: {e}"}); continue
                path = local_path(root_url, url, folder)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f: f.write(raw)
                counts[doc.get("type")] += 1
                if doc.get("type") == "Collection": continue
                for l in doc.get("links", []):
                    if l.get("rel") == "child":
                        u = urllib.parse.urljoin(url, l["href"])
                        if u not in seen: frontier.append(u)
    return counts, failures

reg = json.loads(fetch(REGISTRY))
children = [l for l in reg["links"] if l["rel"] == "child"]
manifest = {"registry": REGISTRY, "mirrored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "catalogs": []}
previous = {}
if RETRY:
    old = json.load(open(os.path.join(OUT, "manifest.json")))
    previous = {c["id"]: c for c in old["catalogs"]}
    children = [l for l in children if previous.get(l["portolan_registry:id"], {}).get("failures")]
    manifest["catalogs"] = [c for c in old["catalogs"] if not c["failures"]]
t_all = time.perf_counter()
for i, l in enumerate(children, 1):
    rid = l["portolan_registry:id"]; folder = os.path.join(OUT, rid)
    t0 = time.perf_counter()
    counts, failures = mirror(l["href"], folder)
    entry = {"id": rid, "title": l.get("title"), "root": l["href"], "status": l.get("portolan_registry:status"),
             "catalogs": counts.get("Catalog", 0), "collections": counts.get("Collection", 0),
             "failures": failures, "seconds": round(time.perf_counter() - t0, 1)}
    manifest["catalogs"].append(entry)
    print(f"[{i:2d}/{len(children)}] {rid:36s} catalogs={entry['catalogs']:4d} collections={entry['collections']:5d} failures={len(failures):3d} {entry['seconds']:6.1f}s", flush=True)
manifest["catalogs"].sort(key=lambda c: c["id"])
manifest["seconds"] = round(time.perf_counter() - t_all, 1)
with open(os.path.join(OUT, "manifest.json"), "w") as f: json.dump(manifest, f, indent=2, ensure_ascii=False)
print(f"total catalogs={sum(c['catalogs'] for c in manifest['catalogs'])} collections={sum(c['collections'] for c in manifest['catalogs'])} failures={sum(len(c['failures']) for c in manifest['catalogs'])} in {manifest['seconds']}s")
