"""Apply db/migrations/*.sql in order. Each file records itself in schema_migrations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
from psycopg.errors import UndefinedTable

from pipeline.config import database_url

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def _statements(script: str) -> list[str]:
    """Split a migration on semicolons that are not inside comments or quotes."""
    cleaned = []
    for line in script.splitlines():
        if line.strip().startswith("--"):
            continue
        if "--" in line:
            line = line.split("--", 1)[0]
        cleaned.append(line)
    text = "\n".join(cleaned)
    statements: list[str] = []
    buf: list[str] = []
    in_quote = False
    i = 0
    while i < len(text):
        char = text[i]
        if char == "'":
            if in_quote and i + 1 < len(text) and text[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_quote = not in_quote
            buf.append(char)
        elif char == ";" and not in_quote:
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
        else:
            buf.append(char)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def applied_versions(conn) -> set[str]:
    try:
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    except UndefinedTable:
        conn.rollback()
        return set()
    return {row[0] for row in rows}


def apply_migrations(dsn: str | None = None) -> list[str]:
    dsn = dsn or database_url()
    applied_now: list[str] = []
    with psycopg.connect(dsn) as conn:
        done = applied_versions(conn)
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            statements = _statements(path.read_text())
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
            applied_now.append(path.name)
    return applied_now


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Apply HomeScout SQL migrations")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    dsn = args.database_url or database_url()
    try:
        applied = apply_migrations(dsn)
    except psycopg.OperationalError as exc:
        sys.exit(f"Could not connect to Postgres ({dsn.split('@')[-1]}): {exc}")
    if applied:
        print("applied " + ", ".join(applied))
    else:
        print("migrations already current")


if __name__ == "__main__":
    main()
