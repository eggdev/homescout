# Database

PostgreSQL 16 with PostGIS 3. Migrations are `db/migrations/*.sql`, applied by `python -m db.migrate`. The loader is idempotent per region: it deletes that region’s parcels (children cascade) and inserts the CSV again.

## Keys

`regions` is one row per county (`state_fips`, `county_fips`). Westchester is `36` / `119`.

`parcels` is unique on `(state_fips, county_fips, swis, print_key)`. `centroid` is a generated point from `lat`/`lon`. `geom` is reserved for the parcel polygon and is null in the current extract.

`municipalities` is one row per SWIS inside a region. `city_town` is the assessing town or city. `municipality` is the village when the roll distinguishes one (Croton-on-Hudson inside Cortlandt, for example).

## Per roll year

These tables use `(parcel_id, roll_year)`. The Westchester extract is roll year 2025.

- `parcel_owners` — name, mailing address, occupancy flags, `owner_type_code`
- `deeds` — book, page, estimated recording date, tenure status, basis
- `parcel_exemptions` — the code string as published, plus senior/STAR/veteran flags
- `exemption_codes` — one row per code, for queries like “who has 4183”
- `assessments` — market value, living area, beds, baths, lot size, style, roll school-district name

`owner_types` is a small lookup. Trust and estate labels are flagged `is_trust_or_estate`.

## Enrichment

- `school_districts` and `parcel_schools` — TIGER GEOID and name, plus the roll name
- `nri_tracts` and `parcel_nri` — tract scores stored once
- `parcel_flood`, `parcel_walkability`, `parcel_terrain`
- `price_estimates` — `method` (the sentence stored on the extract) and `method_version`. Partial unique index: one `is_current` row per parcel
- `prior_tenure` — pre-trust owner and family-tenure fields
- `parcel_streetview` — optional camera point from `roads.py`. Empty until that file is loaded
- `permits` — empty. Columns for a permit id, dates, type, status, flags, and raw JSON
- `app_inclusions` — `why_included`, `owner_group`, and whether the row is in the app

## Provenance

`data_sources` names each upstream dataset. Each CSV load writes a `load_runs` row and `provenance` rows that point at the table and the source. The load itself is the flat extract (`app_dataset_csv`); the provenance notes name the upstream pull that column family came from.

## The app view

`app_homes` joins the current roll year and the current price estimate into the prototype CSV column names, including `SWIS`, `PRINT_KEY`, `rar_2025_pct`, and `market_value_2024_from_rar`. Those last two names are the app contract for this recipe. The table underneath stores `rar_pct`, `rar_year`, and `market_value_from_rar`.

Street-view columns are on the view and are omitted from the HTML payload when they are all null.

`python -m db.export` writes `app_homes` to SQLite (with a `geometry_wkt` column), GeoParquet (WKB point, EPSG:4326, `geo` metadata), and CSV under `data/out/<region>/`.
