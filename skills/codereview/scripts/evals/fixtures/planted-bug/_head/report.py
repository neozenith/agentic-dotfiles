"""Build the summary payload returned by /report."""

import os

from stats import average, total


def summarize(rows: list[dict]) -> dict:
    values = [r["value"] for r in rows if r.get("active")]
    return {"total": total(values), "avg": average(values)}
