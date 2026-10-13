"""Load the app table from Postgres, the CSV extract, SQLite, or GeoParquet."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from db.query import read_sql
from pipeline.adapters import get_adapter
from pipeline.columns import APP_COLUMNS, DROP_BEFORE_ENCODE, STREETVIEW_COLUMNS
from pipeline.config import app_dataset_path, enrich_dir


def load_app_frame(source: str, path: Path | None = None, region: str | None = None) -> pd.DataFrame:
    adapter = get_adapter(region)
    if source == "csv":
        csv_path = path or app_dataset_path(adapter.app_dataset_filename())
        frame = pd.read_csv(csv_path, low_memory=False, dtype={"SWIS": str, "PRINT_KEY": str})
    elif source == "db":
        frame = read_sql("SELECT * FROM app_homes")
    elif source == "parquet":
        if path is None:
            raise SystemExit("--input is required for --source parquet")
        frame = pd.read_parquet(path)
    elif source == "sqlite":
        if path is None:
            raise SystemExit("--input is required for --source sqlite")
        with sqlite3.connect(path) as conn:
            frame = pd.read_sql_query("SELECT * FROM homes", conn)
    else:
        raise SystemExit(f"unknown source {source!r} (csv, db, parquet, sqlite)")

    streetview = enrich_dir(adapter.key) / "streetview_cam.csv"
    if streetview.exists() and "sv_lat" not in frame.columns:
        cameras = pd.read_csv(streetview, dtype={"SWIS": str, "PRINT_KEY": str})
        frame = frame.merge(cameras, on=["SWIS", "PRINT_KEY"], how="left")
    return prepare_frame(frame)


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    drop_geo = [column for column in ("geometry", "geometry_wkt") if column in frame.columns]
    frame = frame.drop(columns=drop_geo)
    for column in ("SWIS", "PRINT_KEY"):
        if column in frame.columns:
            frame[column] = frame[column].map(lambda value: None if pd.isna(value) else str(value))
    for column in APP_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    streetview = [
        column
        for column in STREETVIEW_COLUMNS
        if column in frame.columns and frame[column].notna().any()
    ]
    keep = [column for column in APP_COLUMNS if column not in DROP_BEFORE_ENCODE] + streetview
    return frame.loc[:, keep].reset_index(drop=True)
