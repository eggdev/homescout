"""Load the committed extract into local PostGIS and compare app_homes to the CSV."""

import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow.parquet as pq
import pytest

from db.query import read_sql

from db.export import export_geoparquet, export_sqlite
from db.load_csv import load_csv
from db.migrate import apply_migrations
from db.normalize import read_app_csv
from pipeline.adapters.westchester import WestchesterNY
from pipeline.columns import APP_COLUMNS, STREETVIEW_COLUMNS
from pipeline.config import app_dataset_path, database_url


def _none(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def _is_bool(value) -> bool:
    return type(value).__name__ in ("bool", "bool_")


def _equal(left, right) -> bool:
    left, right = _none(left), _none(right)
    if left is None or right is None:
        return left is None and right is None
    if _is_bool(left) or _is_bool(right):
        return _is_bool(left) and _is_bool(right) and bool(left) == bool(right)
    if isinstance(left, datetime):
        left = left.date().isoformat()
    elif isinstance(left, date):
        left = left.isoformat()
    if isinstance(right, datetime):
        right = right.date().isoformat()
    elif isinstance(right, date):
        right = right.isoformat()
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-6)
    return str(left) == str(right)


@pytest.fixture(scope="module")
def loaded():
    dsn = database_url()
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available: {exc}")
    path = app_dataset_path("westchester_sf_app_dataset.csv.gz")
    apply_migrations(dsn)
    apply_migrations(dsn)
    count = load_csv(path, WestchesterNY(), dsn)
    return dsn, path, count


def test_load_counts_and_spatial_key(loaded):
    dsn, _path, count = loaded
    assert count == 65011
    with psycopg.connect(dsn) as conn:
        parcels = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
        towns = conn.execute(
            "SELECT COUNT(*) FROM municipalities m JOIN regions r ON r.id = m.region_id WHERE r.adapter = 'westchester_ny'"
        ).fetchone()[0]
        permits = conn.execute("SELECT COUNT(*) FROM permits").fetchone()[0]
        region = conn.execute(
            "SELECT state_fips, county_fips, roll_year FROM regions WHERE adapter = 'westchester_ny'"
        ).fetchone()
        senior = conn.execute("SELECT COUNT(*) FROM parcel_exemptions WHERE senior_signal").fetchone()[0]
        trust = conn.execute("SELECT COUNT(*) FROM parcel_owners WHERE trust_or_estate_owner").fetchone()[0]
        tenure = dict(
            conn.execute("SELECT tenure_20plus, COUNT(*) FROM deeds GROUP BY 1").fetchall()
        )
        point = conn.execute(
            """
            SELECT owner, city_town, lat, lon, est_price_mid, tenure_20plus
            FROM app_homes
            WHERE "SWIS" = '552000' AND "PRINT_KEY" = '60.14-4-6.1'
            """
        ).fetchone()
        neighbors = conn.execute(
            """
            SELECT COUNT(*)
            FROM parcels p
            JOIN parcels q ON q.id <> p.id
            WHERE p.swis = '552000' AND p.print_key = '60.14-4-6.1'
              AND ST_DWithin(p.centroid::geography, q.centroid::geography, 800)
            """
        ).fetchone()[0]
        versions = conn.execute("SELECT version FROM schema_migrations ORDER BY 1").fetchall()
    assert parcels == 65011
    assert towns == 45
    assert permits == 0
    assert region == ("36", "119", 2025)
    assert senior == 9285
    assert trust == 7436
    assert tenure == {"likely": 48341, "yes": 9698, "no": 6605, "unknown": 367}
    assert point[0] == "Palmesi, Richard"
    assert point[1] == "Bedford"
    assert math.isclose(point[2], 41.236336, abs_tol=1e-6)
    assert math.isclose(point[3], -73.69438493711657, abs_tol=1e-8)
    assert point[4] == 730000
    assert point[5] == "likely"
    assert neighbors >= 1
    assert [row[0] for row in versions] == [
        "001_extensions.sql",
        "002_core.sql",
        "003_enrichment.sql",
        "004_provenance.sql",
        "005_app_view.sql",
    ]


def test_app_homes_matches_csv(loaded):
    dsn, path, _count = loaded
    expected = {(row["SWIS"], row["PRINT_KEY"]): row for row in read_app_csv(path)}
    frame = read_sql("SELECT * FROM app_homes", dsn)
    assert list(frame.columns[: len(APP_COLUMNS)]) == APP_COLUMNS
    assert list(frame.columns[len(APP_COLUMNS) :]) == STREETVIEW_COLUMNS
    assert len(frame) == len(expected)
    mismatches = []
    for row in frame.itertuples(index=False, name=None):
        got = dict(zip(frame.columns, row))
        key = (got["SWIS"], got["PRINT_KEY"])
        src = expected[key]
        for column in APP_COLUMNS:
            if column in ("permits_matched", "permit_flags"):
                if (got[column] or "") != (src[column] or ""):
                    mismatches.append((key, column, src[column], got[column]))
                continue
            if not _equal(src[column], got[column]):
                mismatches.append((key, column, src[column], got[column]))
            if len(mismatches) >= 8:
                break
        if len(mismatches) >= 8:
            break
    assert not mismatches, mismatches


def test_sqlite_and_geoparquet_export(loaded, tmp_path: Path):
    dsn, _path, _count = loaded
    frame = read_sql("SELECT * FROM app_homes", dsn)
    sqlite_path = tmp_path / "homes.sqlite"
    parquet_path = tmp_path / "homes.parquet"
    export_sqlite(frame, sqlite_path)
    export_geoparquet(frame, parquet_path)
    with sqlite3.connect(sqlite_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM homes").fetchone()[0]
        wkt = conn.execute(
            'SELECT geometry_wkt FROM homes WHERE "SWIS" = ? AND "PRINT_KEY" = ?',
            ("552000", "60.14-4-6.1"),
        ).fetchone()[0]
    assert count == 65011
    assert wkt.startswith("POINT(")
    schema = pq.read_schema(parquet_path)
    meta = json.loads(schema.metadata[b"geo"])
    assert meta["primary_column"] == "geometry"
    assert meta["columns"]["geometry"]["crs"]["id"]["code"] == 4326
    table = pq.read_table(parquet_path, columns=["geometry"])
    assert table.num_rows == 65011
