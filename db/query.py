"""Read a query into a DataFrame without requiring SQLAlchemy."""

from __future__ import annotations

import pandas as pd
import psycopg

from pipeline.config import database_url


def read_sql(query: str, dsn: str | None = None) -> pd.DataFrame:
    with psycopg.connect(dsn or database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [column.name for column in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=columns)
