"""Column-dictionary encoding used by the single-file apps.

Mirrors the prototype build: booleans packed as 0/1, numbers rounded, and
repeated strings stored once. Identifier-like columns stay strings so a GEOID
is not turned into a float.
"""

from __future__ import annotations

import base64
import gzip
import json

import pandas as pd

from pipeline.columns import STRING_ID_COLUMNS


def encode_columns(frame: pd.DataFrame) -> dict:
    columns = {}
    for name in frame.columns:
        series = frame[name]
        present = series.dropna()
        if len(present) and set(present.unique()) <= {True, False}:
            columns[name] = {
                "t": "b",
                "v": [None if pd.isna(value) else int(bool(value)) for value in series],
            }
            continue
        if pd.api.types.is_numeric_dtype(series) and name not in STRING_ID_COLUMNS:
            if name in ("lat", "lon"):
                decimals = 5
            elif name in ("lot_acres", "metro_north_dist_mi", "sky_view_factor", "cod_pct", "rar_2025_pct"):
                decimals = 2
            elif name in ("sv_lat", "sv_lon"):
                decimals = 6
            else:
                decimals = 1
            rounded = series.round(decimals)
            columns[name] = {
                "t": "n",
                "v": [
                    None if pd.isna(value) else (int(value) if float(value).is_integer() else float(value))
                    for value in rounded
                ],
            }
            continue
        text = series.astype("string").str.replace(r"\.0$", "", regex=True)
        uniques = sorted(text.dropna().unique().tolist())
        index = {value: position for position, value in enumerate(uniques)}
        columns[name] = {
            "t": "s",
            "d": uniques,
            "v": [None if pd.isna(value) else index[value] for value in text],
        }
    return columns


def embed(template: str, payload: dict, readme: str) -> tuple[str, int]:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    encoded = base64.b64encode(gzip.compress(raw, 9)).decode()
    html = template.replace("__DATA__", encoded).replace(
        "__README__", json.dumps(readme).replace("</", "<\\/")
    )
    return html, len(raw)
