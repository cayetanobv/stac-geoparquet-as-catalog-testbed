"""Size of index files on disk and in memory, per file and per top-level column.
Compressed and uncompressed sizes come from the Parquet footer. The in-memory size is what pyarrow holds after it reads
the whole file into an Arrow table, the form a browser client such as DuckDB-Wasm or Arrow JS also decodes into.
usage: uv run python sizes.py FILE [FILE ...]    prints one Markdown table for the files, then one per file by column"""
import os, sys, pyarrow.parquet as pq
from collections import defaultdict

def mb(n): return f"{n / 1e6:.2f} MB"

print("| File | Rows | Row groups | On disk | Uncompressed | In memory, Arrow | In memory without `original` and `links` |")
print("|---|---|---|---|---|---|---|")
per_col = {}
for f in sys.argv[1:]:
    pf = pq.ParquetFile(f); md = pf.metadata
    comp, unc = defaultdict(int), defaultdict(int)
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        for c in range(rg.num_columns):
            cc = rg.column(c); top = cc.path_in_schema.split(".")[0]
            comp[top] += cc.total_compressed_size; unc[top] += cc.total_uncompressed_size
    t = pf.read()
    light = t.drop_columns([c for c in ("original", "links") if c in t.column_names])
    print(f"| `{f}` | {md.num_rows:,} | {md.num_row_groups} | {mb(os.path.getsize(f))} | {mb(sum(unc.values()))} | {mb(t.nbytes)} | {mb(light.nbytes)} |")
    per_col[f] = (comp, unc, {n: t.column(n).nbytes for n in t.column_names})
for f, (comp, unc, mem) in per_col.items():
    print(f"\n`{f}`\n\n| Column | Compressed | Uncompressed | In memory |\n|---|---|---|---|")
    for n in mem:
        print(f"| `{n}` | {mb(comp[n])} | {mb(unc[n])} | {mb(mem[n])} |")
