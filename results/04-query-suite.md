# Query suite

Sixteen query shapes against each index over HTTPS, three cold runs each in a fresh DuckDB process and three warm runs in one process after a first run. Measured on 2026-10-23 with DuckDB 2.0.0 and Python 3.14.9 from a machine with about 150 ms round trip to Google Cloud Storage. Requests count one HEAD plus the range GETs. Bytes are what the query read from the file. See [docs/method.md](../docs/method.md).

Runner: `scripts/run_suite.py`. Rerun any table with the command under its heading, or point the runner at another index.

```bash
uv run python scripts/run_suite.py <index URL> --lon <x> --lat <y> --grp <group id> --kw <keyword> --cat <root id> --id <collection id> --runs 3
```

## What the five tables show

- **On a file of a few megabytes, DuckDB 2.0 reads the whole file in one request, whatever the query.** Every Berlin query reads 312 KB and every Madrid query reads 1.4 MB. The prefetch cost model coalesces the byte ranges a query needs when the gaps between them are small, and on these files that is everything. Cold time is then one handshake plus one request: 0.44 to 0.56 s on Berlin, 0.7 to 0.9 s on Madrid.
- **On the 6.5 MB registry file the bytes follow the columns named.** A count on `license` reads 21 KB, a title search 110 KB, a keyword search 490 KB, the `parents` filter 1.0 MB, and one `original` document 5.9 MB. Requests stay at three to seven.
- **Warm queries cost 0.06 to 0.12 s whatever the question.** After the first run the file is in DuckDB's buffer and only the range requests on an open connection remain.
- **A box test on the `bbox` struct can finish without a scan.** When every row group's statistics prove the filter true, DuckDB answers from the footer and the planner removes the scan, which is why S3 reports 0.00 s on Berlin and Madrid. That number excludes the footer fetch. The registry file needs a scan because its statistics span the globe.
- **More row groups mean more requests and more bytes under DuckDB 2.0.** The 3-group file reads 2.8 MB in 8 requests for the point query that the 1-group file answers with 1.0 MB in 4. The 12-group file reads 5.6 MB in 34 requests. Only the full-document lookup gains, and only on the 3-group file.
- **Counts agree with the JSON walk.** S1 gives 367, 1,964, and 2,254, the numbers the walk produced on the same catalogs.

Under DuckDB 1.5.6, measured on 2026-10-23 before the toolchain was pinned, the same suite read 16 to 30 KB per query on Berlin in three to five requests, and the 3-group registry file cut the one-document lookup fivefold with no cost elsewhere. The engine's prefetch strategy, not the file, changed those two results.


## Berlin Geoportal, 371 rows, 312 KB, 1 row group

Index: `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet`  point 13.405,52.52  group `verkehr`  keyword `Radverkehr`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 367 | 2 | 312.4KiB | 0.45, 0.47, 0.43 s | 0.45 s | 0.08 s |
| S2 point in extent, under one group | 19 | 2 | 312.4KiB | 0.55, 0.51, 0.45 s | 0.51 s | 0.06 s |
| S3 box intersects extent, bbox struct only | 371 | 2 | 312.4KiB | 0.00, 0.00, 0.00 s | 0.00 s | 0.00 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 14 | 2 | 312.4KiB | 0.48, 0.46, 0.43 s | 0.46 s | 0.06 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 2 | 312.4KiB | 0.52, 0.47, 0.49 s | 0.49 s | 0.08 s |
| T1 everything under one group, id and title | 19 | 2 | 312.4KiB | 0.47, 0.47, 0.44 s | 0.47 s | 0.06 s |
| T2 collections per direct parent | 36 | 2 | 312.4KiB | 0.44, 0.77, 0.45 s | 0.45 s | 0.10 s |
| T3 one catalog by root id, one group | 19 | 2 | 312.4KiB | 0.56, 0.52, 0.66 s | 0.56 s | 0.06 s |
| A1 keyword equality | 4 | 2 | 312.4KiB | 0.55, 0.47, 0.43 s | 0.47 s | 0.07 s |
| A2 title substring, case-insensitive | 4 | 2 | 312.4KiB | 0.48, 0.55, 0.50 s | 0.50 s | 0.07 s |
| A3 description substring | 7 | 2 | 312.4KiB | 0.48, 0.60, 0.54 s | 0.54 s | 0.07 s |
| A4 license equality | 1 | 2 | 312.4KiB | 0.44, 0.43, 0.49 s | 0.44 s | 0.09 s |
| A5 temporal: end open or after 2024 | 370 | 2 | 312.4KiB | 0.51, 0.46, 0.47 s | 0.47 s | 0.08 s |
| D1 one full document by catalog and id | 1 | 2 | 312.4KiB | 0.87, 0.47, 0.46 s | 0.47 s | 0.09 s |
| D2 field inside the JSON document for a group: providers | 19 | 2 | 312.4KiB | 0.47, 0.45, 0.44 s | 0.45 s | 0.06 s |
| C1 combined: group, point, keyword, title returned | 3 | 2 | 312.4KiB | 0.45, 0.46, 0.55 s | 0.46 s | 0.06 s |

C1 uses the keyword `Radverkehr`, which occurs inside the group.

## Comunidad de Madrid, 1,964 rows, 1.5 MB, 1 row group

Index: `https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 1964 | 2 | 1.4MiB | 0.85, 0.87, 0.79 s | 0.85 s | 0.08 s |
| S2 point in extent, under one group | 146 | 2 | 1.4MiB | 0.77, 0.87, 0.71 s | 0.77 s | 0.07 s |
| S3 box intersects extent, bbox struct only | 1964 | 2 | 1.4MiB | 0.00, 0.00, 0.00 s | 0.00 s | 0.00 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 0 | 2 | 1.4MiB | 0.78, 1.15, 1.04 s | 1.04 s | 0.07 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 2 | 1.4MiB | 0.77, 0.75, 1.62 s | 0.77 s | 0.11 s |
| T1 everything under one group, id and title | 146 | 2 | 1.4MiB | 2.51, 3.17, 1.13 s | 2.51 s | 0.10 s |
| T2 collections per direct parent | 159 | 2 | 1.4MiB | 1.02, 0.71, 0.70 s | 0.71 s | 0.07 s |
| T3 one catalog by root id, one group | 146 | 2 | 1.4MiB | 0.87, 0.91, 0.84 s | 0.87 s | 0.06 s |
| A1 keyword equality | 261 | 2 | 1.4MiB | 0.98, 0.77, 0.75 s | 0.77 s | 0.07 s |
| A2 title substring, case-insensitive | 49 | 2 | 1.4MiB | 0.75, 0.80, 0.77 s | 0.77 s | 0.09 s |
| A3 description substring | 119 | 2 | 1.4MiB | 0.87, 0.83, 0.98 s | 0.87 s | 0.10 s |
| A4 license equality | 1 | 2 | 1.4MiB | 0.91, 0.76, 0.86 s | 0.86 s | 0.06 s |
| A5 temporal: end open or after 2024 | 1964 | 2 | 1.4MiB | 0.73, 0.79, 0.83 s | 0.79 s | 0.08 s |
| D1 one full document by catalog and id | 1 | 2 | 1.4MiB | 0.78, 0.98, 0.90 s | 0.90 s | 0.09 s |
| D2 field inside the JSON document for a group: providers | 20 | 2 | 1.4MiB | 0.85, 0.91, 0.84 s | 0.85 s | 0.08 s |
| C1 combined: group, point, keyword, title returned | 42 | 2 | 1.4MiB | 0.78, 0.80, 0.86 s | 0.80 s | 0.08 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 6.5 MB, 1 row group, Hilbert order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 4 | 1001.5KiB | 0.85, 0.88, 0.85 s | 0.85 s | 0.09 s |
| S2 point in extent, under one group | 150 | 4 | 997.5KiB | 0.88, 0.85, 0.82 s | 0.85 s | 0.07 s |
| S3 box intersects extent, bbox struct only | 2254 | 4 | 109.5KiB | 0.51, 0.54, 0.53 s | 0.53 s | 0.06 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 5 | 1.0MiB | 1.01, 0.94, 0.96 s | 0.96 s | 0.07 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 6 | 1.1MiB | 2.04, 1.08, 1.06 s | 1.08 s | 0.08 s |
| T1 everything under one group, id and title | 162 | 5 | 1.1MiB | 1.13, 1.08, 1.10 s | 1.10 s | 0.06 s |
| T2 collections per direct parent | 716 | 4 | 997.5KiB | 0.85, 0.84, 0.93 s | 0.85 s | 0.06 s |
| T3 one catalog by root id, one group | 146 | 4 | 997.5KiB | 0.80, 0.88, 0.82 s | 0.82 s | 0.08 s |
| A1 keyword equality | 261 | 4 | 489.5KiB | 0.68, 0.85, 0.75 s | 0.75 s | 0.08 s |
| A2 title substring, case-insensitive | 50 | 3 | 109.5KiB | 0.52, 1.43, 0.48 s | 0.52 s | 0.10 s |
| A3 description substring | 186 | 3 | 461.5KiB | 0.67, 0.60, 0.55 s | 0.60 s | 0.08 s |
| A4 license equality | 3 | 3 | 21.5KiB | 1.33, 0.53, 0.45 s | 0.53 s | 0.09 s |
| A5 temporal: end open or after 2024 | 5671 | 3 | 25.5KiB | 0.54, 0.57, 0.44 s | 0.54 s | 0.06 s |
| D1 one full document by catalog and id | 1 | 7 | 5.9MiB | 2.14, 2.41, 2.80 s | 2.41 s | 0.11 s |
| D2 field inside the JSON document for a group: providers | 20 | 7 | 5.9MiB | 2.35, 3.52, 2.55 s | 2.55 s | 0.12 s |
| C1 combined: group, point, keyword, title returned | 42 | 7 | 1.6MiB | 1.16, 1.29, 1.19 s | 1.19 s | 0.08 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 5.8 MB, 3 row groups of 2,048 rows, tree order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 8 | 2.8MiB | 3.38, 1.77, 1.36 s | 1.77 s | 0.09 s |
| S2 point in extent, under one group | 150 | 8 | 2.8MiB | 1.39, 1.29, 1.35 s | 1.35 s | 0.07 s |
| S3 box intersects extent, bbox struct only | 2254 | 5 | 116.5KiB | 0.56, 0.53, 0.50 s | 0.53 s | 0.08 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 8 | 2.9MiB | 1.32, 1.78, 1.34 s | 1.34 s | 0.06 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 12 | 2.9MiB | 1.66, 1.50, 1.49 s | 1.50 s | 0.08 s |
| T1 everything under one group, id and title | 162 | 11 | 3.0MiB | 1.56, 1.63, 1.61 s | 1.61 s | 0.09 s |
| T2 collections per direct parent | 716 | 8 | 2.8MiB | 1.53, 1.32, 1.43 s | 1.43 s | 0.08 s |
| T3 one catalog by root id, one group | 146 | 8 | 2.8MiB | 1.29, 1.40, 1.35 s | 1.35 s | 0.11 s |
| A1 keyword equality | 261 | 8 | 1.9MiB | 2.99, 1.29, 1.18 s | 1.29 s | 0.07 s |
| A2 title substring, case-insensitive | 50 | 5 | 116.5KiB | 0.67, 0.56, 0.52 s | 0.56 s | 0.07 s |
| A3 description substring | 186 | 5 | 464.5KiB | 0.75, 0.57, 0.76 s | 0.75 s | 0.07 s |
| A4 license equality | 3 | 5 | 28.5KiB | 0.54, 0.60, 0.50 s | 0.54 s | 0.10 s |
| A5 temporal: end open or after 2024 | 5671 | 5 | 28.5KiB | 0.83, 0.59, 0.59 s | 0.59 s | 0.09 s |
| D1 one full document by catalog and id | 1 | 9 | 3.3MiB | 1.56, 1.90, 1.92 s | 1.90 s | 0.08 s |
| D2 field inside the JSON document for a group: providers | 20 | 12 | 5.3MiB | 2.01, 2.20, 2.12 s | 2.12 s | 0.07 s |
| C1 combined: group, point, keyword, title returned | 42 | 11 | 2.2MiB | 1.45, 1.40, 1.16 s | 1.40 s | 0.06 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 6.1 MB, 12 row groups of 512 rows, tree order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-pa512.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 34 | 5.6MiB | 2.33, 2.64, 2.30 s | 2.33 s | 0.08 s |
| S2 point in extent, under one group | 150 | 30 | 5.6MiB | 2.58, 2.50, 2.12 s | 2.50 s | 0.08 s |
| S3 box intersects extent, bbox struct only | 2254 | 14 | 193.3KiB | 0.64, 0.67, 0.62 s | 0.64 s | 0.06 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 30 | 5.7MiB | 2.59, 2.65, 4.77 s | 2.65 s | 0.08 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 30 | 5.6MiB | 2.26, 2.24, 2.21 s | 2.24 s | 0.06 s |
| T1 everything under one group, id and title | 162 | 46 | 5.7MiB | 2.20, 2.62, 2.44 s | 2.44 s | 0.07 s |
| T2 collections per direct parent | 716 | 30 | 5.6MiB | 2.46, 2.81, 2.40 s | 2.46 s | 0.08 s |
| T3 one catalog by root id, one group | 146 | 32 | 5.6MiB | 2.25, 2.35, 2.34 s | 2.34 s | 0.06 s |
| A1 keyword equality | 261 | 27 | 5.1MiB | 2.42, 2.09, 2.27 s | 2.27 s | 0.09 s |
| A2 title substring, case-insensitive | 50 | 15 | 209.3KiB | 0.61, 0.68, 0.71 s | 0.68 s | 0.05 s |
| A3 description substring | 186 | 15 | 585.3KiB | 0.66, 0.79, 1.03 s | 0.79 s | 0.06 s |
| A4 license equality | 3 | 15 | 109.3KiB | 0.57, 0.72, 0.82 s | 0.72 s | 0.08 s |
| A5 temporal: end open or after 2024 | 5671 | 15 | 113.3KiB | 0.63, 0.55, 0.55 s | 0.55 s | 0.07 s |
| D1 one full document by catalog and id | 1 | 20 | 4.7MiB | 2.00, 2.05, 2.18 s | 2.05 s | 0.07 s |
| D2 field inside the JSON document for a group: providers | 20 | 44 | 6.6MiB | 2.77, 2.52, 2.42 s | 2.52 s | 0.10 s |
| C1 combined: group, point, keyword, title returned | 42 | 31 | 2.4MiB | 1.26, 1.72, 1.37 s | 1.37 s | 0.09 s |

C1 uses the keyword `Total`, which occurs inside the group.
