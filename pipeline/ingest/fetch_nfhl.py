"""FEMA NFHL flood polygons (SFHA and 0.2% zone) intersecting the county envelope."""

from __future__ import annotations

import json
import time

import requests

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir


def main() -> None:
    adapter = get_adapter()
    url = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
    base = {
        "geometry": adapter.nfhl_envelope(),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "where": "SFHA_TF='T' OR ZONE_SUBTY LIKE '%0.2%' OR FLD_ZONE='D'",
    }
    ids = sorted(
        requests.get(url, params={**base, "returnIdsOnly": "true", "f": "json"}, timeout=300).json()["objectIds"]
    )
    features = []
    for start in range(0, len(ids), 100):
        chunk = ",".join(map(str, ids[start : start + 100]))
        for _attempt in range(5):
            try:
                payload = requests.post(
                    url,
                    data={
                        "objectIds": chunk,
                        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
                        "outSR": 4326,
                        "geometryPrecision": 6,
                        "f": "geojson",
                    },
                    timeout=300,
                ).json()
                features.extend(payload["features"])
                break
            except Exception as exc:
                print(exc)
                time.sleep(10)
    destination = enrich_dir(adapter.key, create=True) / "nfhl.geojson"
    destination.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(len(ids), len(features), destination)


if __name__ == "__main__":
    main()
