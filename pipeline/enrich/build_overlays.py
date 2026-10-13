"""Write the map overlays the mobile app embeds: school-district polygons and Metro-North stations.

Requires a TIGER unified-school-district zip and osm_pois.csv in data/enrich/<region>/.
Geopandas is optional and imported only when this script runs.
"""

from __future__ import annotations

import pandas as pd

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir, overlay_dir, out_dir


def main() -> None:
    import geopandas as gpd

    adapter = get_adapter()
    folder = enrich_dir(adapter.key)
    homes_path = out_dir(adapter.key) / "app_dataset.csv"
    if not homes_path.exists():
        homes_path = out_dir(adapter.key) / "sf_all_enriched.csv"
    homes = pd.read_csv(homes_path, usecols=["school_district_tiger"], low_memory=False)
    districts = gpd.read_file("zip://" + str(folder / adapter.tiger_unsd_filename())).to_crs(4326)
    districts = districts[districts.NAME.isin(homes.school_district_tiger.dropna().unique())][["NAME", "geometry"]]
    districts["geometry"] = districts.geometry.simplify(0.0004)
    destination = overlay_dir(adapter.key, create=True)
    (destination / "school_districts.geojson").write_text(districts.to_json())
    pois = pd.read_csv(folder / "osm_pois.csv")
    stations = pois[
        (pois.cat == "rail_station")
        & pois.network.fillna("").str.contains("Metro-North")
        & ~pois.network.fillna("").str.contains("NJ")
        & pois.name.notna()
    ]
    stations[["name", "lat", "lon"]].to_csv(destination / "metro_north.csv", index=False)
    print(len(districts), "districts", len(stations), "stations", destination)


if __name__ == "__main__":
    main()
