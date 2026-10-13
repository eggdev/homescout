"""Build the mobile single-file MapLibre app.

Reads the database, the committed CSV, or an export. School-district polygons
and Metro-North station points are embedded when overlay files exist; otherwise
those layers are empty and the parcel-level station name and distance remain.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.encode import embed, encode_columns
from app.sources import load_app_frame
from pipeline.adapters import get_adapter
from pipeline.config import about_markdown, dist_dir, overlay_dir


def load_overlays(region: str) -> dict:
    folder = overlay_dir(region)
    districts = folder / "school_districts.geojson"
    stations = folder / "metro_north.csv"
    if districts.exists():
        school_geojson = json.loads(districts.read_text())
    else:
        school_geojson = {"type": "FeatureCollection", "features": []}
    metro = []
    if stations.exists():
        table = pd.read_csv(stations)
        metro = [
            [name, round(float(lat), 5), round(float(lon), 5)]
            for name, lat, lon in table[["name", "lat", "lon"]].itertuples(index=False, name=None)
        ]
    return {"sd": school_geojson, "mn": metro}


def build(source: str, path: Path | None, output: Path | None, region: str | None) -> Path:
    adapter = get_adapter(region)
    frame = load_app_frame(source, path, adapter.key)
    payload = {"n": len(frame), "c": encode_columns(frame), "x": load_overlays(adapter.key)}
    template = Path(__file__).with_name("template_mobile.html").read_text()
    html, raw_bytes = embed(template, payload, about_markdown())
    destination = output or dist_dir() / _name(adapter.key, mobile=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html)
    print(
        f"rows {payload['n']} json_mb {raw_bytes / 1e6:.2f} html_mb {destination.stat().st_size / 1e6:.2f} -> {destination}"
    )
    return destination


def _name(region: str, *, mobile: bool) -> str:
    if region == "westchester_ny":
        return "westchester_homes_mobile.html" if mobile else "westchester_homes.html"
    return f"{region}_homes_mobile.html" if mobile else f"{region}_homes.html"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the single-file mobile app")
    parser.add_argument("--source", choices=("csv", "db", "parquet", "sqlite"), default="csv")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--region", default=None)
    args = parser.parse_args(argv)
    build(args.source, args.input, args.output, args.region)


if __name__ == "__main__":
    main()
