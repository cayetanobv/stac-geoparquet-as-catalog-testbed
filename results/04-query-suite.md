# Query suite

Sixteen query shapes against each index over HTTPS, three cold runs each in a fresh DuckDB process and three warm runs in one process after a first run. Measured on 2026-10-23 with DuckDB 1.5.6 from a machine with about 150 ms round trip to Google Cloud Storage. Requests count one HEAD plus the range GETs. Bytes are what the query read from the file.

Runner: `scripts/run_suite.py`. Rerun any table with the command printed above it, or point the runner at another index.

```bash
python3 scripts/run_suite.py <index URL> --lon <x> --lat <y> --grp <group id> --kw <keyword> --cat <root id> --id <collection id> --runs 3
```

The C1 row in each table comes from a second run with a keyword that occurs inside the group, named in the note under the table. The first run's keyword did not, and returned zero rows.

## What the four tables show

- **Cold queries cost 0.5 to 1 s and warm queries 0.15 to 0.25 s, whatever the question.** The cold time is the TLS handshake plus three to five range requests. The warm time is the range requests on an open connection. Rows, bytes, and query shape barely move either figure, until a query reads a large column.
- **Bytes follow the columns a query names, not the rows it returns.** The keyword query on Madrid reads 436 KB because `keywords` is 28 percent of the file. The description search reads the `description` column. A count on `bbox` reads 16 KB, the footer alone.
- **A box test on the `bbox` struct can finish without a scan.** When every row group's statistics prove the filter true, DuckDB answers from the footer and the planner removes the scan. That is why S3 reports 0.00 s on Berlin and Madrid: the number excludes the footer fetch, which is one HEAD and one GET. The registry file needed a scan because its statistics span the globe.
- **Reading `original` is the expensive case, and row groups fix it.** One document costs 5.7 MB on the one-row-group registry file and 1.1 MB on the three-row-group file. Every other query pays one or two more requests on the three-row-group file and loses nothing visible.
- **Counts agree with the JSON walk.** S1 gives 367, 1,964, and 2,254, the numbers the walk produced on the same catalogs.


## Berlin Geoportal, 371 rows, 320 KB, 1 row group

Index: `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet`  point 13.405,52.52  group `verkehr`  keyword `Straßenbefahrung`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 367 | 3 | 24.6KiB | 0.71, 1.18, 0.84 s | 0.84 s | 0.17 s |
| S2 point in extent, under one group | 19 | 4 | 25.4KiB | 0.68, 0.53, 0.66 s | 0.66 s | 0.19 s |
| S3 box intersects extent, bbox struct only | 371 | 2 | 16.0KiB | 0.00, 0.00, 0.00 s | 0.00 s | 0.23 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 14 | 3 | 30.1KiB | 0.51, 0.80, 0.56 s | 0.56 s | 0.25 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 5 | 39.1KiB | 0.93, 0.73, 1.04 s | 0.93 s | 0.43 s |
| T1 everything under one group, id and title | 19 | 5 | 24.8KiB | 1.00, 0.97, 0.86 s | 0.97 s | 0.23 s |
| T2 collections per direct parent | 36 | 3 | 16.7KiB | 0.71, 0.53, 0.83 s | 0.71 s | 0.16 s |
| T3 one catalog by root id, one group | 19 | 3 | 16.7KiB | 0.63, 0.81, 0.62 s | 0.63 s | 0.24 s |
| A1 keyword equality | 49 | 2 | 16.0KiB | 0.27, 0.49, 0.44 s | 0.44 s | 0.24 s |
| A2 title substring, case-insensitive | 49 | 3 | 19.5KiB | 0.65, 0.59, 0.73 s | 0.65 s | 0.15 s |
| A3 description substring | 51 | 3 | 39.8KiB | 0.59, 0.57, 0.71 s | 0.59 s | 0.20 s |
| A4 license equality | 1 | 3 | 16.0KiB | 0.47, 0.57, 0.50 s | 0.50 s | 0.20 s |
| A5 temporal: end open or after 2024 | 370 | 3 | 16.0KiB | 0.67, 0.74, 0.63 s | 0.67 s | 0.24 s |
| D1 one full document by catalog and id | 1 | 5 | 266.9KiB | 0.91, 1.17, 0.87 s | 0.91 s | 0.17 s |
| D2 field inside the JSON document for a group: providers | 19 | 5 | 266.9KiB | 0.78, 0.92, 0.82 s | 0.82 s | 0.17 s |
| C1 combined: group, point, keyword, title returned | 3 | 4 | 39.1KiB | 0.76, 0.90, 1.23 s | 0.90 s | 0.21 s |

C1 uses the keyword `Radverkehr`, which occurs inside the group.

## Comunidad de Madrid, 1,964 rows, 1.5 MB, 1 row group

Index: `https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Educación`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 1964 | 3 | 16.1KiB | 0.52, 0.47, 0.82 s | 0.52 s | 0.16 s |
| S2 point in extent, under one group | 146 | 4 | 17.4KiB | 0.60, 0.84, 0.79 s | 0.79 s | 0.16 s |
| S3 box intersects extent, bbox struct only | 1964 | 2 | 16.0KiB | 0.00, 0.00, 0.00 s | 0.00 s | 0.20 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 0 | 3 | 16.3KiB | 0.52, 0.53, 0.51 s | 0.52 s | 0.81 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 5 | 77.3KiB | 1.81, 0.84, 1.12 s | 1.12 s | 0.17 s |
| T1 everything under one group, id and title | 146 | 5 | 78.5KiB | 0.73, 0.75, 0.77 s | 0.75 s | 0.18 s |
| T2 collections per direct parent | 159 | 3 | 17.2KiB | 0.60, 0.71, 0.58 s | 0.60 s | 0.26 s |
| T3 one catalog by root id, one group | 146 | 3 | 17.2KiB | 0.61, 0.61, 0.69 s | 0.61 s | 0.19 s |
| A1 keyword equality | 151 | 3 | 435.6KiB | 0.87, 0.65, 0.62 s | 0.65 s | 0.20 s |
| A2 title substring, case-insensitive | 24 | 3 | 47.8KiB | 0.54, 0.51, 0.94 s | 0.54 s | 0.17 s |
| A3 description substring | 57 | 3 | 94.6KiB | 0.64, 0.55, 0.66 s | 0.64 s | 0.20 s |
| A4 license equality | 1 | 3 | 16.0KiB | 0.54, 0.66, 0.54 s | 0.54 s | 0.22 s |
| A5 temporal: end open or after 2024 | 1964 | 3 | 16.1KiB | 0.52, 0.52, 0.63 s | 0.52 s | 0.22 s |
| D1 one full document by catalog and id | 1 | 5 | 1.3MiB | 1.28, 1.33, 1.14 s | 1.28 s | 0.16 s |
| D2 field inside the JSON document for a group: providers | 20 | 5 | 1.3MiB | 1.16, 1.14, 1.24 s | 1.16 s | 0.18 s |
| C1 combined: group, point, keyword, title returned | 42 | 6 | 531.7KiB | 1.81, 1.10, 1.08 s | 1.10 s | 0.18 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 6.5 MB, 1 row group, Hilbert order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `flood`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 3 | 122.4KiB | 0.57, 0.58, 0.68 s | 0.58 s | 0.31 s |
| S2 point in extent, under one group | 150 | 4 | 139.8KiB | 0.88, 0.75, 0.70 s | 0.75 s | 0.18 s |
| S3 box intersects extent, bbox struct only | 2254 | 6 | 105.7KiB | 0.78, 1.04, 0.74 s | 0.78 s | 0.24 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 4 | 190.0KiB | 0.87, 1.08, 1.92 s | 1.08 s | 0.42 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 5 | 282.0KiB | 1.32, 0.98, 0.93 s | 0.98 s | 0.16 s |
| T1 everything under one group, id and title | 162 | 5 | 193.0KiB | 0.73, 1.09, 0.93 s | 0.93 s | 0.18 s |
| T2 collections per direct parent | 716 | 3 | 33.4KiB | 0.46, 0.66, 1.58 s | 0.66 s | 0.22 s |
| T3 one catalog by root id, one group | 146 | 3 | 33.4KiB | 0.65, 0.73, 0.66 s | 0.66 s | 0.21 s |
| A1 keyword equality | 8 | 3 | 488.0KiB | 0.90, 0.74, 0.68 s | 0.74 s | 0.18 s |
| A2 title substring, case-insensitive | 11 | 3 | 102.6KiB | 0.51, 0.50, 0.55 s | 0.51 s | 0.17 s |
| A3 description substring | 26 | 3 | 458.2KiB | 0.64, 0.71, 0.87 s | 0.71 s | 0.17 s |
| A4 license equality | 3 | 3 | 17.5KiB | 0.61, 0.44, 0.62 s | 0.61 s | 0.18 s |
| A5 temporal: end open or after 2024 | 5671 | 3 | 18.0KiB | 0.57, 0.44, 0.79 s | 0.57 s | 0.21 s |
| D1 one full document by catalog and id | 1 | 5 | 5.7MiB | 2.74, 2.28, 2.16 s | 2.28 s | 0.20 s |
| D2 field inside the JSON document for a group: providers | 20 | 5 | 5.7MiB | 2.80, 2.78, 2.83 s | 2.80 s | 0.21 s |
| C1 combined: group, point, keyword, title returned | 42 | 7 | 868.9KiB | 1.23, 1.31, 1.35 s | 1.31 s | 0.19 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 5.8 MB, 3 row groups of 2,048 rows, tree order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048.parquet`  point -3.7038,40.4168  group `demografia`  keyword `flood`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 5 | 124.2KiB | 0.71, 0.53, 0.52 s | 0.53 s | 0.17 s |
| S2 point in extent, under one group | 150 | 7 | 121.9KiB | 0.86, 0.73, 0.67 s | 0.73 s | 0.15 s |
| S3 box intersects extent, bbox struct only | 2254 | 14 | 105.8KiB | 0.79, 0.82, 0.75 s | 0.79 s | 0.15 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 5 | 191.5KiB | 0.71, 0.61, 0.62 s | 0.62 s | 0.33 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 9 | 246.5KiB | 0.97, 0.96, 0.92 s | 0.96 s | 0.17 s |
| T1 everything under one group, id and title | 162 | 9 | 151.0KiB | 0.74, 0.77, 0.79 s | 0.77 s | 0.28 s |
| T2 collections per direct parent | 716 | 5 | 28.7KiB | 0.57, 0.76, 0.89 s | 0.76 s | 0.21 s |
| T3 one catalog by root id, one group | 146 | 5 | 28.7KiB | 0.72, 0.64, 0.63 s | 0.64 s | 0.21 s |
| A1 keyword equality | 8 | 5 | 491.5KiB | 1.14, 0.79, 0.82 s | 0.82 s | 0.19 s |
| A2 title substring, case-insensitive | 11 | 5 | 126.2KiB | 0.67, 0.52, 0.58 s | 0.58 s | 0.22 s |
| A3 description substring | 26 | 5 | 448.5KiB | 0.79, 0.64, 0.84 s | 0.79 s | 0.17 s |
| A4 license equality | 3 | 5 | 16.8KiB | 0.55, 0.64, 0.62 s | 0.62 s | 0.26 s |
| A5 temporal: end open or after 2024 | 5671 | 5 | 18.0KiB | 0.57, 0.74, 0.76 s | 0.74 s | 0.21 s |
| D1 one full document by catalog and id | 1 | 7 | 1.1MiB | 1.24, 1.07, 1.31 s | 1.24 s | 0.16 s |
| D2 field inside the JSON document for a group: providers | 20 | 9 | 2.6MiB | 1.64, 1.45, 1.57 s | 1.57 s | 0.20 s |
| C1 combined: group, point, keyword, title returned | 42 | 9 | 370.3KiB | 1.09, 0.91, 0.91 s | 0.91 s | 0.20 s |

C1 uses the keyword `Total`, which occurs inside the group.
