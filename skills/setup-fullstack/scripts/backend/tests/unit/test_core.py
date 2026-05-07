"""Unit tests for server.core — pure logic, no HTTP."""

from __future__ import annotations

from server.core import echo


def test_echo_strips_whitespace() -> None:
    assert echo("  hello  ") == "hello"


def test_echo_passthrough() -> None:
    assert echo("hi") == "hi"


def test_echo_strips_only_outer_whitespace() -> None:
    assert echo("  hello world  ") == "hello world"


def test_echo_handles_empty_after_strip() -> None:
    assert echo("   ") == ""
