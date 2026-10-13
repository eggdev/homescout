"""Load the flat app CSV into PostGIS. Re-running replaces that region's parcels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from db.migrate import apply_migrations
from db.normalize import read_app_csv
from pipeline.adapters import get_adapter
from pipeline.adapters.base import RegionAdapter
from pipeline.columns import NRI_RATING_COLUMNS, NRI_SCORE_COLUMNS
from pipeline.config import app_dataset_path, database_url


def _copy(cur, table: str, columns: list[str], rows: list[tuple]) -> None:
    if not rows:
        return
    sql = f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    with cur.copy(sql) as copy:
        for row in rows:
            copy.write_row(row)


def _source_ids(cur) -> dict[str, int]:
    return {key: source_id for source_id, key in cur.execute("SELECT id, source_key FROM data_sources")}


def _upsert_region(cur, adapter: RegionAdapter) -> int:
    row = cur.execute(
        """
        INSERT INTO regions (state_fips, county_fips, state_abbr, name, adapter, roll_year)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (state_fips, county_fips) DO UPDATE
        SET state_abbr = EXCLUDED.state_abbr,
            name = EXCLUDED.name,
            adapter = EXCLUDED.adapter,
            roll_year = EXCLUDED.roll_year
        RETURNING id
        """,
        (
            adapter.state_fips,
            adapter.county_fips,
            adapter.state_abbr,
            adapter.county_name,
            adapter.key,
            adapter.roll_year,
        ),
    ).fetchone()
    return row[0]


def _whole(value):
    if value is None:
        return None
    if float(value).is_integer():
        return int(value)
    return value


def load_csv(path: Path, adapter: RegionAdapter, dsn: str | None = None) -> int:
    rows = read_app_csv(path)
    if not rows:
        raise SystemExit(f"{path} has no data rows")
    dsn = dsn or database_url()
    year = adapter.roll_year
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            region_id = _upsert_region(cur, adapter)
            cur.execute("DELETE FROM parcels WHERE region_id = %s", (region_id,))
            cur.execute("DELETE FROM municipalities WHERE region_id = %s", (region_id,))

            municipalities = {}
            for row in rows:
                municipalities[row["SWIS"]] = (row["city_town"], row["municipality"] or row["city_town"])
            cur.executemany(
                """
                INSERT INTO municipalities (region_id, swis, city_town, municipality)
                VALUES (%s, %s, %s, %s)
                """,
                [(region_id, swis, town, local) for swis, (town, local) in municipalities.items()],
            )
            muni_id = {
                swis: mid
                for mid, swis in cur.execute(
                    "SELECT id, swis FROM municipalities WHERE region_id = %s", (region_id,)
                )
            }

            districts = {}
            for row in rows:
                geoid = row["school_district_geoid"]
                if geoid:
                    districts[geoid] = row["school_district_tiger"]
            cur.executemany(
                """
                INSERT INTO school_districts (geoid, name, state_fips)
                VALUES (%s, %s, %s)
                ON CONFLICT (geoid) DO UPDATE
                SET name = COALESCE(EXCLUDED.name, school_districts.name),
                    state_fips = EXCLUDED.state_fips
                """,
                [(geoid, name, adapter.state_fips) for geoid, name in districts.items()],
            )

            tracts: dict[str, dict] = {}
            for row in rows:
                geoid = row["tract_geoid"]
                if not geoid:
                    continue
                current = tracts.get(geoid)
                if current is None or _score_count(current) < _score_count(row):
                    tracts[geoid] = row
            nri_columns = ["tract_geoid", *NRI_SCORE_COLUMNS, *NRI_RATING_COLUMNS]
            cur.executemany(
                f"""
                INSERT INTO nri_tracts ({', '.join(nri_columns)})
                VALUES ({', '.join(['%s'] * len(nri_columns))})
                ON CONFLICT (tract_geoid) DO UPDATE SET
                {', '.join(f'{column} = EXCLUDED.{column}' for column in nri_columns if column != 'tract_geoid')}
                """,
                [tuple(tracts[geoid][column] for column in nri_columns) for geoid in tracts],
            )

            _copy(
                cur,
                "parcels",
                [
                    "region_id",
                    "municipality_id",
                    "state_fips",
                    "county_fips",
                    "swis",
                    "print_key",
                    "sbl",
                    "address",
                    "zip",
                    "prop_class",
                    "lat",
                    "lon",
                ],
                [
                    (
                        region_id,
                        muni_id[row["SWIS"]],
                        adapter.state_fips,
                        adapter.county_fips,
                        row["SWIS"],
                        row["PRINT_KEY"],
                        row["SBL"],
                        row["address"],
                        row["zip"],
                        adapter.single_family_class(),
                        row["lat"],
                        row["lon"],
                    )
                    for row in rows
                ],
            )
            parcel_id = {
                (swis, print_key): pid
                for pid, swis, print_key in cur.execute(
                    "SELECT id, swis, print_key FROM parcels WHERE region_id = %s",
                    (region_id,),
                )
            }
            labels = {label: code for code, label in cur.execute("SELECT code, label FROM owner_types")}

            def pid_of(row):
                return parcel_id[(row["SWIS"], row["PRINT_KEY"])]

            unknown = sorted({row["owner_type"] for row in rows if row["owner_type"] not in labels})
            if unknown:
                raise SystemExit(f"owner_type values missing from owner_types: {unknown}")

            _copy(
                cur,
                "parcel_owners",
                [
                    "parcel_id",
                    "roll_year",
                    "owner_name",
                    "additional_owner",
                    "mail_addr",
                    "mail_city",
                    "mail_state",
                    "mail_zip",
                    "owner_type_code",
                    "owner_flags",
                    "owner_occupied_est",
                    "absentee_owner",
                    "trust_or_estate_owner",
                ],
                [
                    (
                        pid_of(row),
                        year,
                        row["owner"],
                        row["additional_owner"],
                        row["mail_addr"],
                        row["mail_city"],
                        row["mail_state"],
                        row["mail_zip"],
                        labels[row["owner_type"]],
                        row["owner_flags"],
                        row["owner_occupied_est"],
                        row["absentee_owner"],
                        row["trust_or_estate_owner"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "deeds",
                [
                    "parcel_id",
                    "roll_year",
                    "deed_book",
                    "deed_page",
                    "deed_date_est",
                    "deed_year_est",
                    "tenure_years_est",
                    "tenure_20plus",
                    "deed_basis",
                    "blank_deed_means_before_year",
                    "recorded_year",
                ],
                [
                    (
                        pid_of(row),
                        year,
                        row["deed_book"],
                        row["deed_page"],
                        row["deed_date_est"],
                        row["deed_date_est"].year if row["deed_date_est"] else None,
                        row["tenure_years_est"],
                        row["tenure_20plus"],
                        row["deed_basis"],
                        row["blank_deed_means_before_year"],
                        row["deed_recorded_year"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "parcel_exemptions",
                [
                    "parcel_id",
                    "roll_year",
                    "codes",
                    "senior_aged",
                    "enhanced_star",
                    "senior_signal",
                    "basic_star",
                    "veteran",
                ],
                [
                    (
                        pid_of(row),
                        year,
                        row["exemption_codes_4digit"],
                        row["senior_aged_exemption_4180x"],
                        row["enhanced_star_4183x"],
                        row["senior_signal"],
                        row["basic_star_4185x"],
                        row["veteran_exemption"],
                    )
                    for row in rows
                ],
            )
            code_rows = []
            for row in rows:
                codes = row["exemption_codes_4digit"]
                if not codes:
                    continue
                seen = []
                for code in codes.split(";"):
                    code = code.strip()
                    if code and code not in seen:
                        seen.append(code)
                parcel = pid_of(row)
                code_rows.extend((parcel, year, code) for code in seen)
            _copy(cur, "exemption_codes", ["parcel_id", "roll_year", "code"], code_rows)
            _copy(
                cur,
                "assessments",
                [
                    "parcel_id",
                    "roll_year",
                    "full_market_value",
                    "year_built",
                    "living_sqft",
                    "bedrooms",
                    "full_baths",
                    "kitchens",
                    "style",
                    "lot_acres",
                    "lot_sqft",
                    "school_district_name",
                ],
                [
                    (
                        pid_of(row),
                        year,
                        row["full_market_value"],
                        row["year_built"],
                        row["living_sqft"],
                        row["bedrooms"],
                        row["full_baths"],
                        row["kitchens"],
                        row["style"],
                        row["lot_acres"],
                        row["lot_sqft"],
                        row["school_district_roll"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "parcel_schools",
                ["parcel_id", "school_district_geoid", "school_district_tiger", "school_district_roll"],
                [
                    (
                        pid_of(row),
                        row["school_district_geoid"],
                        row["school_district_tiger"],
                        row["school_district_roll"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "parcel_nri",
                ["parcel_id", "tract_geoid"],
                [(pid_of(row), row["tract_geoid"]) for row in rows if row["tract_geoid"]],
            )
            _copy(
                cur,
                "parcel_flood",
                ["parcel_id", "fema_flood_zone", "fema_sfha_100yr", "fema_bfe_ft"],
                [
                    (pid_of(row), row["fema_flood_zone"], row["fema_sfha_100yr"], row["fema_bfe_ft"])
                    for row in rows
                ],
            )
            _copy(
                cur,
                "parcel_walkability",
                [
                    "parcel_id",
                    "n_grocery_within_800m",
                    "n_dining_within_800m",
                    "n_errands_within_800m",
                    "n_school_within_800m",
                    "n_park_within_800m",
                    "n_transit_within_800m",
                    "walk_proxy_0_100",
                    "metro_north_station",
                    "metro_north_dist_mi",
                ],
                [
                    (
                        pid_of(row),
                        row["n_grocery_within_800m"],
                        row["n_dining_within_800m"],
                        row["n_errands_within_800m"],
                        row["n_school_within_800m"],
                        row["n_park_within_800m"],
                        row["n_transit_within_800m"],
                        row["walk_proxy_0_100"],
                        row["metro_north_station"],
                        row["metro_north_dist_mi"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "parcel_terrain",
                [
                    "parcel_id",
                    "elevation_ft",
                    "slope_deg",
                    "aspect_deg",
                    "aspect_dir",
                    "horizon_max_deg",
                    "horizon_south_deg",
                    "solar_terrain_index",
                    "sky_view_factor",
                ],
                [
                    (
                        pid_of(row),
                        row["elevation_ft"],
                        row["slope_deg"],
                        row["aspect_deg"],
                        row["aspect_dir"],
                        row["horizon_max_deg"],
                        row["horizon_south_deg"],
                        row["solar_terrain_index"],
                        row["sky_view_factor"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "price_estimates",
                [
                    "parcel_id",
                    "method_version",
                    "method",
                    "is_current",
                    "rar_year",
                    "rar_pct",
                    "cod_pct",
                    "market_value_from_rar",
                    "est_price_mid",
                    "est_price_low",
                    "est_price_high",
                    "est_price_per_sqft",
                ],
                [
                    (
                        pid_of(row),
                        adapter.price_method_version(),
                        row["price_method"] or adapter.price_method_version(),
                        True,
                        adapter.roll_year,
                        row["rar_2025_pct"],
                        row["cod_pct"],
                        row["market_value_2024_from_rar"],
                        row["est_price_mid"],
                        row["est_price_low"],
                        row["est_price_high"],
                        row["est_price_per_sqft"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "prior_tenure",
                [
                    "parcel_id",
                    "pre_trust_owner",
                    "pre_trust_deed_year",
                    "family_tenure_years",
                    "family_confidence",
                    "prior_owner_note",
                    "family_tenure_is_min",
                    "family_tenure_combined_yrs",
                    "family_tenure_combined_is_min",
                ],
                [
                    (
                        pid_of(row),
                        row["pre_trust_owner"],
                        row["pre_trust_deed_year"],
                        row["family_tenure_years"],
                        row["family_confidence"],
                        row["prior_owner_note"],
                        row["family_tenure_is_min"],
                        row["family_tenure_combined_yrs"],
                        row["family_tenure_combined_is_min"],
                    )
                    for row in rows
                ],
            )
            _copy(
                cur,
                "app_inclusions",
                ["parcel_id", "why_included", "owner_group", "included"],
                [(pid_of(row), row["why_included"], row["owner_group"], True) for row in rows],
            )

            sources = _source_ids(cur)
            load_id = cur.execute(
                """
                INSERT INTO load_runs (region_id, source_id, input_path, row_count, notes)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    region_id,
                    sources["app_dataset_csv"],
                    str(path),
                    len(rows),
                    "Flat app extract. Upstream datasets are recorded on provenance rows.",
                ),
            ).fetchone()[0]
            provenance = [
                ("parcels", "westchester_gis_tax_parcels", "Location, lot, and roll identifiers."),
                ("parcel_owners", "nys_orpts_assessment_roll", "Owner name, mailing address, owner type."),
                ("deeds", "westchester_gis_tax_parcels", "Book/page plus control-number tenure."),
                ("parcel_exemptions", "nys_orpts_assessment_roll", "4-digit exemption codes and senior flags."),
                ("assessments", "westchester_gis_tax_parcels", "Inventory and full market value."),
                ("parcel_schools", "census_tiger_unsd", "TIGER district plus roll district name."),
                ("nri_tracts", "fema_nri", "Tract scores shared by every parcel in the tract."),
                ("parcel_flood", "fema_nfhl", "Flood zone at the parcel point."),
                ("parcel_walkability", "osm", "Amenity counts and Metro-North distance."),
                ("parcel_terrain", "usgs_3dep", "Elevation, slope, aspect, terrain sun."),
                ("price_estimates", "nys_orpts_rar", "RAR, COD, and Zillow ZHVI adjustment."),
                ("prior_tenure", "nys_orpts_assessment_roll", "Pre-trust owner from earlier rolls."),
                ("app_inclusions", "app_dataset_csv", "20+ year owners plus trust/estate homes."),
            ]
            cur.executemany(
                """
                INSERT INTO provenance (load_run_id, region_id, table_name, source_id, roll_year, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (load_id, region_id, table, sources[source], year, notes)
                    for table, source, notes in provenance
                ],
            )
            cur.execute("UPDATE load_runs SET finished_at = now() WHERE id = %s", (load_id,))
        conn.commit()
    return len(rows)


def _score_count(row: dict) -> int:
    return sum(row.get(column) is not None for column in NRI_SCORE_COLUMNS)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load a HomeScout app CSV into PostGIS")
    parser.add_argument("csv", nargs="?", type=Path)
    parser.add_argument("--region", default=None, help="Adapter key (default HOMESCOUT_REGION or westchester_ny)")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    adapter = get_adapter(args.region)
    path = args.csv or app_dataset_path(adapter.app_dataset_filename())
    if not path.exists():
        sys.exit(f"CSV not found: {path}")
    dsn = args.database_url or database_url()
    try:
        apply_migrations(dsn)
        count = load_csv(path, adapter, dsn)
    except psycopg.OperationalError as exc:
        sys.exit(f"Could not connect to Postgres: {exc}")
    print(f"loaded {count} parcels from {path} into {adapter.key}")


if __name__ == "__main__":
    main()
