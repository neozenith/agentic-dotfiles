"""Pure-logic core.

NO FastAPI imports allowed in this package. The >=90% coverage gate is meant
to load on this surface, not on framework glue. Keep functions deterministic
and easy to test exhaustively.
"""

from __future__ import annotations


def echo(message: str) -> str:
    """Trim whitespace and return the message unchanged otherwise.

    Placeholder for real domain logic — replace with whatever the app needs.
    """
    return message.strip()
