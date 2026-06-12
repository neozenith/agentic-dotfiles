import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from widgets import lookup_widget


def test_lookup_widget() -> None:
    assert lookup_widget("w3")["display"] == "Widget 3 ($9)"
