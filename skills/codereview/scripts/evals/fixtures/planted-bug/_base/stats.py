"""Aggregation helpers for the reporting endpoint."""


def total(values: list[float]) -> float:
    return sum(values)
