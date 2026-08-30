"""Aggregation. Single-threaded, single pass, no per-stage timing."""

from collections import defaultdict


def revenue_by_region(rows: list[dict[str, str]]) -> dict[str, float]:
    """Sum order amounts per region; bad numerics abort the whole batch."""
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[row["region"]] += float(row["amount"])  # ValueError kills the night
    return dict(totals)
