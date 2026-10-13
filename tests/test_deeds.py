from datetime import date

import pandas as pd

from pipeline.adapters.westchester import WestchesterNY


def test_control_number_46123():
    adapter = WestchesterNY()
    assert adapter.decode_deed_book(46123) == date(2006, 5, 3)
    assert adapter.decode_deed_book("65100") == date(2025, 4, 10)


def test_undecodable_books():
    adapter = WestchesterNY()
    for book in (None, "", "nope", float("nan"), 39999, 70000, 46000, 40000):
        assert adapter.decode_deed_book(book) is None


def test_vectorized_matches_scalar_and_coverage_rule():
    adapter = WestchesterNY()
    rows = []
    for book in (46123, None, 65100, 30000):
        rows.append({"BOOK": book, "CITYTOWN_NAME": "Bedford"})
    for _ in range(9):
        rows.append({"BOOK": None, "CITYTOWN_NAME": "Quiet"})
    rows.append({"BOOK": 46123, "CITYTOWN_NAME": "Quiet"})
    derived = adapter.derive_deeds(pd.DataFrame(rows))

    assert derived.loc[0, "deed_date_est"] == date(2006, 5, 3)
    assert derived.loc[0, "tenure_20plus"] == "yes"
    assert derived.loc[0, "deed_basis"] == "control-number date"
    assert derived.loc[0, "tenure_years_est"] == 20.4
    assert derived.loc[1, "tenure_20plus"] == "likely"
    assert "pre-2002" in derived.loc[1, "deed_basis"]
    assert derived.loc[2, "tenure_20plus"] == "no"
    assert derived.loc[2, "deed_date_est"] == adapter.decode_deed_book(65100)
    assert derived.loc[3, "deed_basis"] == "old/irregular liber (pre-2002)"
    quiet = derived[derived.CITYTOWN_NAME == "Quiet"]
    blanks = quiet[quiet.BOOK.isna()]
    assert set(blanks.tenure_20plus) == {"unknown"}
    assert set(blanks.deed_basis) == {"municipality does not report deed refs to roll"}
    assert quiet.loc[quiet.BOOK.notna(), "tenure_20plus"].iloc[0] == "yes"
