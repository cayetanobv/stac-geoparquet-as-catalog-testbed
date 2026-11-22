# Files

Every index file the pages measure, with its local copy and its URL. The local copies under `indexes/` are the files as measured. Any host that answers HTTP range requests reproduces the remote measurements with them.

The URLs are under `https://storage.googleapis.com/carto-open-catalogs/_testbed/`, a scratch prefix in the bucket that hosts the CARTO catalogs. `<base>` below stands for that prefix.

| Schema | Index | Local file under `indexes/` | URL |
|---|---|---|---|
| 1 | Berlin | `berlin-geoportal/collections.parquet` | `<base>/berlin-geoportal/collections.parquet` |
| 1 | Madrid | `comunidad-madrid-datos-abiertos/collections.parquet` | `<base>/comunidad-madrid/collections.parquet` |
| 1 | Registry, 1 row group | `portolan-registry/collections.parquet` | `<base>/registry/collections.parquet` |
| 1 | Registry, 3 row groups | `portolan-registry/collections-rg2048.parquet` | `<base>/registry/collections-rg2048.parquet` |
| 1 | Registry, 12 row groups | `portolan-registry/collections-pa512.parquet` | `<base>/registry/collections-pa512.parquet` |
| 1 | Registry, 3 row groups, Hilbert order | not committed, built by `benchmarks/row-groups/build_hilbert.sql` | `<base>/registry/collections-rg2048-hilbert.parquet` |
| 2 | Madrid | `comunidad-madrid-datos-abiertos/collections-links.parquet` | `<base>/comunidad-madrid/collections-links.parquet` |
| 3 | Madrid | `benchmarks/links-catalog-rows/collections-links-catalogs.parquet`, not committed | `<base>/comunidad-madrid/collections-links-catalogs.parquet` |
| 4 | each index | `*/collections-parents-struct.parquet` | `<base>/{berlin-geoportal,comunidad-madrid,registry}/collections-parents-struct.parquet` |
| 5 | each index | `*/collections-parent-hrefs.parquet` | `<base>/{berlin-geoportal,comunidad-madrid,registry}/collections-parent-hrefs.parquet` |
| 8 | each index | `*/collections-catalog-rows.parquet` | `<base>/{berlin-geoportal,comunidad-madrid,registry}/collections-catalog-rows.parquet` |
| 9 | each index | `*/collections-decomposed.parquet` | `<base>/{berlin-geoportal,comunidad-madrid,registry}/collections-decomposed.parquet` |
| 9, with search columns | each index | `*/collections-decomposed-search.parquet` | `<base>/{berlin-geoportal,comunidad-madrid,registry}/collections-decomposed-search.parquet` |
| 9, with `#id=` links | Berlin and Madrid | `*/collections-decomposed-fragments.parquet` | `<base>/{berlin-geoportal,comunidad-madrid}/collections-decomposed-fragments.parquet` |

## The files that pages 01 to 06 read

Pages 01 to 06 read the Berlin and Madrid files of schemas 1 and 2 beside their catalogs, at `carto-open-catalogs/<catalog>/main/collections.parquet` and `collections-links.parquet`. Since 2026-11-05 the CARTO publication pipeline writes its own `collections.parquet` at that path, in schema 8, with a `rel: "data"` link from the root `catalog.json`. So those URLs no longer serve the measured files. The copies under `_testbed/` in the table above have the same bytes as the measured files.

The real-polygon queries on page 04 also read two boundary files that the catalogs publish, under `https://storage.googleapis.com/carto-open-catalogs/`:

- Berlin districts: `berlin-geoportal/main/alkis/bezirke/alkis_bezirke_bezirksgrenzen.parquet`
- Madrid neighbourhoods: `madrid-datos-abiertos/main/urbanismo/barrios-municipales/BARRIOS.parquet`

## Upload your own copy

Use any tool that sets the content type `application/vnd.apache.parquet`:

```bash
gsutil -h "Content-Type:application/vnd.apache.parquet" cp indexes/berlin-geoportal/collections-catalog-rows.parquet gs://<bucket>/<prefix>/collections.parquet
```
