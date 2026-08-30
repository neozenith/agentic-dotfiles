"""CSV loading. Reads the whole export into memory and trusts every row."""

import csv
from pathlib import Path


def load_orders(path: Path) -> list[dict[str, str]]:
    """Read every order row into a list; a malformed row raises and kills the run."""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        # No schema validation: a missing column surfaces later as a KeyError.
        row["amount"] = row["amount"].strip()
    return rows
