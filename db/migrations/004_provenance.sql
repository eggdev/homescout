-- Source catalog and load provenance. The loader writes one load_run per import
-- and one provenance row per table it filled.

CREATE TABLE IF NOT EXISTS data_sources (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_key text NOT NULL UNIQUE,
    name text NOT NULL,
    url text,
    description text
);

INSERT INTO data_sources (source_key, name, url, description) VALUES
    ('westchester_gis_tax_parcels', 'Westchester GIS DataHub tax parcels',
     'https://giswww.westchestergov.com/ArcGIS/rest/services/DataHub_TaxParcels/MapServer/0',
     '2025 ORPTS roll attributes joined to parcel geometry.'),
    ('nys_orpts_assessment_roll', 'NYS ORPTS assessment rolls',
     'https://data.ny.gov/resource/7vem-aaz7',
     'Property assessment data from local rolls. Exemption codes truncated to 4 digits.'),
    ('nys_orpts_rar', 'NYS residential assessment ratios',
     'https://data.ny.gov/resource/bsmp-6um6',
     'ORPTS residential assessment ratio from RP-5217 sales studies.'),
    ('nys_orpts_cod', 'NYS coefficient of dispersion',
     'https://data.ny.gov/resource/4sut-q3dt',
     'Residential coefficient of dispersion by municipality.'),
    ('zillow_zhvi', 'Zillow Home Value Index, county',
     'https://www.zillow.com/research/data/',
     'Westchester single-family ZHVI used to move mid-2024 values forward.'),
    ('census_tiger_unsd', 'Census TIGER unified school districts',
     'https://www2.census.gov/geo/tiger/TIGER2024/UNSD/',
     '2024 unified school district boundaries.'),
    ('census_tiger_tracts', 'Census TIGER census tracts',
     'https://www2.census.gov/geo/tiger/TIGER2024/TRACT/',
     '2024 tract boundaries used to attach FEMA NRI.'),
    ('fema_nfhl', 'FEMA National Flood Hazard Layer',
     'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28',
     'Flood zone at the parcel point. Not an official determination.'),
    ('fema_nri', 'FEMA National Risk Index',
     'https://hazards.fema.gov/nri/',
     'Tract-level NRI v1.20 scores and ratings.'),
    ('usgs_3dep', 'USGS 3DEP elevation',
     'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/',
     '1/3 arc-second DEM for elevation, slope, aspect, and terrain sun.'),
    ('osm', 'OpenStreetMap',
     'https://www.openstreetmap.org/copyright',
     'Geofabrik New York extract or Overpass: amenities, transit, roads.'),
    ('app_dataset_csv', 'HomeScout app dataset extract',
     NULL,
     'Flat extract loaded by db.load_csv. Provenance of the upstream pulls is above.')
ON CONFLICT (source_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS load_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_id integer REFERENCES regions (id),
    source_id integer REFERENCES data_sources (id),
    input_path text,
    row_count integer,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    notes text
);

CREATE TABLE IF NOT EXISTS provenance (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_run_id bigint REFERENCES load_runs (id),
    region_id integer REFERENCES regions (id),
    table_name text NOT NULL,
    source_id integer REFERENCES data_sources (id),
    roll_year integer,
    notes text
);

-- permits.source_id was created before data_sources. Attach the foreign key now.
ALTER TABLE permits
    ADD CONSTRAINT permits_source_id_fkey
    FOREIGN KEY (source_id) REFERENCES data_sources (id);

INSERT INTO schema_migrations (version) VALUES ('004_provenance.sql')
ON CONFLICT (version) DO NOTHING;
