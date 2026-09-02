"""Report writing. HTML is concatenated inline; layout changes are code changes."""

import sys
from pathlib import Path

from .loader import load_orders
from .transform import revenue_by_region


def render(totals: dict[str, float]) -> str:
    rows = "".join(f"<tr><td>{region}</td><td>{amount:.2f}</td></tr>" for region, amount in sorted(totals.items()))
    return "<html><body><h1>Revenue by region</h1><table>" + rows + "</table></body></html>"


def main(argv: list[str]) -> int:
    src, dst = Path(argv[1]), Path(argv[2])
    dst.write_text(render(revenue_by_region(load_orders(src))), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
