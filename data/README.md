# Data layout

| Path | In git | What it is |
| --- | --- | --- |
| `data/app/westchester_sf_app_dataset.csv.gz` | yes | Prototype app extract, 65,011 single-family homes. About 9 MB compressed. |
| `data/raw/<region>/` | no | GIS attributes, assessment roll, prior-year owner files. |
| `data/enrich/<region>/` | no | Centroids, DEM, NFHL, OSM PBF, POIs, ratios, enrichment outputs. |
| `data/out/<region>/` | no | Tenure files, enriched extracts, SQLite and GeoParquet exports. |
| `data/overlays/<region>/` | no | Optional school-district GeoJSON and Metro-North station CSV for the mobile map. |

Raw GIS, the USGS DEM, and Geofabrik `.osm.pbf` files are too large for this repository. Rebuild them with the ingest scripts, or load the committed extract directly.
