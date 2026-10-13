"""New York assessment-roll exemption flags.

ORPTS publishes exemption codes truncated to 4 digits on data.ny.gov.
4180x is the aged exemption (41800–41809), 4183x is Enhanced STAR (41834, age 65+),
4185x is Basic STAR, and 411x is the veteran series. Other states should not reuse this.
"""

from __future__ import annotations

import pandas as pd


def flag_nys_exemptions(codes: pd.Series) -> pd.DataFrame:
    text = codes.fillna("")
    senior_aged = text.str.contains(r"\b4180", regex=True)
    enhanced_star = text.str.contains(r"\b4183", regex=True)
    basic_star = text.str.contains(r"\b4185", regex=True)
    veteran = text.str.contains(r"\b411[0-9]", regex=True)
    return pd.DataFrame(
        {
            "senior_aged_exemption_4180x": senior_aged,
            "enhanced_star_4183x": enhanced_star,
            "basic_star_4185x": basic_star,
            "veteran_exemption": veteran,
            "senior_signal": senior_aged | enhanced_star,
        },
        index=codes.index,
    )
