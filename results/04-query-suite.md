# Query suite

Sixteen query shapes against each index over HTTPS, three cold runs each in a fresh DuckDB process and three warm runs in one process after a first run. Measured on 2026-10-26 with DuckDB 2.0.0 and Python 3.14.9, from the test machine described in [docs/method.md](../docs/method.md). Requests count one HEAD plus the range GETs. Bytes are what the query read from the file.

Cold time is given twice. "Cold, each run" and "Cold median" are the `EXPLAIN ANALYZE` total, which leaves out reads made while planning. "Cold wall median" is the wall clock of the plain query in a separate fresh process, timed after the extensions load, so it includes planning and leaves out process start.

D1 on Madrid and the registry looks up `demografia/a-c/adquisiciones-de-nacionalidad-espanola-por-sexo-y-grupo-de-edad`. The id used on 2026-10-23 was not recorded, so this one was chosen for the rerun; any single id reads the same column chunk.

Runner: `scripts/run_suite.py`. Rerun any table with the command under its heading, or point the runner at another index.

```bash
uv run python scripts/run_suite.py <index URL> --lon <x> --lat <y> --grp <group id> --kw <keyword> --cat <root id> --id <collection id> --runs 3
```

## What the five tables show

- **On a file of a few megabytes, DuckDB 2.0 reads the whole file in one request, whatever the query.** Every Berlin query reads 312 KB and every Madrid query reads 1.4 MB. The prefetch cost model coalesces the byte ranges a query needs when the gaps between them are small, and on these files that is everything. Cold time is then one handshake plus one request: wall-clock medians of 0.22 to 0.42 s on Berlin and 0.53 to 0.61 s on Madrid, S3 included.
- **On the 6.5 MB registry file the bytes follow the columns named.** A count on `license` reads 21 KB, a title search 110 KB, a keyword search 490 KB, the `parents` filter 1.0 MB, and one `original` document 5.9 MB. Requests stay at three to seven.
- **Warm queries cost 0.02 to 0.14 s whatever the question.** They are cache hits: after the first run DuckDB holds the file, sends one HEAD request to check it, and reads no data. They show what a repeated query costs in one session, not what a new question costs a new client.
- **A box test on the `bbox` struct can finish without a scan.** When every row group's statistics prove the filter true, DuckDB answers from the footer and the planner removes the scan. It reads the file while planning, outside the time `EXPLAIN ANALYZE` reports, which is why S3 shows 0.00 s on Berlin and Madrid. The wall clock gives its real cost, 0.23 s on Berlin and 0.59 s on Madrid, the same as the other queries. The registry file needs a scan because its statistics span the globe.
- **More row groups mean more requests and more bytes under DuckDB 2.0.** The 3-group file reads 2.8 MB in 8 requests for the point query that the 1-group file answers with 1.0 MB in 4. The 12-group file reads 5.6 MB in 33 requests. Only the full-document lookup gains: 3.3 MB in 0.93 s on the 3-group file and 4.7 MB in 1.03 s on the 12-group file, against 5.9 MB in 1.41 s. The request counts on the 12-group file move by a few between runs on different days, since DuckDB issues its range reads in parallel. The multi-group files are also in tree order, and the 12-group one is written by pyarrow, so these tables do not isolate the row group count.
- **Counts agree with the JSON walk.** S1 gives 367, 1,964, and 2,254. The walk gives 367 and 1,964 on the two cities. On the registry it gives 2,251, because one catalog, root id `bot-portolan-catalog` at `data.back-on-track.eu/bot-open-data/`, no longer serves its `catalog.json` and its 3 collections are missing from the walk; the index was built from the mirror of 2026-10-22, when it did. See [page 03](03-portolan-registry.md).

Under DuckDB 1.5.6, measured on 2026-10-23 before the toolchain was pinned, the same suite read 16 to 30 KB per query on Berlin in three to five requests, and the 3-group registry file cut the one-document lookup fivefold with no cost elsewhere. The engine's prefetch strategy, not the file, changed those two results.


## Berlin Geoportal, 371 rows, 312 KB, 1 row group

Index: `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet`  point 13.405,52.52  group `verkehr`  keyword `Radverkehr`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 367 | 2 | 312.4KiB | 0.45, 0.43, 0.28 s | 0.43 s | 0.28 s | 0.02 s |
| S2 point in extent, under one group | 19 | 2 | 312.4KiB | 0.35, 0.25, 0.41 s | 0.35 s | 0.39 s | 0.06 s |
| S3 box intersects extent, bbox struct only | 371 | 2 | 312.4KiB | 0.00, 0.00, 0.00 s | 0.00 s | 0.23 s | 0.00 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 14 | 2 | 312.4KiB | 0.27, 0.43, 0.39 s | 0.39 s | 0.26 s | 0.07 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 2 | 312.4KiB | 0.43, 0.35, 0.40 s | 0.40 s | 0.22 s | 0.02 s |
| T1 everything under one group, id and title | 19 | 2 | 312.4KiB | 0.38, 0.24, 0.35 s | 0.35 s | 0.36 s | 0.06 s |
| T2 collections per direct parent | 36 | 2 | 312.4KiB | 0.48, 0.44, 0.42 s | 0.44 s | 0.23 s | 0.06 s |
| T3 one catalog by root id, one group | 19 | 2 | 312.4KiB | 0.23, 0.41, 0.43 s | 0.41 s | 0.42 s | 0.02 s |
| A1 keyword equality | 4 | 2 | 312.4KiB | 0.24, 0.40, 0.50 s | 0.40 s | 0.24 s | 0.06 s |
| A2 title substring, case-insensitive | 4 | 2 | 312.4KiB | 0.40, 0.38, 0.40 s | 0.40 s | 0.40 s | 0.02 s |
| A3 description substring | 7 | 2 | 312.4KiB | 0.23, 0.42, 0.41 s | 0.41 s | 0.37 s | 0.06 s |
| A4 license equality | 1 | 2 | 312.4KiB | 0.42, 0.24, 0.41 s | 0.41 s | 0.40 s | 0.03 s |
| A5 temporal: end open or after 2024 | 370 | 2 | 312.4KiB | 0.42, 0.23, 0.25 s | 0.25 s | 0.39 s | 0.07 s |
| D1 one full document by catalog and id | 1 | 2 | 312.4KiB | 0.23, 0.24, 0.40 s | 0.24 s | 0.40 s | 0.06 s |
| D2 field inside the JSON document for a group: providers | 19 | 2 | 312.4KiB | 0.41, 0.38, 0.28 s | 0.38 s | 0.27 s | 0.06 s |
| C1 combined: group, point, keyword, title returned | 3 | 2 | 312.4KiB | 0.49, 0.26, 0.40 s | 0.40 s | 0.40 s | 0.03 s |

C1 uses the keyword `Radverkehr`, which occurs inside the group.

## Comunidad de Madrid, 1,964 rows, 1.5 MB, 1 row group

Index: `https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 1964 | 2 | 1.4MiB | 0.61, 0.52, 0.58 s | 0.58 s | 0.59 s | 0.06 s |
| S2 point in extent, under one group | 146 | 2 | 1.4MiB | 0.59, 0.57, 0.60 s | 0.59 s | 0.60 s | 0.06 s |
| S3 box intersects extent, bbox struct only | 1964 | 2 | 1.4MiB | 0.00, 0.00, 0.00 s | 0.00 s | 0.59 s | 0.00 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 0 | 2 | 1.4MiB | 0.60, 0.65, 0.66 s | 0.65 s | 0.59 s | 0.09 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 2 | 1.4MiB | 0.55, 0.59, 0.55 s | 0.55 s | 0.61 s | 0.06 s |
| T1 everything under one group, id and title | 146 | 2 | 1.4MiB | 0.55, 0.57, 0.57 s | 0.57 s | 0.56 s | 0.06 s |
| T2 collections per direct parent | 159 | 2 | 1.4MiB | 0.56, 0.55, 0.55 s | 0.55 s | 0.57 s | 0.07 s |
| T3 one catalog by root id, one group | 146 | 2 | 1.4MiB | 0.58, 0.69, 0.60 s | 0.60 s | 0.56 s | 0.06 s |
| A1 keyword equality | 261 | 2 | 1.4MiB | 0.59, 0.56, 0.57 s | 0.57 s | 0.59 s | 0.07 s |
| A2 title substring, case-insensitive | 49 | 2 | 1.4MiB | 0.55, 0.56, 0.54 s | 0.55 s | 0.57 s | 0.06 s |
| A3 description substring | 119 | 2 | 1.4MiB | 0.55, 0.55, 0.59 s | 0.55 s | 0.54 s | 0.06 s |
| A4 license equality | 1 | 2 | 1.4MiB | 0.52, 0.57, 0.52 s | 0.52 s | 0.55 s | 0.05 s |
| A5 temporal: end open or after 2024 | 1964 | 2 | 1.4MiB | 0.52, 0.55, 0.65 s | 0.55 s | 0.54 s | 0.06 s |
| D1 one full document by catalog and id | 1 | 2 | 1.4MiB | 0.54, 0.53, 0.59 s | 0.54 s | 0.61 s | 0.07 s |
| D2 field inside the JSON document for a group: providers | 20 | 2 | 1.4MiB | 0.55, 0.55, 0.54 s | 0.55 s | 0.53 s | 0.07 s |
| C1 combined: group, point, keyword, title returned | 42 | 2 | 1.4MiB | 0.55, 0.55, 0.60 s | 0.55 s | 0.55 s | 0.08 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 6.5 MB, 1 row group, Hilbert order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 4 | 1001.5KiB | 0.62, 0.60, 0.70 s | 0.62 s | 0.68 s | 0.07 s |
| S2 point in extent, under one group | 150 | 4 | 997.5KiB | 0.67, 0.72, 0.65 s | 0.67 s | 0.64 s | 0.06 s |
| S3 box intersects extent, bbox struct only | 2254 | 4 | 109.5KiB | 0.50, 0.44, 0.47 s | 0.47 s | 0.46 s | 0.07 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 5 | 1.0MiB | 0.78, 0.71, 0.72 s | 0.72 s | 0.70 s | 0.07 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 6 | 1.1MiB | 0.87, 0.88, 0.83 s | 0.87 s | 0.86 s | 0.07 s |
| T1 everything under one group, id and title | 162 | 5 | 1.1MiB | 0.79, 0.73, 0.76 s | 0.76 s | 0.78 s | 0.06 s |
| T2 collections per direct parent | 790 | 4 | 997.5KiB | 0.77, 0.62, 0.63 s | 0.63 s | 0.72 s | 0.06 s |
| T3 one catalog by root id, one group | 146 | 4 | 997.5KiB | 0.61, 0.58, 0.62 s | 0.61 s | 0.64 s | 0.06 s |
| A1 keyword equality | 261 | 4 | 489.5KiB | 0.56, 0.66, 0.60 s | 0.60 s | 0.61 s | 0.07 s |
| A2 title substring, case-insensitive | 50 | 3 | 109.5KiB | 0.52, 0.40, 0.42 s | 0.42 s | 0.44 s | 0.08 s |
| A3 description substring | 186 | 3 | 461.5KiB | 0.54, 0.54, 0.51 s | 0.54 s | 0.52 s | 0.06 s |
| A4 license equality | 3 | 3 | 21.5KiB | 0.32, 0.38, 0.33 s | 0.33 s | 0.33 s | 0.08 s |
| A5 temporal: end open or after 2024 | 5671 | 3 | 25.5KiB | 0.39, 0.32, 0.48 s | 0.39 s | 0.33 s | 0.06 s |
| D1 one full document by catalog and id | 1 | 7 | 5.9MiB | 1.54, 1.41, 1.16 s | 1.41 s | 1.24 s | 0.10 s |
| D2 field inside the JSON document for a group: providers | 20 | 7 | 5.9MiB | 1.43, 1.40, 1.48 s | 1.43 s | 1.19 s | 0.11 s |
| C1 combined: group, point, keyword, title returned | 42 | 7 | 1.6MiB | 1.06, 0.93, 0.93 s | 0.93 s | 1.09 s | 0.09 s |

C1 uses the keyword `Total`, which occurs inside the group.

T2 groups by the full `parents` chain, so parents whose ids collide across catalogs stay apart: 790 groups on the registry. The tables of 2026-10-23 grouped by `parents[-1]` and showed 716.

## Portolan registry, 5,852 rows, 5.8 MB, 3 row groups of 2,048 rows, tree order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-rg2048.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 8 | 2.8MiB | 1.12, 0.92, 1.11 s | 1.11 s | 1.03 s | 0.08 s |
| S2 point in extent, under one group | 150 | 8 | 2.8MiB | 0.96, 0.90, 0.84 s | 0.90 s | 0.98 s | 0.06 s |
| S3 box intersects extent, bbox struct only | 2254 | 5 | 116.5KiB | 0.47, 0.48, 0.48 s | 0.48 s | 0.51 s | 0.06 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 8 | 2.9MiB | 0.88, 0.86, 0.83 s | 0.86 s | 0.91 s | 0.08 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 12 | 2.9MiB | 1.00, 0.99, 1.05 s | 1.00 s | 1.00 s | 0.07 s |
| T1 everything under one group, id and title | 162 | 11 | 3.0MiB | 0.90, 0.95, 0.88 s | 0.90 s | 0.86 s | 0.06 s |
| T2 collections per direct parent | 790 | 8 | 2.8MiB | 0.83, 0.90, 0.81 s | 0.83 s | 1.04 s | 0.06 s |
| T3 one catalog by root id, one group | 146 | 8 | 2.8MiB | 0.88, 0.86, 0.83 s | 0.86 s | 0.84 s | 0.06 s |
| A1 keyword equality | 261 | 8 | 1.9MiB | 0.74, 0.71, 0.73 s | 0.73 s | 0.78 s | 0.07 s |
| A2 title substring, case-insensitive | 50 | 5 | 116.5KiB | 0.45, 0.46, 0.48 s | 0.46 s | 0.47 s | 0.06 s |
| A3 description substring | 186 | 5 | 464.5KiB | 0.67, 0.64, 0.63 s | 0.64 s | 0.53 s | 0.06 s |
| A4 license equality | 3 | 5 | 28.5KiB | 0.42, 0.42, 0.44 s | 0.42 s | 0.42 s | 0.05 s |
| A5 temporal: end open or after 2024 | 5671 | 5 | 28.5KiB | 0.47, 0.44, 0.41 s | 0.44 s | 0.43 s | 0.05 s |
| D1 one full document by catalog and id | 1 | 9 | 3.3MiB | 0.87, 1.04, 0.93 s | 0.93 s | 0.95 s | 0.08 s |
| D2 field inside the JSON document for a group: providers | 20 | 12 | 5.3MiB | 1.03, 1.05, 2.97 s | 1.05 s | 1.25 s | 0.08 s |
| C1 combined: group, point, keyword, title returned | 42 | 11 | 2.2MiB | 0.91, 0.99, 0.94 s | 0.94 s | 0.88 s | 0.06 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Portolan registry, 5,852 rows, 6.1 MB, 12 row groups of 512 rows, tree order

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections-pa512.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| S1 point in extent, whole file | 2254 | 33 | 5.6MiB | 1.32, 1.21, 1.15 s | 1.21 s | 1.24 s | 0.06 s |
| S2 point in extent, under one group | 150 | 32 | 5.6MiB | 1.76, 1.28, 1.24 s | 1.28 s | 1.22 s | 0.06 s |
| S3 box intersects extent, bbox struct only | 2254 | 14 | 193.3KiB | 0.74, 0.54, 1.35 s | 0.74 s | 0.58 s | 0.06 s |
| S4 local datasets: extent narrower than 0.3 degrees containing the point | 20 | 30 | 5.7MiB | 1.17, 1.24, 1.31 s | 1.24 s | 1.12 s | 0.06 s |
| S5 nearest 10 collections to the point by extent centre, with title | 10 | 32 | 5.6MiB | 1.19, 1.35, 1.19 s | 1.19 s | 1.29 s | 0.06 s |
| T1 everything under one group, id and title | 162 | 43 | 5.7MiB | 1.25, 1.19, 1.22 s | 1.22 s | 1.31 s | 0.06 s |
| T2 collections per direct parent | 790 | 30 | 5.6MiB | 1.34, 1.24, 1.61 s | 1.34 s | 1.76 s | 0.14 s |
| T3 one catalog by root id, one group | 146 | 32 | 5.6MiB | 3.77, 1.49, 1.53 s | 1.53 s | 1.56 s | 0.08 s |
| A1 keyword equality | 261 | 29 | 5.1MiB | 2.10, 1.26, 5.22 s | 2.10 s | 1.24 s | 0.06 s |
| A2 title substring, case-insensitive | 50 | 15 | 209.3KiB | 0.94, 0.60, 0.56 s | 0.60 s | 0.61 s | 0.08 s |
| A3 description substring | 186 | 15 | 585.3KiB | 0.61, 0.60, 0.63 s | 0.61 s | 0.62 s | 0.06 s |
| A4 license equality | 3 | 15 | 109.3KiB | 3.14, 1.14, 0.81 s | 1.14 s | 0.57 s | 0.08 s |
| A5 temporal: end open or after 2024 | 5671 | 15 | 113.3KiB | 0.58, 0.51, 0.54 s | 0.54 s | 0.58 s | 0.05 s |
| D1 one full document by catalog and id | 1 | 20 | 4.7MiB | 1.03, 0.97, 1.12 s | 1.03 s | 1.01 s | 0.07 s |
| D2 field inside the JSON document for a group: providers | 20 | 41 | 6.8MiB | 1.51, 1.49, 1.28 s | 1.49 s | 1.44 s | 0.07 s |
| C1 combined: group, point, keyword, title returned | 42 | 30 | 2.4MiB | 1.11, 1.01, 1.28 s | 1.11 s | 1.05 s | 0.06 s |

C1 uses the keyword `Total`, which occurs inside the group.

## Real polygons

Seven more shapes that use the `geometry` column against real polygons from the catalogs themselves, fetched over HTTPS inside the same query. The region for Berlin is the district Mitte from `alkis/bezirke`, 12 multipolygons in OGC:CRS84. The region for Madrid and for the registry is the neighbourhood Sol from `urbanismo/barrios-municipales` in the Madrid city catalog, 131 polygons in EPSG:25830, transformed to EPSG:4326 in the query. The region is the feature that contains the test point. G7 joins the index with every feature of the file.

```bash
uv run python scripts/run_suite.py <index URL> ... --only G --region-url <GeoParquet URL> --region-geom <geometry column> --region-name <name column> [--region-crs EPSG:25830]
```

Berlin uses `--region-geom geometry --region-name namgem`. Madrid uses `--region-geom geom --region-name NOMBRE --region-crs EPSG:25830`. G7 on Madrid and the registry was run again at 09:42 UTC, a minute after the rest of the run, because the first attempt passed a name column that the Madrid file does not have.

What the three tables show:

- **Polygon predicates cost the same as point predicates.** `ST_Intersects`, `ST_Within`, `ST_Contains`, `ST_DWithin`, an intersection-area ranking, and a spatial join against 12 or 131 real polygons all finish in 0.2 to 1.0 s cold and 0.05 to 0.34 s warm. The extra bytes are the region file.
- **The counts say what the extents are.** In Berlin 370 of 371 extents intersect Mitte and 355 contain it whole, because most extents are city-wide. One lies inside it. In Madrid every extent contains the neighbourhood, because 1,960 of the 1,964 collections carry the whole-world bbox as a placeholder and the other 4 cover the region. The join with narrow extents finds nothing in the Comunidad de Madrid catalog and 20 collections per neighbourhood in the Madrid city catalog, all from `madrid-datos-abiertos`.
- **G5 is the query a catalog browser wants.** It ranks collections by the share of their extent that falls inside the region, which puts local datasets first.
- **No row group is skipped by geometry on these files.** The same `ST_Intersects` reads the same bytes for a point in Madrid, a point in the Pacific, and a box over Berlin, on the one-, three-, and twelve-row-group registry files. DuckDB pushes the predicate into the scan, but every row group holds global datasets, so its bbox statistics span the globe. The files with several row groups are in tree order, not spatial order, so this does not show whether a Hilbert-ordered file with several row groups would skip any; that layout was not built.

### Berlin Geoportal, region district Mitte

Index: `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet`  point 13.405,52.52  group `verkehr`  keyword `Radverkehr`  runs 3  region from `https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/alkis/bezirke/alkis_bezirke_bezirksgrenzen.parquet`

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| G1 extents that intersect a box of about 5 x 3 km | 371 | 2 | 312.4KiB | 0.44, 0.22, 0.22 s | 0.22 s | 0.22 s | 0.05 s |
| G2 extents that intersect the region polygon | 370 | 3 | 654.3KiB | 0.59, 0.73, 0.67 s | 0.67 s | 0.55 s | 0.12 s |
| G3 extents that lie inside the region polygon | 1 | 3 | 654.3KiB | 0.63, 0.58, 0.57 s | 0.58 s | 0.57 s | 0.11 s |
| G4 extents that contain the whole region polygon | 355 | 3 | 654.3KiB | 0.54, 0.72, 0.72 s | 0.72 s | 0.67 s | 0.17 s |
| G5 ten most local datasets for the region: share of the extent that falls inside it | 10 | 3 | 654.3KiB | 0.65, 0.69, 0.65 s | 0.65 s | 0.69 s | 0.34 s |
| G6 extents within 0.05 degrees of the point | 371 | 2 | 312.4KiB | 0.24, 0.24, 0.40 s | 0.24 s | 0.41 s | 0.07 s |
| G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees | 5 | 3 | 654.3KiB | 0.55, 0.53, 0.66 s | 0.55 s | 0.72 s | 0.12 s |

### Comunidad de Madrid, region neighbourhood Sol

Index: `https://storage.googleapis.com/carto-open-catalogs/comunidad-madrid-datos-abiertos/main/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3  region from `https://storage.googleapis.com/carto-open-catalogs/madrid-datos-abiertos/main/urbanismo/barrios-municipales/BARRIOS.parquet`

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| G1 extents that intersect a box of about 5 x 3 km | 1964 | 2 | 1.4MiB | 0.51, 0.56, 0.53 s | 0.53 s | 0.58 s | 0.08 s |
| G2 extents that intersect the region polygon | 1964 | 3 | 1.6MiB | 1.02, 0.84, 0.81 s | 0.84 s | 0.76 s | 0.16 s |
| G3 extents that lie inside the region polygon | 0 | 3 | 1.6MiB | 0.68, 0.71, 0.85 s | 0.71 s | 0.85 s | 0.13 s |
| G4 extents that contain the whole region polygon | 1964 | 3 | 1.6MiB | 0.85, 0.83, 0.74 s | 0.83 s | 0.80 s | 0.13 s |
| G5 ten most local datasets for the region: share of the extent that falls inside it | 10 | 3 | 1.6MiB | 0.71, 0.69, 0.81 s | 0.71 s | 0.77 s | 0.16 s |
| G6 extents within 0.05 degrees of the point | 1964 | 2 | 1.4MiB | 0.53, 0.54, 0.55 s | 0.54 s | 0.63 s | 0.06 s |
| G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees | 0 | 3 | 1.6MiB | 0.85, 0.94, 0.76 s | 0.85 s | 0.90 s | 0.12 s |

### Portolan registry, region neighbourhood Sol

Index: `https://storage.googleapis.com/carto-open-catalogs/_testbed/registry/collections.parquet`  point -3.7038,40.4168  group `demografia`  keyword `Total`  runs 3  region from `https://storage.googleapis.com/carto-open-catalogs/madrid-datos-abiertos/main/urbanismo/barrios-municipales/BARRIOS.parquet`

| Query | Result (count or rows) | Requests | Bytes read | Cold, each run | Cold median | Cold wall median | Warm median |
|---|---|---|---|---|---|---|---|
| G1 extents that intersect a box of about 5 x 3 km | 2254 | 4 | 1001.5KiB | 0.65, 0.57, 1.62 s | 0.65 s | 0.65 s | 0.06 s |
| G2 extents that intersect the region polygon | 2254 | 5 | 1.1MiB | 0.75, 0.92, 0.83 s | 0.83 s | 0.83 s | 0.13 s |
| G3 extents that lie inside the region polygon | 0 | 5 | 1.1MiB | 0.93, 0.76, 0.89 s | 0.89 s | 0.94 s | 0.18 s |
| G4 extents that contain the whole region polygon | 2254 | 5 | 1.1MiB | 0.93, 0.74, 0.77 s | 0.77 s | 0.91 s | 0.19 s |
| G5 ten most local datasets for the region: share of the extent that falls inside it | 10 | 5 | 1.2MiB | 0.97, 1.08, 0.95 s | 0.97 s | 0.81 s | 0.21 s |
| G6 extents within 0.05 degrees of the point | 2254 | 4 | 1001.5KiB | 0.67, 0.72, 0.65 s | 0.67 s | 0.65 s | 0.07 s |
| G7 spatial join with every feature of the file: collections per feature, extents narrower than 0.3 degrees | 5 | 6 | 1.1MiB | 1.11, 0.98, 1.00 s | 1.00 s | 1.03 s | 0.16 s |
