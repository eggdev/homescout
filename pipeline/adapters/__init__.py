"""County adapters. Pipeline stages call these instead of hard-coding a jurisdiction."""

from __future__ import annotations

import os

from pipeline.adapters.base import RegionAdapter
from pipeline.adapters.westchester import WestchesterNY

ADAPTERS: dict[str, type[RegionAdapter]] = {
    WestchesterNY.key: WestchesterNY,
}


def get_adapter(key: str | None = None) -> RegionAdapter:
    key = key or os.environ.get("HOMESCOUT_REGION", "westchester_ny")
    try:
        cls = ADAPTERS[key]
    except KeyError as exc:
        known = ", ".join(sorted(ADAPTERS))
        raise KeyError(f"Unknown region adapter {key!r}. Known adapters: {known}") from exc
    return cls()


def list_adapters() -> list[str]:
    return sorted(ADAPTERS)
