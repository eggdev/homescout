"""Export app_homes to SQLite and GeoParquet (WKB point, EPSG:4326)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from db.query import read_sql
from pipeline.adapters import get_adapter
from pipeline.config import out_dir

GEO_METADATA = {
    "version": "1.1.0",
    "primary_column": "geometry",
    "columns": {
        "geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
            "crs": {"id": {"authority": "EPSG", "code": 4326}},
            "edges": "planar",
        }
    },
}


def read_app_homes(dsn: str | None = None) -> pd.DataFrame:
    return read_sql("SELECT * FROM app_homes", dsn)


def _wkb_point(lon, lat) -> bytes | None:
    if pd.isna(lon) or pd.isna(lat):
        return None
    return struct.pack("<BIdd", 1, 1, float(lon), float(lat))


def export_sqlite(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    table = frame.copy()
    table["geometry_wkt"] = [
        None if pd.isna(lat) or pd.isna(lon) else f"POINT({float(lon)} {float(lat)})"
        for lat, lon in zip(table["lat"], table["lon"])
    ]
    with sqlite3.connect(path) as conn:
        table.to_sql("homes", conn, index=False)
        conn.execute("CREATE TABLE export_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO export_meta (key, value) VALUES ('rows', ?), ('geometry', 'geometry_wkt EPSG:4326')",
            (str(len(table)),),
        )


def export_geoparquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    geometry = pa.array(
        [_wkb_point(lon, lat) for lon, lat in zip(frame["lon"], frame["lat"])],
        type=pa.binary(),
    )
    table = pa.Table.from_pandas(frame, preserve_index=False)
    table = table.append_column("geometry", geometry)
    metadata = dict(table.schema.metadata or {})
    metadata[b"geo"] = json.dumps(GEO_METADATA).encode()
    table = table.replace_schema_metadata(metadata)
    pq.write_table(table, path)


def export_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export app_homes to SQLite and GeoParquet")
    parser.add_argument("--region", default=None)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--sqlite", type=Path)
    parser.add_argument("--geoparquet", type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    adapter = get_adapter(args.region)
    folder = out_dir(adapter.key, create=True)
    sqlite_path = args.sqlite or folder / "app_homes.sqlite"
    parquet_path = args.geoparquet or folder / "app_homes.parquet"
    csv_path = args.csv or folder / "app_homes.csv"
    frame = read_app_homes(args.database_url)
    export_sqlite(frame, sqlite_path)
    export_geoparquet(frame, parquet_path)
    export_csv(frame, csv_path)
    print(f"exported {len(frame)} rows")
    print(f"  sqlite     {sqlite_path}")
    print(f"  geoparquet {parquet_path}")
    print(f"  csv        {csv_path}")


if __name__ == "__main__":
    main()
