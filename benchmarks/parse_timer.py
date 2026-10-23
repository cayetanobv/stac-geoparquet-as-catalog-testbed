"""Pair DuckDB `.timer on` output with the `SELECT '<label>' AS q;` line that precedes each query.
Each label is paired with the last Run Time printed before the next label, so it works whether or not
the CLI prints a Run Time for the label statement itself (1.5 does, 2.0 does not).
usage: duckdb < queries.sql 2>&1 | python3 parse_timer.py"""
import re, sys
rows, label, last = [], None, None
def flush():
    if label and last: rows.append((label, *last))
for line in sys.stdin:
    m = re.match(r"^│ ((?:[A-Z]\d?|S\d|---) ?[^│]*?)\s*│$", line)
    if m and not re.match(r"^[\d.]+$", m.group(1).strip()):
        flush(); label, last = m.group(1).strip().lstrip("- "), None
        continue
    t = re.match(r"Run Time \(s\): real ([\d.]+) user ([\d.]+)", line)
    if t: last = (float(t.group(1)), float(t.group(2)))
flush()
for l, real, user in rows:
    print(f"{l:60s} wall {real:7.3f} s  cpu {user:7.3f} s")
