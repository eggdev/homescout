"""Per-region adapter interface.

County-specific pieces — deed-book date decoding, GIS and assessment-roll
endpoints, bounding boxes, projected CRS, terrain tiles — live on a
RegionAdapter. Shared stages (classify exemptions for NYS, encode the app,
load the database) call the adapter instead of branching on a county name.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class RegionAdapter(ABC):
    key: str
    state_fips: str
    county_fips: str
    state_abbr: str
    county_name: str
    roll_year: int
    as_of: date
    # Stable sub-county code prefix (NY SWIS county digits). None outside that scheme.
    swis_prefix: str | None = None

    @abstractmethod
    def decode_deed_book(self, book) -> date | None:
        """Recording date encoded in one deed-book control number, or None."""

    @abstractmethod
    def derive_deeds(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add deed date, tenure, and basis columns. Input must include BOOK and CITYTOWN_NAME."""

    @abstractmethod
    def flag_exemptions(self, codes: pd.Series) -> pd.DataFrame:
        """Boolean senior/veteran/STAR flags from the county's exemption-code strings."""

    def gis_parcels_query_url(self) -> str:
        raise NotImplementedError(f"{self.key} has no parcel GIS endpoint")

    def gis_where(self) -> str:
        raise NotImplementedError(f"{self.key} has no parcel GIS filter")

    def gis_out_fields(self) -> str:
        raise NotImplementedError(f"{self.key} has no parcel GIS field list")

    def bbox(self) -> tuple[float, float, float, float]:
        """West, south, east, north in WGS84."""
        raise NotImplementedError(f"{self.key} has no bounding box")

    def metric_crs(self) -> str:
        """Projected CRS used for distance and slope (for example EPSG:32618)."""
        raise NotImplementedError(f"{self.key} has no metric CRS")

    def orpts_resource(self) -> str | None:
        """Socrata resource id for the state assessment roll, if this state publishes one."""
        return None

    def orpts_where(self) -> str | None:
        return None

    def single_family_class(self) -> str:
        return "210"

    def dem_tiles(self) -> list[str]:
        raise NotImplementedError(f"{self.key} has no DEM tile list")

    def dem_bounds(self) -> tuple[float, float, float, float]:
        """West, south, east, north passed to rasterio.merge."""
        raise NotImplementedError(f"{self.key} has no DEM bounds")

    def nfhl_envelope(self) -> str:
        """Esri envelope 'xmin,ymin,xmax,ymax' in WGS84 for the NFHL query."""
        raise NotImplementedError(f"{self.key} has no NFHL envelope")

    def solar_site(self) -> tuple[float, float, float]:
        """Representative lat, lon, altitude (m) for the clear-sky sun path."""
        raise NotImplementedError(f"{self.key} has no solar site")

    def overpass_query(self) -> str | None:
        return None

    def tiger_unsd_filename(self) -> str:
        return f"tl_2024_{self.state_fips}_unsd.zip"

    def tiger_tract_filename(self) -> str:
        return f"tl_2024_{self.state_fips}_tract.zip"

    def app_dataset_filename(self) -> str:
        return f"{self.key}_app_dataset.csv.gz"

    def price_method_version(self) -> str:
        return f"{self.key}-price-v1"

    def trust_name_pattern(self) -> str:
        return r"TRUST|ESTATE|EST OF|TRSTE|TRUSTEE|LIFE EST"
