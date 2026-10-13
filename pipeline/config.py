"""Paths and database URL. Override with environment variables; nothing is hard-coded to a machine path."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("HOMESCOUT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    env = os.environ.get("HOMESCOUT_DATA_DIR")
    return Path(env).expanduser().resolve() if env else repo_root() / "data"


def dist_dir() -> Path:
    env = os.environ.get("HOMESCOUT_DIST_DIR")
    return Path(env).expanduser().resolve() if env else repo_root() / "dist"


def _region_dir(kind: str, region: str, *, create: bool) -> Path:
    path = data_dir() / kind / region
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def raw_dir(region: str, *, create: bool = False) -> Path:
    return _region_dir("raw", region, create=create)


def enrich_dir(region: str, *, create: bool = False) -> Path:
    return _region_dir("enrich", region, create=create)


def out_dir(region: str, *, create: bool = False) -> Path:
    return _region_dir("out", region, create=create)


def overlay_dir(region: str, *, create: bool = False) -> Path:
    return _region_dir("overlays", region, create=create)


def app_dataset_path(filename: str) -> Path:
    return data_dir() / "app" / filename


def database_url() -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    dotenv = repo_root() / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")
    return "postgresql://homescout:homescout@localhost:5432/homescout"


def about_markdown() -> str:
    docs = repo_root() / "docs"
    parts = []
    for name in ("sources.md", "methods.md", "caveats.md"):
        path = docs / name
        if path.exists():
            parts.append(path.read_text())
    return "\n\n".join(parts)
