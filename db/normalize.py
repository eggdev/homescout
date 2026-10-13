"""Parse the flat app CSV into Python values. Empty fields become None."""

from __future__ import annotations

import csv
import gzip
from datetime import date
from pathlib import Path

from pipeline.columns import APP_COLUMNS, BOOL_COLUMNS, DOT_ZERO_ID_COLUMNS, FLOAT_COLUMNS


def open_csv(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", newline="")
    return open(path, newline="")


def parse_bool(value: str) -> bool | None:
    if value is None or value == "":
        return None
    if value in ("True", "true", "1"):
        return True
    if value in ("False", "false", "0"):
        return False
    raise ValueError(f"not a boolean: {value!r}")


def parse_float(value: str) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def parse_text(value: str) -> str | None:
    if value is None or value == "":
        return None
    return value


def parse_id(value: str) -> str | None:
    text = parse_text(value)
    if text and text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def parse_date(value: str) -> date | None:
    text = parse_text(value)
    if text is None:
        return None
    return date.fromisoformat(text[:10])


def parse_row(raw: dict[str, str]) -> dict:
    parsed = {}
    for column in APP_COLUMNS:
        value = raw.get(column, "")
        if column in BOOL_COLUMNS:
            parsed[column] = parse_bool(value)
        elif column in FLOAT_COLUMNS:
            parsed[column] = parse_float(value)
        elif column == "deed_date_est":
            parsed[column] = parse_date(value)
        elif column in DOT_ZERO_ID_COLUMNS:
            parsed[column] = parse_id(value)
        else:
            parsed[column] = parse_text(value)
    return parsed


def read_app_csv(path: Path) -> list[dict]:
    with open_csv(path) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != APP_COLUMNS:
            got = reader.fieldnames or []
            missing = [column for column in APP_COLUMNS if column not in got]
            extra = [column for column in got if column not in APP_COLUMNS]
            raise SystemExit(
                f"{path} header does not match the app contract. missing={missing} extra={extra}"
            )
        return [parse_row(row) for row in reader]
