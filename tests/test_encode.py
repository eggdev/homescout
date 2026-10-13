import base64
import gzip
import json

import pandas as pd

from app.encode import embed, encode_columns
from pipeline.columns import APP_COLUMNS
from pipeline.config import app_dataset_path, repo_root


def test_csv_header_matches_contract():
    import gzip as gz
    import csv

    path = app_dataset_path("westchester_sf_app_dataset.csv.gz")
    with gz.open(path, "rt", newline="") as handle:
        header = next(csv.reader(handle))
    assert header == APP_COLUMNS


def test_encode_roundtrip_small_frame():
    frame = pd.DataFrame(
        {
            "SWIS": ["552000", "552000"],
            "city_town": ["Bedford", "Bedford"],
            "senior_signal": [True, False],
            "est_price_mid": [730000.0, None],
            "lat": [41.236336, 41.22],
            "lon": [-73.69438, -73.72],
        }
    )
    encoded = encode_columns(frame)
    assert encoded["senior_signal"]["t"] == "b"
    assert encoded["senior_signal"]["v"] == [1, 0]
    assert encoded["city_town"]["d"] == ["Bedford"]
    assert encoded["est_price_mid"]["v"][0] == 730000
    assert encoded["est_price_mid"]["v"][1] is None
    assert encoded["SWIS"]["t"] == "s"
    html, _nbytes = embed("const B64=\"__DATA__\"; const README=__README__;", {"n": 2, "c": encoded}, "hello")
    assert "__DATA__" not in html
    assert "__README__" not in html
    payload = html.split('const B64="', 1)[1].split('"', 1)[0]
    raw = gzip.decompress(base64.b64decode(payload))
    assert json.loads(raw)["n"] == 2


def test_about_text_includes_caveats():
    text = (repo_root() / "docs" / "caveats.md").read_text()
    assert "not an appraisal" in text
    assert "Permits" in text
