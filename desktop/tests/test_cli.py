"""Smoke tests for the D0-001 desktop skeleton."""

from market_monitor import __version__
from market_monitor.cli import main


def test_package_version_is_pinned() -> None:
    assert __version__ == "0.1.0"


def test_main_returns_success(capsys) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "skeleton ready" in out
