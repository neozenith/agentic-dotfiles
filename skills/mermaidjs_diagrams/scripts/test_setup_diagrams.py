#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for setup_diagrams.py"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
import setup_diagrams


@pytest.fixture
def temp_dir() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestSetupInfrastructure:
    def test_creates_directory(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        assert target.is_dir()

    def test_creates_makefile(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        assert (target / "Makefile").exists()

    def test_makefile_uses_tabs(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        assert "\tnpx" in (target / "Makefile").read_text()

    def test_makefile_icon_packs_empty_by_default(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        content = (target / "Makefile").read_text()
        # Flowcharts use Font Awesome natively — no icon pack default
        line = next(ln for ln in content.splitlines() if ln.startswith("ICON_PACKS ?="))
        assert line.strip() == "ICON_PACKS ?="

    def test_creates_gitattributes(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        assert (target / ".gitattributes").exists()

    def test_creates_readme(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        readme = (target / "README.md").read_text()
        assert "flowchart" in readme.lower()

    def test_does_not_overwrite_existing_files(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        setup_diagrams.setup_diagrams_infrastructure(target)
        makefile = target / "Makefile"
        makefile.write_text("# sentinel")
        setup_diagrams.setup_diagrams_infrastructure(target)
        assert makefile.read_text() == "# sentinel"

    def test_default_target_is_docs_diagrams(self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
        monkeypatch.chdir(temp_dir)
        setup_diagrams.setup_diagrams_infrastructure(None)
        assert (temp_dir / "docs" / "diagrams").is_dir()

    def test_returns_existing_mmd_files(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        target.mkdir()
        (target / "arch.mmd").write_text("flowchart LR\n  A --> B")
        (target / "data.mmd").write_text("flowchart LR\n  C --> D")
        mmd_files, _ = setup_diagrams.setup_diagrams_infrastructure(target)
        assert len(mmd_files) == 2

    def test_returns_empty_for_new_dir(self, temp_dir: Path) -> None:
        target = temp_dir / "new_diagrams"
        mmd_files, _ = setup_diagrams.setup_diagrams_infrastructure(target)
        assert mmd_files == []

    def test_returns_diagrams_dir(self, temp_dir: Path) -> None:
        target = temp_dir / "diagrams"
        _, diagrams_dir = setup_diagrams.setup_diagrams_infrastructure(target)
        assert diagrams_dir == target


class TestMain:
    def test_default_creates_docs_diagrams(self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
        monkeypatch.chdir(temp_dir)
        monkeypatch.setattr(sys, "argv", ["setup_diagrams.py"])
        assert setup_diagrams.main() == 0
        assert (temp_dir / "docs" / "diagrams").is_dir()

    def test_target_folder_arg(self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
        target = str(temp_dir / "custom")
        monkeypatch.setattr(sys, "argv", ["setup_diagrams.py", "--target-folder", target])
        assert setup_diagrams.main() == 0
        assert Path(target).is_dir()

    def test_help_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["setup_diagrams.py", "--help"]
            setup_diagrams.main()
        assert exc.value.code == 0


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    sys.exit(pytest.main([__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]))
