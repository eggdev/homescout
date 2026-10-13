-- Enrichment, price estimates (method + version), permits, and app inclusion.
-- Reference tables (school districts, NRI tracts) are shared across counties.

CREATE TABLE IF NOT EXISTS school_districts (
    geoid text PRIMARY KEY,
    name text,
    state_fips varchar(2),
    geom geometry(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS school_districts_geom_gix ON school_districts USING GIST (geom);

CREATE TABLE IF NOT EXISTS parcel_schools (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    school_district_geoid text REFERENCES school_districts (geoid),
    school_district_tiger text,
    school_district_roll text
);

CREATE TABLE IF NOT EXISTS nri_tracts (
    tract_geoid text PRIMARY KEY,
    nri_overall_score double precision,
    nri_overall_rating text,
    nri_social_vuln_rating text,
    nri_community_resilience_rating text,
    nri_inland_flood_score double precision,
    nri_inland_flood_rating text,
    nri_coastal_flood_score double precision,
    nri_coastal_flood_rating text,
    nri_hurricane_score double precision,
    nri_hurricane_rating text,
    nri_winter_weather_score double precision,
    nri_winter_weather_rating text,
    nri_ice_storm_score double precision,
    nri_ice_storm_rating text,
    nri_strong_wind_score double precision,
    nri_strong_wind_rating text,
    nri_heat_wave_score double precision,
    nri_heat_wave_rating text,
    nri_cold_wave_score double precision,
    nri_cold_wave_rating text,
    nri_landslide_score double precision,
    nri_landslide_rating text,
    nri_tornado_score double precision,
    nri_tornado_rating text
);

CREATE TABLE IF NOT EXISTS parcel_nri (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    tract_geoid text REFERENCES nri_tracts (tract_geoid)
);

CREATE TABLE IF NOT EXISTS parcel_flood (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    fema_flood_zone text,
    fema_sfha_100yr boolean,
    fema_bfe_ft double precision
);

CREATE TABLE IF NOT EXISTS parcel_walkability (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    n_grocery_within_800m double precision,
    n_dining_within_800m double precision,
    n_errands_within_800m double precision,
    n_school_within_800m double precision,
    n_park_within_800m double precision,
    n_transit_within_800m double precision,
    walk_proxy_0_100 double precision,
    metro_north_station text,
    metro_north_dist_mi double precision
);

CREATE TABLE IF NOT EXISTS parcel_terrain (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    elevation_ft double precision,
    slope_deg double precision,
    aspect_deg double precision,
    aspect_dir text,
    horizon_max_deg double precision,
    horizon_south_deg double precision,
    solar_terrain_index double precision,
    sky_view_factor double precision
);

-- method is the human-readable recipe. method_version is the stable id.
-- Only one row per parcel may be is_current; older recipes stay for comparison.
CREATE TABLE IF NOT EXISTS price_estimates (
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    method_version text NOT NULL,
    method text NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    rar_year integer,
    rar_pct double precision,
    cod_pct double precision,
    market_value_from_rar double precision,
    est_price_mid double precision,
    est_price_low double precision,
    est_price_high double precision,
    est_price_per_sqft double precision,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parcel_id, method_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS price_estimates_one_current
    ON price_estimates (parcel_id) WHERE is_current;

CREATE TABLE IF NOT EXISTS prior_tenure (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    pre_trust_owner text,
    pre_trust_deed_year text,
    family_tenure_years double precision,
    family_confidence text,
    prior_owner_note text,
    family_tenure_is_min boolean,
    family_tenure_combined_yrs double precision,
    family_tenure_combined_is_min boolean
);

CREATE TABLE IF NOT EXISTS app_inclusions (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    why_included text,
    owner_group text,
    included boolean NOT NULL DEFAULT true
);

-- No Westchester municipality publishes a free bulk permit feed. Table is ready; loader leaves it empty.
CREATE TABLE IF NOT EXISTS permits (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    source_permit_id text,
    issued_on date,
    permit_type text,
    status text,
    description text,
    flags text,
    source_id integer,
    raw jsonb
);

CREATE INDEX IF NOT EXISTS permits_parcel_idx ON permits (parcel_id);

CREATE TABLE IF NOT EXISTS parcel_streetview (
    parcel_id bigint PRIMARY KEY REFERENCES parcels (id) ON DELETE CASCADE,
    sv_lat double precision,
    sv_lon double precision,
    sv_heading double precision,
    road_dist_m double precision
);

INSERT INTO schema_migrations (version) VALUES ('003_enrichment.sql')
ON CONFLICT (version) DO NOTHING;
