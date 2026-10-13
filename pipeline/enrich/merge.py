"""Attach enrichment fields and the town-level price estimate to the tenure extracts.

Price recipe (Westchester prototype): total assessed value / 2025 NYS residential
assessment ratio, moved forward with Zillow ZHVI, range +/- 1.5 x the town COD.
Inputs in data/enrich/<region>/: enrich_fields.csv, centroids.csv, rar.csv, equity.csv, zhvi_county.csv.
Roll and GIS inputs in data/raw/<region>/. Tenure files in data/out/<region>/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir, out_dir, raw_dir


def main() -> None:
    adapter = get_adapter()
    folder = enrich_dir(adapter.key)
    raw = raw_dir(adapter.key)
    output = out_dir(adapter.key, create=True)
    fields = pd.read_csv(
        folder / "enrich_fields.csv",
        dtype={"SWIS": str, "PRINT_KEY": str, "school_district_geoid": str, "tract_geoid": str},
    ).drop(columns=["lat", "lon"])
    fields = fields.merge(
        pd.read_csv(folder / "centroids.csv", dtype=str)[["SWIS", "PRINT_KEY", "lat", "lon"]].drop_duplicates(
            ["SWIS", "PRINT_KEY"]
        ),
        on=["SWIS", "PRINT_KEY"],
        how="left",
    )
    gis = pd.read_csv(raw / "gis_210.csv", dtype={"SWIS": str, "PRINT_KEY": str})[
        ["SWIS", "PRINT_KEY", "TOTAL_AV"]
    ].drop_duplicates(["SWIS", "PRINT_KEY"])
    roll = (
        pd.read_csv(raw / "raw_210.csv", dtype=str)[["swis_code", "print_key_code", "school_district_name"]]
        .drop_duplicates(["swis_code", "print_key_code"])
        .rename(
            columns={
                "swis_code": "SWIS",
                "print_key_code": "PRINT_KEY",
                "school_district_name": "school_district_roll",
            }
        )
    )
    ratios = pd.read_csv(folder / "rar.csv", dtype={"swis_code": str})
    ratios = ratios[(ratios.rate_year == adapter.roll_year) & (ratios.type != "Village")].set_index(
        "swis_code"
    ).residential_assessment_ratio
    equity = pd.read_csv(folder / "equity.csv", dtype={"swis_code": str})
    equity = (
        equity[equity.survey_year == adapter.roll_year]
        .drop_duplicates("swis_code")
        .set_index("swis_code")
        .residential_coefficient_of_dispersion
    )
    zhvi = pd.read_csv(folder / "zhvi_county.csv")
    county = zhvi[(zhvi.RegionName == adapter.county_name) & (zhvi.State == adapter.state_abbr)].iloc[0]
    date_columns = [column for column in county.index if str(column)[:2] == "20"]
    latest = date_columns[-1]
    base = "2024-07-31"
    appreciation = county[latest] / county[base]
    gis["town_swis"] = gis.SWIS.str[:4] + "00"
    gis["rar_2025_pct"] = gis.town_swis.map(ratios)
    gis["cod_pct"] = gis.town_swis.map(equity).fillna(equity.median())
    gis["market_value_2024_from_rar"] = (
        pd.to_numeric(gis.TOTAL_AV, errors="coerce") / (gis.rar_2025_pct / 100)
    ).round(-3)
    gis["est_price_mid"] = (gis.market_value_2024_from_rar * appreciation).round(-3)
    gis["est_price_low"] = (gis.est_price_mid * (1 - 1.5 * gis.cod_pct / 100)).round(-3)
    gis["est_price_high"] = (gis.est_price_mid * (1 + 1.5 * gis.cod_pct / 100)).round(-3)
    gis.loc[gis.est_price_mid <= 0, ["est_price_mid", "est_price_low", "est_price_high"]] = np.nan
    place = adapter.county_name.removesuffix(" County")
    gis["price_method"] = (
        f"AV / {adapter.roll_year} NYS RAR (town) x Zillow ZHVI {place} "
        f"{base}->{latest} ({appreciation:.3f}); range +/-1.5x town residential COD"
    )
    attached = fields.merge(roll, on=["SWIS", "PRINT_KEY"], how="left").merge(
        gis.drop(columns=["TOTAL_AV", "town_swis"]), on=["SWIS", "PRINT_KEY"], how="left"
    )
    enriched = None
    for name in ("sf_all", "sf_tenure20plus"):
        table = pd.read_csv(output / f"{name}.csv", dtype={"SWIS": str, "PRINT_KEY": str}, low_memory=False)
        table = table.merge(attached, on=["SWIS", "PRINT_KEY"], how="left")
        table["est_price_per_sqft"] = (table.est_price_mid / table.living_sqft).round(0)
        table.to_csv(output / f"{name}_enriched.csv", index=False)
        print(name, len(table))
        enriched = table
    coverage = enriched.notna().mean().round(3)
    coverage.to_csv(output / "coverage_tenure20plus_enriched.csv", header=["share_nonblank"])
    summary = enriched.groupby("city_town").agg(
        parcels=("SWIS", "size"),
        tenure20_yes=("tenure_20plus", lambda series: (series == "yes").sum()),
        tenure20_likely=("tenure_20plus", lambda series: (series == "likely").sum()),
        senior_signal=("senior_signal", "sum"),
        median_sqft=("living_sqft", "median"),
        median_est_price=("est_price_mid", "median"),
        median_walk_proxy=("walk_proxy_0_100", "median"),
        median_mn_dist_mi=("metro_north_dist_mi", "median"),
        in_100yr_flood=("fema_sfha_100yr", "sum"),
        median_solar_index=("solar_terrain_index", "median"),
        median_slope_deg=("slope_deg", "median"),
    )
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("openpyxl not installed; skipped xlsx")
    else:
        with pd.ExcelWriter(output / "sf_tenure20plus_enriched.xlsx", engine="openpyxl") as writer:
            enriched.to_excel(writer, sheet_name="tenure20plus", index=False)
            sheet = writer.sheets["tenure20plus"]
            sheet.auto_filter.ref = sheet.dimensions
            sheet.freeze_panes = "C2"
            summary.to_excel(writer, sheet_name="town_summary")
            writer.sheets["town_summary"].auto_filter.ref = writer.sheets["town_summary"].dimensions
            coverage.rename("share_nonblank").to_frame().to_excel(writer, sheet_name="field_coverage")
    print(appreciation, latest)


if __name__ == "__main__":
    main()
