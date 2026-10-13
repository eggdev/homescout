"""USGS 3DEP 1/3 arc-second DEM for the county, read from the public COG tiles."""

from __future__ import annotations

import rasterio

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir


def main() -> None:
    adapter = get_adapter()
    sources = [
        rasterio.open(
            "/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/"
            f"{tile}/USGS_13_{tile}.tif"
        )
        for tile in adapter.dem_tiles()
    ]
    west, south, east, north = adapter.dem_bounds()
    from rasterio.merge import merge

    array, transform = merge(sources, bounds=(west, south, east, north))
    profile = sources[0].profile
    profile.update(
        height=array.shape[1],
        width=array.shape[2],
        transform=transform,
        driver="GTiff",
        compress="deflate",
        tiled=True,
        count=1,
        blockxsize=256,
        blockysize=256,
    )
    destination = enrich_dir(adapter.key, create=True) / "dem.tif"
    with rasterio.open(destination, "w", **profile) as dataset:
        dataset.write(array[0], 1)
    print(array.shape, destination)


if __name__ == "__main__":
    main()
