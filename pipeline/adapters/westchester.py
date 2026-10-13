"""Westchester County, New York.

Deed books from the county clerk are control numbers, not classic liber/page:
book = (year - 1960) * 1000 + day-of-year. 46123 is 2006, day 123 (2006-05-03).
That encoding was checked against parcels whose book changed between the 2021 and
2025 rolls: the new book always fell in 61xxx–65xxx for the matching year.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from pipeline.adapters.base import RegionAdapter
from pipeline.exemptions import flag_nys_exemptions


class WestchesterNY(RegionAdapter):
    key = "westchester_ny"
    state_fips = "36"
    county_fips = "119"
    state_abbr = "NY"
    county_name = "Westchester County"
    roll_year = 2025
    as_of = date(2026, 10, 11)
    swis_prefix = "55"

    def decode_deed_book(self, book) -> date | None:
        try:
            value = float(book)
        except (TypeError, ValueError):
            return None
        if value != value:  # NaN
            return None
        if not (40000 <= value < 70000 and 1 <= (value % 1000) <= 366):
            return None
        year = int(1960 + value // 1000)
        day_of_year = int(value % 1000)
        return date(year, 1, 1) + timedelta(days=day_of_year - 1)

    def derive_deeds(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["BOOK"] = pd.to_numeric(d["BOOK"], errors="coerce")
        books = d["BOOK"]
        ok = (books >= 40000) & (books < 70000) & ((books % 1000) >= 1) & ((books % 1000) <= 366)
        d["deed_year_est"] = np.where(ok, 1960 + books // 1000, np.nan)
        d["deed_date_est"] = pd.NaT
        d.loc[ok, "deed_date_est"] = pd.to_datetime(
            d.loc[ok, "deed_year_est"].astype(int).astype(str) + "-01-01"
        ) + pd.to_timedelta(books[ok] % 1000 - 1, unit="D")
        d["deed_date_est"] = pd.to_datetime(d["deed_date_est"]).dt.date
        d["tenure_years_est"] = np.where(
            ok,
            ((pd.Timestamp(self.as_of) - pd.to_datetime(d["deed_date_est"])).dt.days / 365.25).round(1),
            np.nan,
        )
        d["deed_basis"] = np.where(
            ok,
            "control-number date",
            np.where(
                books.isna(),
                "no deed ref on roll (likely pre-2002 liber era)",
                "old/irregular liber (pre-2002)",
            ),
        )
        d["tenure_20plus"] = np.where(ok, d["tenure_years_est"] >= 20, "likely")
        coverage = d.groupby("CITYTOWN_NAME")["BOOK"].transform(lambda series: series.notna().mean())
        d["tenure_20plus"] = d["tenure_20plus"].astype(str).replace({"True": "yes", "False": "no"})
        low_coverage = (d["tenure_20plus"] == "likely") & (coverage < 0.5)
        d.loc[low_coverage, "tenure_20plus"] = "unknown"
        d.loc[d["tenure_20plus"] == "unknown", "deed_basis"] = (
            "municipality does not report deed refs to roll"
        )
        first_percentile = d.groupby("CITYTOWN_NAME")["deed_year_est"].transform(
            lambda series: series.quantile(0.01)
        )
        d["blank_deed_means_before_year"] = np.where(books.isna(), first_percentile, np.nan)
        return d

    def flag_exemptions(self, codes: pd.Series) -> pd.DataFrame:
        return flag_nys_exemptions(codes)

    def gis_parcels_query_url(self) -> str:
        return (
            "https://giswww.westchestergov.com/ArcGIS/rest/services/"
            "DataHub_TaxParcels/MapServer/0/query"
        )

    def gis_where(self) -> str:
        return f"PROP_CLASS='{self.single_family_class()}'"

    def gis_out_fields(self) -> str:
        return (
            "SWIS,PRINT_KEY,SBL,MUNI_NAME,CITYTOWN_NAME,PARCEL_ADDR,LOC_ZIP,PROP_CLASS,"
            "YR_BLT,SQ_FT,ACRES,CALC_ACRES,SQFT_LIVING,GFA,NBR_KITCHENS,NBR_FULL_BATHS,"
            "NBR_BEDROOMS,BLDG_STYLE_DESC,BOOK,PAGE,PRIMARY_OWNER,ADD_OWNER,OWNER_TYPE,"
            "MAIL_ADDR,MAIL_CITY,MAIL_STATE,MAIL_ZIP,FULL_MARKET_VAL,TOTAL_AV"
        )

    def bbox(self) -> tuple[float, float, float, float]:
        return (-74.05, 40.82, -73.40, 41.45)

    def metric_crs(self) -> str:
        return "EPSG:32618"

    def orpts_resource(self) -> str | None:
        return "7vem-aaz7"

    def orpts_where(self) -> str | None:
        return f"starts_with(swis_code,'{self.swis_prefix}') AND roll_year='{self.roll_year}'"

    def dem_tiles(self) -> list[str]:
        return ["n41w074", "n42w074"]

    def dem_bounds(self) -> tuple[float, float, float, float]:
        return (-74.02, 40.85, -73.43, 41.40)

    def nfhl_envelope(self) -> str:
        return "-73.99,40.87,-73.47,41.37"

    def solar_site(self) -> tuple[float, float, float]:
        return (41.1, -73.78, 100.0)

    def overpass_query(self) -> str | None:
        return """[out:json][timeout:600];(
node["shop"~"supermarket|grocery|greengrocer|convenience"](40.85,-74.0,41.4,-73.45);way["shop"~"supermarket|grocery|greengrocer"](40.85,-74.0,41.4,-73.45);
node["amenity"~"restaurant|cafe|fast_food|bar|pub|pharmacy|library|school|bank"](40.85,-74.0,41.4,-73.45);way["amenity"~"school|library"](40.85,-74.0,41.4,-73.45);
node["highway"="bus_stop"](40.85,-74.0,41.4,-73.45);node["public_transport"="platform"](40.85,-74.0,41.4,-73.45);
node["railway"="station"](40.85,-74.0,41.4,-73.45);
way["leisure"~"park|playground"](40.85,-74.0,41.4,-73.45);node["leisure"~"park|playground"](40.85,-74.0,41.4,-73.45););out center tags;"""

    def app_dataset_filename(self) -> str:
        return "westchester_sf_app_dataset.csv.gz"

    def price_method_version(self) -> str:
        return "rar-zhvi-westchester-2025-v1"

    def gradient_latitude(self) -> float:
        """Latitude used to turn the 3DEP degree grid into meters."""
        return 41.1
