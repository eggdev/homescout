-- Flat app contract. Column names match the prototype CSV so the HTML build
-- can read the view or the file. rar_2025_pct and market_value_2024_from_rar
-- keep those names for the current app; the table stores a versioned estimate.

CREATE OR REPLACE VIEW app_homes AS
SELECT
    p.swis AS "SWIS",
    p.print_key AS "PRINT_KEY",
    p.sbl AS "SBL",
    m.city_town,
    m.municipality,
    p.address,
    p.zip,
    o.owner_name AS owner,
    o.additional_owner,
    o.mail_addr,
    o.mail_city,
    o.mail_state,
    o.mail_zip,
    o.owner_occupied_est,
    o.absentee_owner,
    o.trust_or_estate_owner,
    d.deed_book,
    d.deed_page,
    to_char(d.deed_date_est, 'YYYY-MM-DD') AS deed_date_est,
    d.tenure_years_est,
    d.tenure_20plus,
    d.deed_basis,
    d.blank_deed_means_before_year,
    e.codes AS exemption_codes_4digit,
    e.senior_aged AS senior_aged_exemption_4180x,
    e.enhanced_star AS enhanced_star_4183x,
    e.senior_signal,
    e.basic_star AS basic_star_4185x,
    e.veteran AS veteran_exemption,
    a.year_built,
    a.living_sqft,
    a.bedrooms,
    a.full_baths,
    a.kitchens,
    a.style,
    a.lot_acres,
    a.lot_sqft,
    a.full_market_value,
    COALESCE(pm.permits_matched, '') AS permits_matched,
    COALESCE(pm.permit_flags, '') AS permit_flags,
    sc.school_district_tiger,
    sc.school_district_geoid,
    pn.tract_geoid,
    n.nri_overall_score,
    n.nri_overall_rating,
    n.nri_social_vuln_rating,
    n.nri_community_resilience_rating,
    n.nri_inland_flood_score,
    n.nri_inland_flood_rating,
    n.nri_coastal_flood_score,
    n.nri_coastal_flood_rating,
    n.nri_hurricane_score,
    n.nri_hurricane_rating,
    n.nri_winter_weather_score,
    n.nri_winter_weather_rating,
    n.nri_ice_storm_score,
    n.nri_ice_storm_rating,
    n.nri_strong_wind_score,
    n.nri_strong_wind_rating,
    n.nri_heat_wave_score,
    n.nri_heat_wave_rating,
    n.nri_cold_wave_score,
    n.nri_cold_wave_rating,
    n.nri_landslide_score,
    n.nri_landslide_rating,
    n.nri_tornado_score,
    n.nri_tornado_rating,
    f.fema_flood_zone,
    f.fema_sfha_100yr,
    f.fema_bfe_ft,
    w.n_grocery_within_800m,
    w.n_dining_within_800m,
    w.n_errands_within_800m,
    w.n_school_within_800m,
    w.n_park_within_800m,
    w.n_transit_within_800m,
    w.walk_proxy_0_100,
    w.metro_north_station,
    w.metro_north_dist_mi,
    t.elevation_ft,
    t.slope_deg,
    t.aspect_deg,
    t.aspect_dir,
    t.horizon_max_deg,
    t.horizon_south_deg,
    t.solar_terrain_index,
    t.sky_view_factor,
    p.lat,
    p.lon,
    sc.school_district_roll,
    pr.rar_pct AS rar_2025_pct,
    pr.cod_pct,
    pr.market_value_from_rar AS market_value_2024_from_rar,
    pr.est_price_mid,
    pr.est_price_low,
    pr.est_price_high,
    pr.method AS price_method,
    pr.est_price_per_sqft,
    ot.label AS owner_type,
    o.owner_flags,
    pri.pre_trust_owner,
    pri.pre_trust_deed_year,
    pri.family_tenure_years,
    pri.family_confidence,
    pri.prior_owner_note,
    pri.family_tenure_is_min,
    inc.why_included,
    inc.owner_group,
    pri.family_tenure_combined_yrs,
    pri.family_tenure_combined_is_min,
    d.recorded_year AS deed_recorded_year,
    sv.sv_lat,
    sv.sv_lon,
    sv.sv_heading,
    sv.road_dist_m
FROM parcels p
JOIN regions r ON r.id = p.region_id
JOIN municipalities m ON m.id = p.municipality_id
JOIN app_inclusions inc ON inc.parcel_id = p.id AND inc.included
LEFT JOIN parcel_owners o ON o.parcel_id = p.id AND o.roll_year = r.roll_year
LEFT JOIN owner_types ot ON ot.code = o.owner_type_code
LEFT JOIN deeds d ON d.parcel_id = p.id AND d.roll_year = r.roll_year
LEFT JOIN parcel_exemptions e ON e.parcel_id = p.id AND e.roll_year = r.roll_year
LEFT JOIN assessments a ON a.parcel_id = p.id AND a.roll_year = r.roll_year
LEFT JOIN parcel_schools sc ON sc.parcel_id = p.id
LEFT JOIN parcel_nri pn ON pn.parcel_id = p.id
LEFT JOIN nri_tracts n ON n.tract_geoid = pn.tract_geoid
LEFT JOIN parcel_flood f ON f.parcel_id = p.id
LEFT JOIN parcel_walkability w ON w.parcel_id = p.id
LEFT JOIN parcel_terrain t ON t.parcel_id = p.id
LEFT JOIN price_estimates pr ON pr.parcel_id = p.id AND pr.is_current
LEFT JOIN prior_tenure pri ON pri.parcel_id = p.id
LEFT JOIN parcel_streetview sv ON sv.parcel_id = p.id
LEFT JOIN (
    SELECT
        parcel_id,
        string_agg(description, '; ' ORDER BY id) AS permits_matched,
        string_agg(flags, '; ' ORDER BY id) AS permit_flags
    FROM permits
    GROUP BY parcel_id
) pm ON pm.parcel_id = p.id;

INSERT INTO schema_migrations (version) VALUES ('005_app_view.sql')
ON CONFLICT (version) DO NOTHING;
