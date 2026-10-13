"""Parcel representative points (WGS84) from the county GIS."""

from __future__ import annotations

import time

import pandas as pd
import requests
from shapely.geometry import shape

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir


def main() -> None:
    adapter = get_adapter()
    url = adapter.gis_parcels_query_url()
    ids = sorted(
        requests.get(
            url,
            params={"where": adapter.gis_where(), "returnIdsOnly": "true", "f": "json"},
            timeout=120,
        ).json()["objectIds"]
    )
    rows = []
    for start in range(0, len(ids), 500):
        chunk = ",".join(map(str, ids[start : start + 500]))
        for _attempt in range(5):
            try:
                payload = requests.post(
                    url,
                    data={
                        "objectIds": chunk,
                        "outFields": "SWIS,PRINT_KEY",
                        "returnGeometry": "true",
                        "outSR": 4326,
                        "geometryPrecision": 6,
                        "f": "geojson",
                    },
                    timeout=180,
                ).json()
                for feature in payload["features"]:
                    properties = feature["properties"]
                    try:
                        point = shape(feature["geometry"]).representative_point()
                        rows.append((properties["SWIS"], properties["PRINT_KEY"], point.y, point.x))
                    except Exception:
                        rows.append((properties["SWIS"], properties["PRINT_KEY"], None, None))
                break
            except Exception:
                time.sleep(5)
    destination = enrich_dir(adapter.key, create=True) / "centroids.csv"
    pd.DataFrame(rows, columns=["SWIS", "PRINT_KEY", "lat", "lon"]).to_csv(destination, index=False)
    print(len(rows), destination)


if __name__ == "__main__":
    main()
