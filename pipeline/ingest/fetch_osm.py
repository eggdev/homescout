"""OSM amenities inside the county via Overpass. Prefer osm_extract.py for the Geofabrik PBF."""

from __future__ import annotations

import json

import requests

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir


def main() -> None:
    adapter = get_adapter()
    query = adapter.overpass_query()
    if not query:
        raise SystemExit(f"{adapter.key} has no Overpass query")
    destination = enrich_dir(adapter.key, create=True) / "osm.json"
    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "homescout/0.1 (public-records research)"},
        timeout=900,
    )
    response.raise_for_status()
    payload = response.json()
    destination.write_text(json.dumps(payload))
    print(len(payload["elements"]), destination)


if __name__ == "__main__":
    main()
