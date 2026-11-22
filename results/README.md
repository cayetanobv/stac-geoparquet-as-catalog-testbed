# Results

One page per measurement, in the order they were made. Each page records what was measured at the time, and the schema numbers refer to [docs/schema.md](../docs/schema.md). To read the current state first, read pages 10 and 11. [docs/method.md](../docs/method.md) explains how the times are measured, and [docs/files.md](../docs/files.md) lists the files.

| Page | What it measures | Schema | Data |
|---|---|---|---|
| [01 Berlin Geoportal](01-berlin-geoportal.md) | JSON walk against one query on the file, a catalog of depth 2 | 1 | 371 collections |
| [02 Comunidad de Madrid](02-comunidad-madrid.md) | The same, on a catalog of depth 3, where a topic sits in the middle of the tree | 1 | 1,964 collections |
| [03 Portolan registry](03-portolan-registry.md) | One federated file of 86 catalogs: repeated ids, antimeridian boxes, row groups | 1 | 5,852 collections |
| [04 Query suite](04-query-suite.md) | Sixteen query shapes, plus seven with real polygons from the catalogs | 1 | all of the above |
| [05 Tree designs](05-tree-designs.md) | `parents` against a path string, level columns and a recursive query | 6 | synthetic, 5 million rows |
| [06 Links-only variant](06-links-only-variant.md) | STAC `links` instead of `parents` | 2 | 1,964 collections |
| [07 List shapes](07-list-shapes.md) | How DuckDB filters a flat column, a list of strings and a list of structs | 7 | synthetic, 5 million rows |
| [08 Follow-up checks](08-follow-up-checks.md) | Links with catalog rows, and row groups in Hilbert order | 3, 1 | 2,141 rows, 5,852 rows |
| [09 Ancestor hrefs](09-parent-hrefs.md) | Each ancestor's href, as a list of structs and as a second list | 4, 5 | 371 to 5,852 rows |
| [10 Catalog and collection rows](10-catalog-and-collection-rows.md) | The shape agreed in stac-geoparquet-spec#17: same answers as schema 4, size on disk and in memory | 8 | 408 to 6,725 rows |
| [11 Decomposed columns](11-decomposed-columns.md) | One column per STAC field against schema 8: round trip, size, times over HTTPS, `#id=` links | 9, 8 | 408 to 6,725 rows |

Pages 01 to 06 read the Berlin and Madrid files at their catalogs' URLs. Those URLs now serve the CARTO pipeline's file. [docs/files.md](../docs/files.md) gives copies with the same bytes.
