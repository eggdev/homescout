-- Regions, municipalities, parcels, owners, deeds, exemptions, assessments.
-- A parcel's natural key is state FIPS + county FIPS + SWIS + print key.
-- Outside New York, put a stable sub-county code in swis (see docs/adding-a-county.md).

CREATE TABLE IF NOT EXISTS regions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state_fips varchar(2) NOT NULL,
    county_fips varchar(3) NOT NULL,
    state_abbr varchar(2) NOT NULL,
    name text NOT NULL,
    adapter text NOT NULL,
    roll_year integer,
    UNIQUE (state_fips, county_fips)
);

CREATE TABLE IF NOT EXISTS municipalities (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_id integer NOT NULL REFERENCES regions (id),
    swis text NOT NULL,
    city_town text NOT NULL,
    municipality text NOT NULL,
    UNIQUE (region_id, swis)
);

CREATE TABLE IF NOT EXISTS parcels (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_id integer NOT NULL REFERENCES regions (id),
    municipality_id integer NOT NULL REFERENCES municipalities (id),
    state_fips varchar(2) NOT NULL,
    county_fips varchar(3) NOT NULL,
    swis text NOT NULL,
    print_key text NOT NULL,
    sbl text,
    address text,
    zip text,
    prop_class text,
    -- Parcel boundary when the county GIS provides one. The app dataset is points.
    geom geometry(Geometry, 4326),
    lat double precision,
    lon double precision,
    centroid geometry(Point, 4326) GENERATED ALWAYS AS (
        CASE
            WHEN lat IS NOT NULL AND lon IS NOT NULL
            THEN ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            ELSE NULL
        END
    ) STORED,
    FOREIGN KEY (state_fips, county_fips) REFERENCES regions (state_fips, county_fips),
    UNIQUE (state_fips, county_fips, swis, print_key)
);

CREATE INDEX IF NOT EXISTS parcels_region_idx ON parcels (region_id);
CREATE INDEX IF NOT EXISTS parcels_municipality_idx ON parcels (municipality_id);
CREATE INDEX IF NOT EXISTS parcels_centroid_gix ON parcels USING GIST (centroid);
CREATE INDEX IF NOT EXISTS parcels_geom_gix ON parcels USING GIST (geom);

CREATE TABLE IF NOT EXISTS owner_types (
    code text PRIMARY KEY,
    label text NOT NULL UNIQUE,
    is_trust_or_estate boolean NOT NULL DEFAULT false
);

INSERT INTO owner_types (code, label, is_trust_or_estate) VALUES
    ('individual', 'Individual(s)', false),
    ('revocable_trust', 'Revocable/Living trust', true),
    ('irrevocable_trust', 'Irrevocable trust', true),
    ('other_trust', 'Other trust', true),
    ('life_estate', 'Life estate', true),
    ('estate', 'Estate', true),
    ('llc', 'LLC/corporation', false)
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS parcel_owners (
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    roll_year integer NOT NULL,
    owner_name text,
    additional_owner text,
    mail_addr text,
    mail_city text,
    mail_state text,
    mail_zip text,
    owner_type_code text REFERENCES owner_types (code),
    owner_flags text,
    owner_occupied_est boolean,
    absentee_owner boolean,
    trust_or_estate_owner boolean,
    PRIMARY KEY (parcel_id, roll_year)
);

-- One deed observation per parcel per assessment-roll year.
-- Historical rolls add rows; they do not overwrite the current year.
CREATE TABLE IF NOT EXISTS deeds (
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    roll_year integer NOT NULL,
    deed_book text,
    deed_page text,
    deed_date_est date,
    deed_year_est integer,
    tenure_years_est double precision,
    tenure_20plus text,
    deed_basis text,
    blank_deed_means_before_year double precision,
    recorded_year double precision,
    PRIMARY KEY (parcel_id, roll_year),
    CONSTRAINT deeds_tenure_status CHECK (
        tenure_20plus IS NULL OR tenure_20plus IN ('yes', 'no', 'likely', 'unknown')
    )
);

CREATE TABLE IF NOT EXISTS parcel_exemptions (
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    roll_year integer NOT NULL,
    codes text,
    senior_aged boolean,
    enhanced_star boolean,
    senior_signal boolean,
    basic_star boolean,
    veteran boolean,
    PRIMARY KEY (parcel_id, roll_year)
);

CREATE TABLE IF NOT EXISTS exemption_codes (
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    roll_year integer NOT NULL,
    code text NOT NULL,
    PRIMARY KEY (parcel_id, roll_year, code)
);

CREATE INDEX IF NOT EXISTS exemption_codes_code_idx ON exemption_codes (code);

CREATE TABLE IF NOT EXISTS assessments (
    parcel_id bigint NOT NULL REFERENCES parcels (id) ON DELETE CASCADE,
    roll_year integer NOT NULL,
    full_market_value double precision,
    total_assessed_value double precision,
    year_built double precision,
    living_sqft double precision,
    bedrooms double precision,
    full_baths double precision,
    kitchens double precision,
    style text,
    lot_acres double precision,
    lot_sqft double precision,
    school_district_name text,
    PRIMARY KEY (parcel_id, roll_year)
);

INSERT INTO schema_migrations (version) VALUES ('002_core.sql')
ON CONFLICT (version) DO NOTHING;
