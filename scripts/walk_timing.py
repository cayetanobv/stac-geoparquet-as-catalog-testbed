"""Time what a client does today: walk catalog JSONs over HTTPS, any depth, to find collections
under one group whose bbox contains a point.  usage: walk_timing.py ROOT_URL LON LAT GROUP [fresh]
Each thread keeps one connection alive per host. Pass `fresh` to open a new connection for every
document instead, as urllib does and as the measurements before 2026-10-25 did.

GROUP as `find:TERM,TERM` makes the client find the group itself, three runs each: fetch the root,
keep every child whose link title contains a term, and walk those subtrees, or every subtree when none
matches. `describe:TERM,TERM` also fetches each child catalog and matches its title and description.
Terms match without case or accents."""
import http.client, json, sys, threading, time, unicodedata, urllib.request, urllib.parse, concurrent.futures as cf
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
        except ValueError: raise                      # not JSON: a retry returns the same page
        except Exception:
            if a == 4: raise
            time.sleep(0.5 * 2 ** a)
def fetch_or_fail(url):
    try: return fetch(url)
    except Exception as e: return e
def contains(b, x, y):
    # a bbox with west > east crosses the antimeridian, as in scripts/build_index.sql
    in_x = b[0] <= x <= b[2] if b[0] <= b[2] else (x >= b[0] or x <= b[2])
    return in_x and b[1] <= y <= b[3]
def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()
def walk(ex, frontier, keep=lambda url, link: True, fetched=()):
    """Breadth-first from `frontier`, plus documents already `fetched` as (url, doc), which cost no request here."""
    reqs = 0; hits = 0; failed = []; docs = list(fetched)
    while frontier or docs:
        docs += zip(frontier, ex.map(fetch_or_fail, frontier)); reqs += len(frontier); frontier = []
        for url, d in docs:
            if isinstance(d, Exception):              # counted as a request, its subtree is not walked
                failed.append(f"{url}: {type(d).__name__}: {str(d)[:80]}"); continue
            if d.get("type") == "Collection":
                hits += contains(d["extent"]["spatial"]["bbox"][0], QX, QY)
                continue
            frontier += [urllib.parse.urljoin(url, l["href"]) for l in d["links"] if l["rel"] == "child" and keep(url, l)]
        docs = []
    return reqs, hits, failed
def run(workers, group):
    t0 = time.perf_counter()
    # when a group is requested, prune at the root to that group's subtree only
    keep = lambda url, l: not (group and url == ROOT and l["href"].strip("./").split("/")[0] != group
                               and l.get("portolan_registry:id") != group)
    with cf.ThreadPoolExecutor(workers) as ex: reqs, hits, failed = walk(ex, [ROOT], keep)
    return time.perf_counter() - t0, reqs, hits, failed
def find(workers, terms, describe):
    """Find the group from the root's child links, then walk it. Returns the find step and the whole flow separately."""
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(workers) as ex:
        root = fetch(ROOT); reqs = 1
        kids = [(urllib.parse.urljoin(ROOT, l["href"]), l.get("title", "")) for l in root["links"] if l["rel"] == "child"]
        docs = list(zip([u for u, _ in kids], ex.map(fetch_or_fail, [u for u, _ in kids]))) if describe else []
        reqs += len(docs)
        text = {u: t for u, t in kids}
        for u, d in docs:
            if not isinstance(d, Exception): text[u] += " " + d.get("title", "") + " " + d.get("description", "")
        chosen = [u for u, _ in kids if any(t in norm(text[u]) for t in terms)] or [u for u, _ in kids]   # none matches: walk them all
        t_find = time.perf_counter() - t0; reqs_find = reqs
        if describe: r, hits, failed = walk(ex, [], fetched=[(u, d) for u, d in docs if u in chosen])
        else: r, hits, failed = walk(ex, chosen)
    groups = [urllib.parse.urlsplit(u).path.rstrip("/").split("/")[-2] for u in chosen]
    return t_find, time.perf_counter() - t0, reqs_find, reqs + r, hits, failed, groups
mode = "fresh connections" if FRESH else "keep-alive"
if GROUP.split(":")[0] in ("find", "describe"):
    how, terms = GROUP.split(":", 1); terms = [norm(t) for t in terms.split(",")]
    for label, w in [(f"{how} group ({','.join(terms)}), sequential", 1), (f"{how} group ({','.join(terms)}), 16 threads", 16)]:
        for _ in range(3):
            tf, t, nf, n, h, f, g = find(w, terms, how == "describe")
            print(f"{label:45s} {mode} find_requests={nf:3d} find_time={tf:6.2f} s requests={n:5d} hits={h:5d} failed={len(f)} "
                  f"time={t:7.2f} s groups={','.join(g)}", flush=True)
            for x in f: print(f"  failed {x}", file=sys.stderr)
else:
    for label, w, g in [(f"one group ({GROUP}), sequential", 1, GROUP), (f"one group ({GROUP}), 16 threads", 16, GROUP),
                        ("whole tree, 16 threads", 16, None), ("whole tree, sequential", 1, None)]:
        t, n, h, f = run(w, g); print(f"{label:36s} {mode} requests={n:5d} hits={h:5d} failed={len(f)} time={t:7.2f} s", flush=True)
        for x in f: print(f"  failed {x}", file=sys.stderr)
