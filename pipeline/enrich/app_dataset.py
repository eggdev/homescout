"""App dataset = 20+ year owners (including senior-signal unknowns) plus every trust, estate, and life estate.

Reads the enriched all-homes file, owner types, and prior-tenure file.
Writes data/out/<region>/app_dataset.csv. The committed Westchester extract is
data/app/westchester_sf_app_dataset.csv.gz; pass --publish to gzip a replacement there.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from pipeline.adapters import get_adapter
from pipeline.config import app_dataset_path, enrich_dir, out_dir

TRUST_TYPES = ["Revocable/Living trust", "Irrevocable trust", "Other trust", "Estate", "Life estate"]


def build_app_dataset(adapter=None) -> pd.DataFrame:
    adapter = adapter or get_adapter()
    folder = enrich_dir(adapter.key)
    output = out_dir(adapter.key)
    homes = pd.read_csv(output / "sf_all_enriched.csv", low_memory=False, dtype={"SWIS": str, "PRINT_KEY": str})
    owners = pd.read_csv(folder / "owner_types.csv", dtype=str)[["SWIS", "PRINT_KEY", "owner_type", "owner_flags"]]
    prior = pd.read_csv(folder / "prior_tenure.csv", dtype={"SWIS": str, "PRINT_KEY": str})
    homes = homes.merge(owners, on=["SWIS", "PRINT_KEY"], how="left").merge(prior, on=["SWIS", "PRINT_KEY"], how="left")
    trust = homes.owner_type.isin(TRUST_TYPES)
    long_tenure = homes.tenure_20plus.isin(["yes", "likely"]) | (
        (homes.tenure_20plus == "unknown") & homes.senior_signal
    )
    homes["why_included"] = np.select(
        [long_tenure & trust, long_tenure, trust],
        ["20+ yr owner; " + homes.owner_type.fillna(""), "20+ yr owner", "Trust/estate owner (any tenure)"],
        "",
    )
    homes["owner_group"] = np.where(
        homes.owner_type.str.contains("trust", case=False, na=False),
        "Trust",
        np.where(homes.owner_type.isin(["Estate", "Life estate"]), homes.owner_type, homes.owner_type),
    )
    homes["family_tenure_combined_yrs"] = np.where(
        homes.family_confidence == "same surname",
        np.fmax(homes.family_tenure_years, homes.tenure_years_est.fillna(0)),
        homes.tenure_years_est,
    )
    homes["family_tenure_combined_is_min"] = np.where(
        homes.family_confidence == "same surname",
        homes.family_tenure_is_min.fillna(False),
        False,
    )
    homes["deed_recorded_year"] = pd.to_datetime(homes.deed_date_est, errors="coerce").dt.year
    homes["trust_or_estate_owner"] = trust
    included = homes[long_tenure | trust]
    destination = output / "app_dataset.csv"
    included.to_csv(destination, index=False)
    print(len(included), destination)
    return included


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the app extract from enriched outputs")
    parser.add_argument("--region", default=None)
    parser.add_argument("--publish", action="store_true", help="Also gzip the extract to data/app/")
    args = parser.parse_args()
    adapter = get_adapter(args.region)
    frame = build_app_dataset(adapter)
    if args.publish:
        destination = app_dataset_path(adapter.app_dataset_filename())
        frame.to_csv(destination, index=False, compression="gzip")
        print(destination)


if __name__ == "__main__":
    main()
