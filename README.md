# HomeScout

HomeScout finds single-family homes that are likely to come to market: long-tenure owners, senior exemption signals, and trusts or estates. It uses free public records only. The working county is Westchester County, New York. The schema and the pipeline adapter are meant to take another county without renaming tables.

The committed dataset is the app extract: **65,011** homes, gzipped at about 9 MB in `data/app/westchester_sf_app_dataset.csv.gz`. It is the 20-year owners (including senior-signal rows whose deed book is unknown) plus every trust, estate, and life estate. The full class-210 roll is about 164,000 parcels and is not in git.

## Layout

```
pipeline/     ingest, tenure, enrichment, and one adapter per county
app/          single-file MapLibre (mobile) and Leaflet (desktop) builds
db/           PostGIS migrations, CSV loader, SQLite and GeoParquet export
docs/         sources, methods, caveats, schema, adding a county
data/app/     committed Westchester extract
```

Raw GIS, the USGS DEM, and OpenStreetMap PBF files are gitignored. See `data/README.md`.

## Run it

PostgreSQL 16 and PostGIS 3. `docker compose up -d` starts them with user `homescout`, password `homescout`, database `homescout`. The same URL is the default in `.env.example`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # optional; the default URL matches compose
docker compose up -d
python -m db.migrate
python -m db.load_csv         # data/app/westchester_sf_app_dataset.csv.gz
python -m db.export           # sqlite, geoparquet, csv under data/out/westchester_ny/
python -m app.build_mobile --source db
python -m app.build_app --source db
```

Open `dist/westchester_homes_mobile.html` in a current browser. The file is self-contained. Map tiles need a network connection. School-district outlines and Metro-North station dots are empty until you add overlay files (below). Station name and distance on each home are already in the extract.

Build from the CSV, or from an export, without going back through Postgres:

```bash
python -m app.build_mobile --source csv
python -m app.build_mobile --source parquet --input data/out/westchester_ny/app_homes.parquet
python -m app.build_mobile --source sqlite --input data/out/westchester_ny/app_homes.sqlite
```

Paths come from the repository root, or from `HOMESCOUT_DATA_DIR`, `HOMESCOUT_DIST_DIR`, and `DATABASE_URL`. The county is `HOMESCOUT_REGION` (default `westchester_ny`).

## Rebuild Westchester from the public sources

Enrichment needs pandas plus the optional extra: `pip install -e ".[enrich]"`. Put downloads in `data/raw/westchester_ny/` and `data/enrich/westchester_ny/`. The order is in [docs/adding-a-county.md](docs/adding-a-county.md). Short version:

```bash
python -m pipeline.ingest.fetch_gis
python -m pipeline.ingest.fetch_orpts
python -m pipeline.build_tenure
python -m pipeline.ingest.fetch_centroids
python -m pipeline.ingest.fetch_nfhl
python -m pipeline.ingest.fetch_dem
python -m pipeline.enrich.osm_extract
python -m pipeline.enrich.enrich
python -m pipeline.enrich.merge
python -m pipeline.enrich.owner_type
python -m pipeline.enrich.prior_tenure
python -m pipeline.enrich.app_dataset
```

`python -m pipeline.enrich.build_overlays` writes `data/overlays/westchester_ny/school_districts.geojson` and `metro_north.csv`. The next mobile build embeds them.

## Read this before trusting a row

- [Sources](docs/sources.md) — the public datasets and what each one contributes.
- [Methods](docs/methods.md) — deed-book dates, exemptions, walk proxy, flood, sun, price.
- [Caveats](docs/caveats.md) — last deed is not last sale, senior means an exemption, price is not an appraisal, permits are empty.
- [Schema](docs/schema.md) — tables, the natural key, and the `app_homes` view.
- [Adding a county](docs/adding-a-county.md) — adapter interface. Do not reuse Westchester’s deed-book formula unless you have checked it.

## Tests

```bash
pytest
```

The loader test needs the database from the steps above. It reloads the Westchester extract, checks the natural key, a known parcel, PostGIS distance, and that `app_homes` matches the CSV. Unit tests cover deed-book decoding, owner-type patterns, and the HTML column encoder. The original Playwright checks are in `app/manual/` and are not part of `pytest`.
