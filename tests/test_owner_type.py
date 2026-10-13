import pandas as pd

from pipeline.enrich.owner_type import classify_owners


def _row(primary, additional=""):
    return {"PRIMARY_OWNER": primary, "ADD_OWNER": additional, "roll_names": ""}


def test_owner_type_patterns():
    frame = pd.DataFrame(
        [
            _row("Smith, John"),
            _row("Smith Family Revocable Trust"),
            _row("Jones Irrevocable Trust"),
            _row("Estate of Jones"),
            _row("Acme LLC"),
            _row("West, John"),
            _row("Palmesi Life Estate"),
        ]
    )
    classified = classify_owners(frame)
    assert classified.owner_type.tolist() == [
        "Individual(s)",
        "Revocable/Living trust",
        "Irrevocable trust",
        "Estate",
        "LLC/corporation",
        "Individual(s)",
        "Life estate",
    ]
