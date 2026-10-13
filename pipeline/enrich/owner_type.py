"""Classify owner type from GIS and assessment-roll name fields.

Patterns are the prototype's, tuned on Westchester names (trusts, estates, LLCs).
A new county with different naming habits should adjust the patterns here or
subclass the step; see docs/adding-a-county.md.
"""

from __future__ import annotations

import re

import pandas as pd

from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir, raw_dir

PATTERNS = {
    "Revocable/Living trust": (
        r"\b(?:REVOCABLE|REVOC|REVO|REV|LIVING|LIV)\b.{0,25}(?:TRUST|\bTRUS\b|\bTR\b|\bTRST\b|\bTRS\b)"
        r"|\bRLT\b|LIVINGTRUST|REVTRUST|\bREV\.? ?TR"
    ),
    "Irrevocable trust": r"\bIRREV\w*|\bIRRVOC\w*|\bIRRE\b|\bIRRV\b|\bIRR\b|\bIRR\.|\bQPRT\b|\bQUALIFIED PERSONAL RESIDENCE",
    "Other trust": (
        r"TRUST|\bTRUS\b|\(TRUS|\bTRU\s*(?:\||$)|\bFAM(?:ILY)? TR\b|\bTRUSTEES?\b|\bTTEES?\b|\bTRSTE?E?S?\b"
        r"|\bTRST\b|\bTRS\b|\bAS TR\b|\bTR\b(?=\s*($|\||,|U/?A|UAD|DTD|OF\b))|\bFAMILY TR\b|\bU/?A\b|\bUAD\b|\bU/D/T\b|\bUDT\b"
    ),
    "Life estate": r"\bLIFE ?EST(ATE)?\b|\bL/E\b|\(LE\)|\bLE\b\s*(\||$)|\bLIFE TENANT\b|\bLIFE USE\b",
    "Estate": r"\bESTATE OF\b|\bEST OF\b|\bESTATE\b|\bEXECUT(OR|RIX)\b|\bEXEC\b|\bEXR\b|\bADMINISTRAT(OR|RIX)\b|\bADMIN\b|\bHEIRS?\b|\bDECEASED\b|\bDEC\'?D\b|\bEST\b(?=\s*($|\|))",
    "LLC/corporation": (
        r"\bL\.?L\.?C\.?\b|REAL ESTATE|\bBK\b|\bN\.?A\.?\s*(?:\||$)|\bINC\.?\b|\bCORP(ORATION)?\b|\bL\.?P\.?\b"
        r"|\bLTD\b|\bCO\b\s*(\||$)|\bCOMPANY\b|\bHOLDINGS?\b|\bPROPERTIES\b|\bREALTY\b|\bASSOC(IATES|IATION)?\b"
        r"|\bPARTNERS(HIP)?\b|\bBANK\b|\bCHURCH\b|\bMORTGAGE\b|\bFEDERAL\b|\bSOCIETY\b"
    ),
}
ORDER = [
    "Life estate",
    "Estate",
    "Revocable/Living trust",
    "Irrevocable trust",
    "Other trust",
    "LLC/corporation",
]


def classify_owners(frame: pd.DataFrame) -> pd.DataFrame:
    """frame needs PRIMARY_OWNER, ADD_OWNER, and roll_names. Returns owner_type and owner_flags."""
    work = frame.copy()
    work["owner_text"] = (
        work["PRIMARY_OWNER"].fillna("") + " | " + work["ADD_OWNER"].fillna("") + " | " + work["roll_names"].fillna("")
    ).str.upper().str.replace(r"\s+", " ", regex=True)
    text = work["owner_text"]
    realty = text.str.replace(r"REAL ESTATE", "REALTY", regex=True)
    for label, pattern in PATTERNS.items():
        work["m_" + label] = (realty if label == "Estate" else text).str.contains(pattern, regex=True)
    work["owner_type"] = "Individual(s)"
    for label in reversed(ORDER):
        work.loc[work["m_" + label], "owner_type"] = label
    estate_and_company = (
        (work["owner_type"] == "Estate")
        & work["m_LLC/corporation"]
        & ~text.str.contains(r"ESTATE OF|EXECUT|ADMINISTRAT|HEIRS")
    )
    work.loc[estate_and_company, "owner_type"] = "LLC/corporation"
    work["owner_flags"] = work[["m_" + label for label in ORDER]].apply(
        lambda matched: ";".join(label for label, flag in zip(ORDER, matched) if flag),
        axis=1,
    )
    return work


def main() -> None:
    adapter = get_adapter()
    raw = raw_dir(adapter.key)
    gis = pd.read_csv(raw / "gis_210.csv", dtype=str)[
        ["SWIS", "PRINT_KEY", "PRIMARY_OWNER", "ADD_OWNER"]
    ].drop_duplicates(["SWIS", "PRINT_KEY"])
    roll = pd.read_csv(raw / "raw_210.csv", dtype=str).drop_duplicates(["swis_code", "print_key_code"])
    name_columns = [
        column
        for column in roll.columns
        if re.match(r"(primary_owner|additional_owner_\d)_(first|mi|last)", column)
    ]
    roll["roll_names"] = roll[name_columns].fillna("").agg(" ".join, axis=1)
    merged = gis.merge(
        roll[["swis_code", "print_key_code", "roll_names"]],
        left_on=["SWIS", "PRINT_KEY"],
        right_on=["swis_code", "print_key_code"],
        how="left",
    )
    classified = classify_owners(merged)
    destination = enrich_dir(adapter.key, create=True) / "owner_types.csv"
    classified[["SWIS", "PRINT_KEY", "owner_type", "owner_flags", "owner_text"]].to_csv(destination, index=False)
    print(classified.owner_type.value_counts().to_string())
    print(destination)


if __name__ == "__main__":
    main()
