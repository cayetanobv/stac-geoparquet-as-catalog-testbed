# Query suite

Sixteen query shapes against each index over HTTPS, three cold runs each in a fresh DuckDB process and three warm runs in one process after a first run. Measured on 2026-10-23 with DuckDB 2.0.0 and Python 3.14.9, from the test machine described in [docs/method.md](../docs/method.md). Requests count one HEAD plus the range GETs. Bytes are what the query read from the file.

Runner: `scripts/run_suite.py`. Rerun any table with the command under its heading, or point the runner at another index.

```bash
uv run python scripts/run_suite.py <index URL> --lon <x> --lat <y> --grp <group id> --kw <keyword> --cat <root id> --id <collection id> --runs 3
```

## What the five tables show

- **On a file of a few megabytes, DuckDB 2.0 reads the whole file in one request, whatever the query.** Every Berlin query reads 312 KB and every Madrid query reads 1.4 MB. The prefetch cost model coalesces the byte ranges a query needs when the gaps between them are small, and on these files that is everything. Cold time is then one handshake plus one request: medians of 0.44 to 0.56 s on Berlin and 0.71 to 1.04 s on Madrid, leaving out S3, and T1 on Madrid, whose three runs ranged from 1.1 to 3.2 s.
- **On the 6.5 MB registry file the bytes follow the columns named.** A count on `license` reads 21 KB, a title search 110 KB, a keyword search 490 KB, the `parents` filter 1.0 MB, and one `original` document 5.9 MB. Requests stay at three to seven.
- **Warm queries cost 0.06 to 0.12 s whatever the question.** They are cache hits: after the first run DuckDB holds the file, sends one HEAD request to check it, and reads no data. They show what a repeated query costs in one session, not what a new question costs a new client.
- **A box test on the `bbox` struct can finish without a scan.** When every row group's statistics prove the filter true, DuckDB answers from the footer and the planner removes the scan. It reads the file while planning, outside the time `EXPLAIN ANALYZE` reports, which is why S3 shows 0.00 s on Berlin and Madrid. The whole process took about 0.5 s of wall clock, the same as the other queries. The registry file needs a scan because its statistics span the globe.
- **More row groups mean more requests and more bytes under DuckDB 2.0.** The 3-group file reads 2.8 MB in 8 requests for the point query that the 1-group file answers with 1.0 MB in 4. The 12-group file reads 5.6 MB in 34 requests. Only the full-document lookup gains: 3.3 MB on the 3-group file and 4.7 MB on the 12-group file, against 5.9 MB. The multi-group files are also in tree order, and the 12-group one is written by pyarrow, so these tables do not isolate the row group count.
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

T2 groups by the direct parent id, `parents[-1]`. In a federated index that merges parents whose ids collide across catalogs; grouped by the full `parents` chain the registry has 790 groups, not 716. The same applies to the two tables below.

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

## Real polygons

Seven more shapes that use the `geometry` column against real polygons from the catalogs themselves, fetched over HTTPS inside the same query. The region for Berlin is the district Mitte from `alkis/bezirke`, 12 multipolygons in OGC:CRS84. The region for Madrid and for the registry is the neighbourhood Sol from `urbanismo/barrios-municipales` in the Madrid city catalog, 131 polygons in EPSG:25830, transformed to EPSG:4326 in the query. The region is the feature that contains the test point. G7 joins the index with every feature of the file.

```bash
uv run python scripts/run_suite.py <index URL> ... --only G --region-url <GeoParquet URL> --region-geom geometry --region-name namgem [--region-crs EPSG:25830]
```

What the three tables show:

- **Polygon predicates cost the same as point predicates.** `ST_Intersects`, `ST_Within`, `ST_Contains`, `ST_DWithin`, an intersection-area ranking, and a spatial join against 12 or 131 real polygons all finish in 0.3 to 0.9 s cold and 0.05 to 0.25 s warm. The extra bytes are the region file.
- **The counts say what the extents are.** In Berlin 370 of 371 extents intersect Mitte and 355 contain it whole, because most extents are city-wide. One lies inside it. In Madrid every extent contains the neighbourhood, because 1,960 of the 1,964 collections carry the whole-world bbox as a placeholder and the other 4 cover the region. The join with narrow extents finds nothing in the Comunidad de Madrid catalog and 20 collections per neighbourhood in the Madrid city catalog, all from `madrid-datos-abiertos`.
- **G5 is the query a catalog browser wants.** It ranks collections by the share of their extent that falls inside the region, which puts local datasets first.
- **No row group is skipped by geometry on these files.** The same `ST_Intersects` reads the same bytes for a point in Madrid, a point in the Pacific, and a box over Berlin, on the one-, three-, and twelve-row-group registry files. DuckDB pushes the predicate into the scan, but every row group holds global datasets, so its bbox statistics span the globe. The files with several row groups are in tree order, not spatial order, so this does not show whether a Hilbert-ordered file with several row groups would skip any; that layout was not built.

### Berlin Geoportal, region district Mitte

Index: `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet`  point 13.405,52.52  group `verkehr`  keyword `Radverkehr`  runs 3  region from `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/alkis/bezirke/alkis_bezirke_bezirksgrenzen.parquet`

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| G1 extents that intersect a box of about 5 x 3 km | 371 | 2 | 312.4KiB | 0.35, 0.36, 0.33 s | 0.35 s | 0.05 s |
| G2 extents that intersect the region polygon | 370 | 3 | 654.3KiB | 0.48, 0.53, 0.49 s | 0.49 s | 0.11 s |
| G3 extents that lie inside the region polygon | 1 | 3 | 654.3KiB | 0.50, 0.47, 0.46 s | 0.47 s | 0.12 s |
| G4 extents that contain the whole region polygon | 355 | 3 | 654.3KiB | 0.46, 0.52, 0.54 s | 0.52 s | 0.11 s |
| G5 ten most local datasets for the region: share of the extent that falls inside it | 10 | 3 | 654.3KiB | 0.61, 0.61, 0.66 s | 0.61 s | 0.25 s |
| G6 extents within 0.05 degrees of the point | 371 | 2 | 312.4KiB | 0.34, 0.32, 0.32 s | 0.32 s | 0.05 s |
| G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees | 5 | 3 | 654.3KiB | 0.46, 0.81, 0.51 s | 0.51 s | 0.11 s |

### Comunidad de Madrid, region neighbourhood Sol

Index: `https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3  region from `https://storage.googleapis.com/carto-open-catalogs/madrid-datos-abiertos/main/urbanismo/barrios-municipales/BARRIOS.parquet`

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| G1 extents that intersect a box of about 5 x 3 km | 1964 | 2 | 1.4MiB | 0.42, 0.41, 0.43 s | 0.42 s | 0.05 s |
| G2 extents that intersect the region polygon | 1964 | 3 | 1.6MiB | 0.53, 0.55, 0.54 s | 0.54 s | 0.12 s |
| G3 extents that lie inside the region polygon | 0 | 3 | 1.6MiB | 0.52, 0.56, 0.58 s | 0.56 s | 0.12 s |
| G4 extents that contain the whole region polygon | 1964 | 3 | 1.6MiB | 0.57, 0.54, 0.60 s | 0.57 s | 0.12 s |
| G5 ten most local datasets for the region: share of the extent that falls inside it | 10 | 3 | 1.6MiB | 0.59, 0.54, 0.56 s | 0.56 s | 0.14 s |
| G6 extents within 0.05 degrees of the point | 1964 | 2 | 1.4MiB | 0.40, 0.42, 0.40 s | 0.40 s | 0.06 s |
| G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees | 0 | 3 | 1.6MiB | 0.54, 0.57, 0.53 s | 0.54 s | 0.11 s |

### Portolan registry, region neighbourhood Sol

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3  region from `https://storage.googleapis.com/carto-open-catalogs/madrid-datos-abiertos/main/urbanismo/barrios-municipales/BARRIOS.parquet`

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Warm median |
|---|---|---|---|---|---|---|
| G1 extents that intersect a box of about 5 x 3 km | 2254 | 4 | 1001.5KiB | 0.50, 0.58, 0.60 s | 0.58 s | 0.05 s |
| G2 extents that intersect the region polygon | 2254 | 5 | 1.1MiB | 0.64, 0.68, 0.64 s | 0.64 s | 0.12 s |
| G3 extents that lie inside the region polygon | 0 | 5 | 1.1MiB | 0.92, 0.65, 0.66 s | 0.66 s | 0.12 s |
| G4 extents that contain the whole region polygon | 2254 | 5 | 1.1MiB | 0.90, 0.62, 0.69 s | 0.69 s | 0.13 s |
| G5 ten most local datasets for the region: share of the extent that falls inside it | 10 | 5 | 1.2MiB | 0.65, 0.66, 0.67 s | 0.66 s | 0.15 s |
| G6 extents within 0.05 degrees of the point | 2254 | 4 | 1001.5KiB | 0.49, 0.49, 0.51 s | 0.49 s | 0.05 s |
| G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees | 5 | 6 | 1.1MiB | 0.88, 0.94, 0.83 s | 0.88 s | 0.13 s |
