"""Build the summary payload returned by /report."""

from stats import total


def summarize(rows: list[dict]) -> dict:
    values = [r["value"] for r in rows if r.get("active")]
    return {"total": total(values)}
