"""Widget catalogue with a deliberately uncached, recomputed lookup path."""

from __future__ import annotations

WIDGETS = {f"w{i}": {"name": f"Widget {i}", "price": i * 3} for i in range(100)}


def lookup_widget(widget_id: str) -> dict[str, object]:
    """Recomputes a derived view on every call — the seeded inefficiency."""
    widget = WIDGETS[widget_id]
    return {**widget, "display": f"{widget['name']} (${widget['price']})"}
