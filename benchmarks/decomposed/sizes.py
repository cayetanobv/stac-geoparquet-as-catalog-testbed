"""Size on disk and in memory of schema 8 and schema 9 files, with the memory of the column sets a client reads.
search: the columns of the place, time and topic query (type, id, title, keywords, geometry, bbox, start_datetime, end_datetime)
document: the columns that hold the full document; `original` in schema 8, every column except the search-only ones in schema 9
MB is 10^6 bytes. usage: uv run python sizes.py FILE [FILE ...]"""
import os, sys, pyarrow.parquet as pq
SEARCH = ["type", "id", "title", "keywords", "geometry", "bbox", "start_datetime", "end_datetime"]
DERIVED = ["geometry", "bbox", "start_datetime", "end_datetime", "parents", "href"]
def mb(n): return f"{n / 1e6:.2f} MB"
print("| File | On disk | Whole table in memory | Search columns in memory | Document columns in memory |")
print("|---|---|---|---|---|")
for f in sys.argv[1:]:
    t = pq.read_table(f); names = t.column_names
    s = sum(t.column(c).nbytes for c in SEARCH if c in names) if "geometry" in names else None
    doc = (t.column("original").nbytes if "original" in names
           else sum(t.column(c).nbytes for c in names if c not in DERIVED))
    print(f"| `{f}` | {mb(os.path.getsize(f))} | {mb(t.nbytes)} | {mb(s) if s else 'no search columns'} | {mb(doc)} |")
