# Results

Read in order. Pages 1 to 4 measure the index against real catalogs over HTTPS. Pages 5 to 7 compare designs for the tree column, on real data and on synthetic files. Pages 8 and 9 follow up on questions raised by the first pages and by the spec discussion. [docs/method.md](../docs/method.md) explains the question and the measurement setup.

| Page | What it measures | Data |
|---|---|---|
| [01 Berlin Geoportal](01-berlin-geoportal.md) | JSON walk against index, one city catalog of depth 2 | 371 collections |
| [02 Comunidad de Madrid](02-comunidad-madrid.md) | Same, a catalog of depth 3 with the mid-tree case | 1,964 collections |
| [03 Portolan registry](03-portolan-registry.md) | One federated index over 86 catalogs: id collisions, antimeridian, row group layout | 5,852 collections |
| [04 Query suite](04-query-suite.md) | Sixteen query shapes over five index files, plus seven with real polygons from the catalogs | all of the above |
| [05 Tree designs](05-tree-designs.md) | `parents` list against path string, level columns, recursive query | synthetic, 5 million rows |
| [06 Links-only variant](06-links-only-variant.md) | The Madrid index with STAC `links` instead of `parents` | 1,964 collections |
| [07 List shapes](07-list-shapes.md) | How DuckDB filters a flat column, a list of strings, and a list of structs | synthetic, 5 million rows |
| [08 Follow-up checks](08-follow-up-checks.md) | A links file with catalog rows, and row groups with the Hilbert order kept | 2,141 rows, 5,852 rows |
| [09 Ancestor hrefs](09-parent-hrefs.md) | The three indexes with each ancestor's href, as a list of structs and as a second list | 371 to 5,852 rows |

Every remote measurement reads the files listed under [Upload](../README.md#3-upload) in the README.
