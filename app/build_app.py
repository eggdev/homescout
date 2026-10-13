"""Build the desktop single-file Leaflet app from the same table as the mobile app."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.build_mobile import _name
from app.encode import embed, encode_columns
from app.sources import load_app_frame
from pipeline.adapters import get_adapter
from pipeline.config import about_markdown, dist_dir


def build(source: str, path: Path | None, output: Path | None, region: str | None) -> Path:
    adapter = get_adapter(region)
    frame = load_app_frame(source, path, adapter.key)
    payload = {"n": len(frame), "c": encode_columns(frame)}
    template = Path(__file__).with_name("template.html").read_text()
    html, raw_bytes = embed(template, payload, about_markdown())
    destination = output or dist_dir() / _name(adapter.key, mobile=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html)
    print(
        f"rows {payload['n']} json_mb {raw_bytes / 1e6:.2f} html_mb {destination.stat().st_size / 1e6:.2f} -> {destination}"
    )
    return destination


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the single-file desktop app")
    parser.add_argument("--source", choices=("csv", "db", "parquet", "sqlite"), default="csv")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--region", default=None)
    args = parser.parse_args(argv)
    build(args.source, args.input, args.output, args.region)


if __name__ == "__main__":
    main()
