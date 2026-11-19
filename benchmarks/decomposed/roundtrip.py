"""Rebuild every document of a schema 9 file from its columns and compare it with `original` in the schema 8 file.

A row becomes a document this way: every core column that is not null, then every key of `extra_fields`. Inside a
struct, a null key is left out, because the struct holds every key that occurs in any document. Timestamps are
written back as RFC 3339 in UTC, with microseconds only when they are not zero.

Two results per file:
  exact     the rebuilt document equals the original as JSON values, key order ignored
  semantic  the same, after each timestamp string in extent.temporal.interval is read as an instant
For the documents that differ, the paths that differ are counted.

usage: uv run python roundtrip.py SCHEMA9_FILE SCHEMA8_FILE"""
import json, sys, collections
from datetime import datetime, timezone
import pyarrow.parquet as pq

NINE, EIGHT = sys.argv[1], sys.argv[2]
SKIP = {"geometry", "bbox", "start_datetime", "end_datetime", "extra_fields"}

def strip(v):  # drop the null keys a struct holds for keys this document does not have
    if isinstance(v, dict): return {k: strip(x) for k, x in v.items() if x is not None}
    if isinstance(v, list): return [strip(x) for x in v]
    return v

def iso(t):
    if t is None: return None
    t = t.astimezone(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.%fZ" if t.microsecond else "%Y-%m-%dT%H:%M:%SZ")

def rebuild(row):
    d = {}
    for k, v in row.items():
        if k in SKIP or v is None: continue
        if k == "summaries": d[k] = json.loads(v)
        elif k in ("assets", "item_assets"): d[k] = {a: strip(x) for a, x in v}
        elif k == "extent":
            d[k] = {"spatial": {"bbox": v["spatial"]["bbox"]},
                    "temporal": {"interval": [[iso(x) for x in i] for i in v["temporal"]["interval"]]}}
        else: d[k] = strip(v)
    if row["extra_fields"]: d.update(json.loads(row["extra_fields"]))
    return d

def instant(d):  # timestamps in the extent read as instants
    if "extent" in d:
        d = json.loads(json.dumps(d))
        d["extent"]["temporal"]["interval"] = [[None if x is None else datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
                                                 for x in i] for i in d["extent"]["temporal"]["interval"]]
    return d

def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys():
            if k not in a: yield f"{path}.{k} missing after rebuild"
            elif k not in b: yield f"{path}.{k} added by rebuild"
            else: yield from diff(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for x, y in zip(a, b): yield from diff(x, y, f"{path}[]")
    elif a != b or type(a) != type(b):
        yield f"{path} {type(b).__name__} -> {type(a).__name__}" if type(a) != type(b) else f"{path} value"

rows = pq.read_table(NINE).to_pylist()
orig = [json.loads(s) for s in pq.read_table(EIGHT, columns=["original"]).column("original").to_pylist()]
exact = semantic = 0
paths = collections.Counter()
for r, o in zip(rows, orig):
    d = rebuild(r)
    if d == o and not list(diff(d, o)): exact += 1
    if instant(d) == instant(o) and not list(diff(instant(d), instant(o))): semantic += 1
    else: paths.update(set(diff(instant(d), instant(o))))
print(f"{NINE}: {len(rows)} documents, exact {exact}, semantic {semantic}, differ {len(rows) - semantic}")
for p, n in paths.most_common(20): print(f"  {n:6d}  {p}")
