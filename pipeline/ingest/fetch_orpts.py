"""Page the state assessment roll (NYS ORPTS on data.ny.gov) into raw_210.csv.

The adapter's orpts_where is the county filter. Rows are kept when a property-class
column is present and equals the adapter's single-family class; if the roll uses a
different column name, every returned row is kept and a warning is printed.
"""

from __future__ import annotations

import pandas as pd
import requests

from pipeline.adapters import get_adapter
from pipeline.config import raw_dir

CLASS_COLUMNS = ("property_class_code", "prop_class", "property_class", "prop_class_code")
PAGE = 50_000


def main() -> None:
    adapter = get_adapter()
    resource = adapter.orpts_resource()
    where = adapter.orpts_where()
    if not resource or not where:
        raise SystemExit(f"{adapter.key} has no assessment-roll resource")
    url = f"https://data.ny.gov/resource/{resource}.json"
    frames = []
    offset = 0
    while True:
        response = requests.get(
            url,
            params={"$where": where, "$limit": PAGE, "$offset": offset},
            timeout=180,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        print(f"fetched {offset + len(batch)}")
        if len(batch) < PAGE:
            break
        offset += PAGE
    if not frames:
        raise SystemExit("assessment roll returned no rows")
    frame = pd.concat(frames, ignore_index=True)
    class_column = next((column for column in CLASS_COLUMNS if column in frame.columns), None)
    if class_column:
        frame = frame[frame[class_column].astype(str) == adapter.single_family_class()]
    else:
        print("no property-class column in the roll response; kept every row from orpts_where")
    destination = raw_dir(adapter.key, create=True) / "raw_210.csv"
    frame.to_csv(destination, index=False)
    print(len(frame), destination)


if __name__ == "__main__":
    main()
