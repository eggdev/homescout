"""Join county GIS attributes to the state assessment roll and derive tenure.

Inputs (data/raw/<region>/): gis_210.csv, raw_210.csv
Outputs (data/out/<region>/): sf_all.csv, sf_tenure20plus.csv, and an xlsx when openpyxl is installed.
Deed dates and exemption flags come from the region adapter.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from pipeline.adapters import get_adapter
from pipeline.config import out_dir, raw_dir


def _norm_addr(series: pd.Series) -> pd.Series:
    return series.fillna("").str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)


def build(adapter=None) -> pd.DataFrame:
    adapter = adapter or get_adapter()
    raw = raw_dir(adapter.key)
    gis = pd.read_csv(raw / "gis_210.csv", dtype=str)
    roll = pd.read_csv(raw / "raw_210.csv", dtype=str)
    exemption_cols = [column for column in roll.columns if re.fullmatch(r"exemption_code_\d+", column)]
    roll["exempt_codes"] = roll[exemption_cols].apply(lambda series: ";".join(series.dropna()), axis=1)
    roll = roll[
        [
            "swis_code",
            "print_key_code",
            "exempt_codes",
            "primary_owner_first_name",
            "primary_owner_last_name",
            "parcel_address_number",
            "parcel_address_street",
            "mailing_address_number",
            "mailing_address_street",
        ]
    ].drop_duplicates(["swis_code", "print_key_code"])
    frame = gis.merge(
        roll,
        left_on=["SWIS", "PRINT_KEY"],
        right_on=["swis_code", "print_key_code"],
        how="left",
    )
    for column in [
        "YR_BLT",
        "SQ_FT",
        "ACRES",
        "CALC_ACRES",
        "SQFT_LIVING",
        "NBR_FULL_BATHS",
        "NBR_BEDROOMS",
        "NBR_KITCHENS",
        "BOOK",
        "PAGE",
        "FULL_MARKET_VAL",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["SQFT_LIVING", "YR_BLT", "NBR_BEDROOMS", "NBR_FULL_BATHS"]:
        frame.loc[frame[column] <= 0, column] = np.nan
    frame = adapter.derive_deeds(frame)
    flags = adapter.flag_exemptions(frame["exempt_codes"])
    frame = pd.concat([frame, flags], axis=1)
    frame["owner_occupied_est"] = (_norm_addr(frame["MAIL_ADDR"]) == _norm_addr(frame["PARCEL_ADDR"])) | frame[
        "basic_star_4185x"
    ] | frame["enhanced_star_4183x"]
    frame["absentee_owner"] = ~frame["owner_occupied_est"]
    frame["trust_or_estate_owner"] = (
        frame["PRIMARY_OWNER"].fillna("").str.upper().str.contains(adapter.trust_name_pattern(), regex=True)
    )
    frame["lot_acres"] = frame["ACRES"].fillna(frame["CALC_ACRES"]).round(3)
    frame["lot_sqft"] = (frame["lot_acres"] * 43560).round()
    frame["permits_matched"] = ""
    frame["permit_flags"] = ""
    renamed = frame.rename(
        columns={
            "CITYTOWN_NAME": "city_town",
            "MUNI_NAME": "municipality",
            "PARCEL_ADDR": "address",
            "LOC_ZIP": "zip",
            "YR_BLT": "year_built",
            "SQFT_LIVING": "living_sqft",
            "NBR_BEDROOMS": "bedrooms",
            "NBR_FULL_BATHS": "full_baths",
            "NBR_KITCHENS": "kitchens",
            "BLDG_STYLE_DESC": "style",
            "PRIMARY_OWNER": "owner",
            "ADD_OWNER": "additional_owner",
            "MAIL_ADDR": "mail_addr",
            "MAIL_CITY": "mail_city",
            "MAIL_STATE": "mail_state",
            "MAIL_ZIP": "mail_zip",
            "FULL_MARKET_VAL": "full_market_value",
            "BOOK": "deed_book",
            "PAGE": "deed_page",
            "exempt_codes": "exemption_codes_4digit",
        }
    )
    columns = [
        "SWIS",
        "PRINT_KEY",
        "SBL",
        "city_town",
        "municipality",
        "address",
        "zip",
        "owner",
        "additional_owner",
        "mail_addr",
        "mail_city",
        "mail_state",
        "mail_zip",
        "owner_occupied_est",
        "absentee_owner",
        "trust_or_estate_owner",
        "deed_book",
        "deed_page",
        "deed_date_est",
        "tenure_years_est",
        "tenure_20plus",
        "deed_basis",
        "blank_deed_means_before_year",
        "exemption_codes_4digit",
        "senior_aged_exemption_4180x",
        "enhanced_star_4183x",
        "senior_signal",
        "basic_star_4185x",
        "veteran_exemption",
        "year_built",
        "living_sqft",
        "bedrooms",
        "full_baths",
        "kitchens",
        "style",
        "lot_acres",
        "lot_sqft",
        "full_market_value",
        "permits_matched",
        "permit_flags",
    ]
    out = renamed[columns].sort_values(["city_town", "address"])
    destination = out_dir(adapter.key, create=True)
    out.to_csv(destination / "sf_all.csv", index=False)
    tenure = out[
        out.tenure_20plus.isin(["yes", "likely"]) | ((out.tenure_20plus == "unknown") & out.senior_signal)
    ]
    tenure.to_csv(destination / "sf_tenure20plus.csv", index=False)
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("openpyxl not installed; skipped sf_tenure20plus.xlsx")
    else:
        with pd.ExcelWriter(destination / "sf_tenure20plus.xlsx", engine="openpyxl") as writer:
            tenure.to_excel(writer, sheet_name="tenure20plus", index=False)
            sheet = writer.sheets["tenure20plus"]
            sheet.auto_filter.ref = sheet.dimensions
            sheet.freeze_panes = "A2"
            summary = out.groupby("city_town").agg(
                parcels=("SWIS", "size"),
                tenure20_yes=("tenure_20plus", lambda series: (series == "yes").sum()),
                tenure20_likely=("tenure_20plus", lambda series: (series == "likely").sum()),
                tenure_unknown=("tenure_20plus", lambda series: (series == "unknown").sum()),
                senior_signal=("senior_signal", "sum"),
                has_sqft=("living_sqft", lambda series: series.notna().sum()),
            )
            summary.to_excel(writer, sheet_name="summary")
    print(
        len(out),
        (out.tenure_20plus == "yes").sum(),
        (out.tenure_20plus == "likely").sum(),
        len(tenure),
        destination,
    )
    return out


def main() -> None:
    build()


if __name__ == "__main__":
    main()
