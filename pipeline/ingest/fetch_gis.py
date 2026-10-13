"""Download county GIS attributes for the single-family class. No geometry."""

from __future__ import annotations

import time

import pandas as pd
import requests

from pipeline.adapters import get_adapter
from pipeline.config import raw_dir


def main() -> None:
    adapter = get_adapter()
    url = adapter.gis_parcels_query_url()
    ids = requests.get(
        url,
        params={"where": adapter.gis_where(), "returnIdsOnly": "true", "f": "json"},
        timeout=120,
    ).json()["objectIds"]
    ids.sort()
    rows = []
    for start in range(0, len(ids), 1000):
        chunk = ",".join(map(str, ids[start : start + 1000]))
        for _attempt in range(4):
            try:
                payload = requests.post(
                    url,
                    data={
                        "objectIds": chunk,
                        "outFields": adapter.gis_out_fields(),
                        "returnGeometry": "false",
                        "f": "json",
                    },
                    timeout=120,
                ).json()
                rows.extend(feature["attributes"] for feature in payload["features"])
                break
            except Exception:
                time.sleep(3)
    destination = raw_dir(adapter.key, create=True) / "gis_210.csv"
    pd.DataFrame(rows).to_csv(destination, index=False)
    print(len(rows), destination)


if __name__ == "__main__":
    main()
