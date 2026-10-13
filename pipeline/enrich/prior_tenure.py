"""For trust and estate owners, look at the 2021–2024 rolls for the owner before the current deed.

Same surname on the prior deed is treated as continued family tenure. Deed books are
decoded with the region adapter. Historical owner files are data/raw/<region>/owners_YYYY.csv.
"""

from __future__ import annotations

import re

import pandas as pd

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir, out_dir, raw_dir

STOP = set(
    "TRUST TRUSTEE TRUSTEES REVOCABLE IRREVOCABLE LIVING FAMILY THE OF ESTATE LIFE EST REV IRREV IRR TR TRS TTEE AND JR SR LLC INC".split()
)
TRUST_TYPES = ["Revocable/Living trust", "Irrevocable trust", "Other trust", "Estate", "Life estate"]


def words(value) -> set[str]:
    return {word for word in re.findall(r"[A-Z]{3,}", str(value).upper()) if word not in STOP}


def _display_name(row) -> str:
    first, last, extra = [
        str(value).strip() if pd.notna(value) else ""
        for value in (row.primary_owner_first_name, row.primary_owner_last_name, row.additional_owner_1_last_name)
    ]
    parts = [first, last]
    if extra and extra.upper() != last.upper() and extra.upper() not in (first + " " + last).upper():
        parts.append(extra)
    out = []
    for word in " ".join(parts).split():
        if not out or out[-1].upper() != word.upper():
            out.append(word)
    return " ".join(out)


def main() -> None:
    adapter = get_adapter()
    folder = enrich_dir(adapter.key)
    raw = raw_dir(adapter.key)
    owners = pd.read_csv(folder / "owner_types.csv", dtype=str)
    current = pd.read_csv(raw / "gis_210.csv", dtype=str)[["SWIS", "PRINT_KEY", "BOOK"]].drop_duplicates(
        ["SWIS", "PRINT_KEY"]
    )
    owners = owners.merge(current, on=["SWIS", "PRINT_KEY"], how="left")
    trusts = owners[owners.owner_type.isin(TRUST_TYPES)].copy()
    history = {}
    for year in [2024, 2023, 2022, 2021]:
        historic = pd.read_csv(raw / f"owners_{year}.csv", dtype=str).drop_duplicates(
            ["swis_code", "print_key_code"]
        )
        historic["n"] = historic.apply(_display_name, axis=1)
        history[year] = historic.set_index(["swis_code", "print_key_code"])[["deed_book", "n"]]
    thresholds = (
        pd.read_csv(
            out_dir(adapter.key) / "sf_all_enriched.csv",
            usecols=["SWIS", "city_town", "blank_deed_means_before_year"],
            dtype={"SWIS": str},
        )
        .dropna()
        .groupby("city_town")
        .blank_deed_means_before_year.max()
    )
    towns = (
        pd.read_csv(raw / "gis_210.csv", usecols=["SWIS", "PRINT_KEY", "CITYTOWN_NAME"], dtype=str)
        .drop_duplicates(["SWIS", "PRINT_KEY"])
        .set_index(["SWIS", "PRINT_KEY"])
        .CITYTOWN_NAME
    )
    output = []
    for _, row in trusts.iterrows():
        key = (row.SWIS, row.PRINT_KEY)
        current_words = words(row.owner_text)
        prior = None
        for year in [2024, 2023, 2022, 2021]:
            if key not in history[year].index:
                continue
            book, name = history[year].loc[key]
            current_book = None if pd.isna(row.BOOK) else str(row.BOOK).replace(".0", "")
            if pd.notna(row.BOOK) and (pd.isna(book) or str(book) != current_book):
                prior = (book, str(name).strip(), year)
                break
        if not prior:
            output.append(
                (
                    row.SWIS,
                    row.PRINT_KEY,
                    None,
                    None,
                    None,
                    "unknown",
                    "No deed change 2021-2025 visible in rolls (trust deed predates 2021, or no deed ref)",
                )
            )
            continue
        book, name, year = prior
        also_trust = bool(re.search(r"TRUST|ESTATE|LIFE EST|TTEE|TRUSTEE", name.upper()))
        confidence = "same surname" if (current_words & words(name)) else "different"
        decoded = adapter.decode_deed_book(book)
        prior_year = decoded.year if decoded else None
        lower_bound = None
        if decoded:
            family_years = round((pd.Timestamp(adapter.as_of) - pd.Timestamp(decoded)).days / 365.25, 1)
        else:
            lower_bound = thresholds.get(towns.get(key), 2003)
            family_years = float(adapter.as_of.year - lower_bound)
        note = f"Before this deed: {name} (roll {year}), prior deed " + (
            decoded.isoformat() if decoded else f"before {int(lower_bound)} (older than county digital records)"
        )
        if also_trust:
            note += "; prior owner was also a trust/estate"
        output.append(
            (
                row.SWIS,
                row.PRINT_KEY,
                name,
                prior_year if prior_year else (f"<{int(lower_bound)}" if lower_bound else None),
                family_years if confidence == "same surname" else None,
                confidence,
                note,
            )
        )
    result = pd.DataFrame(
        output,
        columns=[
            "SWIS",
            "PRINT_KEY",
            "pre_trust_owner",
            "pre_trust_deed_year",
            "family_tenure_years",
            "family_confidence",
            "prior_owner_note",
        ],
    )
    result["family_tenure_is_min"] = result.pre_trust_deed_year.astype(str).str.startswith("<")
    destination = folder / "prior_tenure.csv"
    result.to_csv(destination, index=False)
    print(result.family_confidence.value_counts().to_string())
    print(destination)


if __name__ == "__main__":
    main()
