# Adding a county

The pipeline is shared. The county lives in an adapter. Westchester is `pipeline/adapters/westchester.py`, registered in `pipeline/adapters/__init__.py`.

## 1. Write the adapter

Subclass `RegionAdapter` and set:

- `key`, `state_fips`, `county_fips`, `state_abbr`, `county_name`
- `roll_year` and `as_of` (the date tenure is measured against)
- `swis_prefix` when the state uses SWIS. Westchester’s county digits are `55`. State FIPS `36` and county FIPS `119` are the 36119 code.

Implement:

- `decode_deed_book` and `derive_deeds`. This is the piece that does not travel. Westchester’s book number is `(year - 1960) * 1000 + day-of-year` for books in the 40000–69999 range. Other New York counties often still use classic liber and page, which do not encode a date. Leave the date null and say so in `deed_basis` rather than copying the Westchester formula.
- `flag_exemptions`. New York counties can call `pipeline.exemptions.flag_nys_exemptions`. Other states need their own senior, veteran, or homestead signals.
- `gis_parcels_query_url`, `gis_where`, `gis_out_fields` when a parcel service exists.
- `bbox` as `(west, south, east, north)`, `metric_crs` (an EPSG code in the right UTM zone), `dem_tiles`, `dem_bounds`, `nfhl_envelope`, `solar_site`.
- `orpts_resource` / `orpts_where` for New York. Elsewhere return `None` and bring the roll in as `data/raw/<key>/raw_210.csv` yourself.
- `trust_name_pattern` if the simple trust/estate flag should match local words.

Register the class in `ADAPTERS`. Select it with `HOMESCOUT_REGION=<key>` or `--region <key>`.

## 2. Parcel identity

Every parcel is unique on **state FIPS + county FIPS + SWIS + print key**.

In New York, SWIS is the 6-digit municipality code and print key is the roll’s print key (`60.14-4-6.1`). Outside New York, put a stable sub-county code in `swis` (township FIPS, appraisal district, or a zero-padded local code — not a null) and the local parcel id in `print_key`. Do not invent a second key. Polygon geometry, when you have it, goes in `parcels.geom`. The analysis point is `lat`/`lon`, and `centroid` is generated from that point.

## 3. Run the pipeline

Files land under `data/raw/<key>/`, `data/enrich/<key>/`, and `data/out/<key>/`. Override the root with `HOMESCOUT_DATA_DIR`.

```bash
python -m pipeline.ingest.fetch_gis
python -m pipeline.ingest.fetch_orpts          # NYS; other states: drop raw_210.csv in yourself
python -m pipeline.build_tenure
python -m pipeline.ingest.fetch_centroids
python -m pipeline.ingest.fetch_nfhl
python -m pipeline.ingest.fetch_dem
python -m pipeline.enrich.osm_extract          # after you place a .osm.pbf in the enrich directory
python -m pipeline.enrich.enrich
```

`enrich` expects, in the enrich directory: `centroids.csv`, the TIGER zips named by the adapter, `nri.json` (an Esri JSON feature set of tract attributes), `nfhl.geojson`, `osm_pois.csv`, and `dem.tif`.

Price attachment also expects `rar.csv`, `equity.csv`, and `zhvi_county.csv` (Zillow county ZHVI with `RegionName`, `State`, and month columns). Column names match the NYS ratio files and the Zillow research CSV.

```bash
python -m pipeline.enrich.merge
python -m pipeline.enrich.owner_type
python -m pipeline.enrich.prior_tenure         # needs data/raw/<key>/owners_2021.csv … owners_2024.csv
python -m pipeline.enrich.app_dataset
python -m pipeline.enrich.roads                # optional Street View camera points
python -m pipeline.enrich.build_overlays       # optional school-district and station layers
```

Owner-type patterns were tuned on Westchester names. Read a sample of `owner_types.csv` before trusting them in a new county.

## 4. Load and build the app

```bash
python -m db.migrate
python -m db.load_csv data/out/<key>/app_dataset.csv --region <key>
python -m app.build_mobile --source db --region <key>
```

`app_homes` is the flat contract the HTML build reads. The same frame can come from `--source csv`, `--source sqlite`, or `--source parquet` after `python -m db.export`.

Roll years are rows, not new tables. A later assessment year inserts another `deeds`, `parcel_owners`, `parcel_exemptions`, and `assessments` row for the same parcel. Price recipes are `price_estimates` rows with a `method_version`; only one row per parcel has `is_current`.

## 5. What you should not copy blindly

- The Westchester deed-book formula.
- Metro-North station logic. Replace it with the transit system that matters, or leave the columns null.
- The ZHVI series and the July 2024 base date inside `pipeline/enrich/merge.py`. Change the base date when the assessment ratio’s vintage changes, and keep the description in `price_method`.
- Hard-coded `/workspace/...` paths. There should not be any. Paths come from `pipeline.config` and the adapter key.
