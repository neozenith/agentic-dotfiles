#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for mermaid_complexity.py"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import mermaid_complexity as mc
import pytest

SIMPLE_FLOWCHART = """\
flowchart LR
    A[Start] --> B[Process]
    B --> C[End]
"""

COMPLEX_FLOWCHART = """\
flowchart LR
    subgraph Ingress
        dns[DNS] --> cdn[CDN]
    end
    subgraph Web
        alb[Load Balancer] --> w1[Web 1]
        alb --> w2[Web 2]
    end
    subgraph App
        api[API] --> db[(DB)]
        api --> cache[Cache]
        worker[Worker] --> db
    end
    cdn --> alb
    w1 --> api
    w2 --> api
"""


@pytest.fixture
def temp_dir() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def simple_mmd(temp_dir: Path) -> Path:
    f = temp_dir / "simple.mmd"
    f.write_text(SIMPLE_FLOWCHART)
    return f


@pytest.fixture
def complex_mmd(temp_dir: Path) -> Path:
    f = temp_dir / "complex.mmd"
    f.write_text(COMPLEX_FLOWCHART)
    return f


class TestParseMermaidFile:
    def test_simple_node_count(self) -> None:
        stats = mc.parse_mermaid_file(SIMPLE_FLOWCHART)
        assert stats.nodes == 3

    def test_simple_edge_count(self) -> None:
        stats = mc.parse_mermaid_file(SIMPLE_FLOWCHART)
        assert stats.edges == 2

    def test_no_subgraphs(self) -> None:
        stats = mc.parse_mermaid_file(SIMPLE_FLOWCHART)
        assert stats.subgraphs == 0
        assert stats.max_subgraph_depth == 0

    def test_subgraph_detection(self) -> None:
        stats = mc.parse_mermaid_file(COMPLEX_FLOWCHART)
        assert stats.subgraphs == 3

    def test_subgraph_names(self) -> None:
        stats = mc.parse_mermaid_file(COMPLEX_FLOWCHART)
        assert "Ingress" in stats.subgraph_names
        assert "Web" in stats.subgraph_names
        assert "App" in stats.subgraph_names

    def test_ignores_comments(self) -> None:
        content = "flowchart LR\n%% This is a comment\n    A --> B\n"
        stats = mc.parse_mermaid_file(content)
        assert stats.edges == 1

    def test_empty_diagram(self) -> None:
        stats = mc.parse_mermaid_file("flowchart LR\n")
        assert stats.nodes == 0
        assert stats.edges == 0


class TestCalculateComplexity:
    def test_vcs_increases_with_nodes(self) -> None:
        config = mc.ThresholdConfig()
        stats_small = mc.parse_mermaid_file(SIMPLE_FLOWCHART)
        stats_large = mc.parse_mermaid_file(COMPLEX_FLOWCHART)
        m_small = mc.calculate_complexity(stats_small, config)
        m_large = mc.calculate_complexity(stats_large, config)
        assert m_large["visual_complexity_score"] > m_small["visual_complexity_score"]

    def test_formula_breakdown_keys(self) -> None:
        config = mc.ThresholdConfig()
        stats = mc.parse_mermaid_file(SIMPLE_FLOWCHART)
        metrics = mc.calculate_complexity(stats, config)
        assert "visual_complexity_score" in metrics
        assert "edge_density" in metrics
        assert "cyclomatic_complexity" in metrics
        assert "vcs_breakdown" in metrics

    def test_edge_density_bounded(self) -> None:
        config = mc.ThresholdConfig()
        stats = mc.parse_mermaid_file(COMPLEX_FLOWCHART)
        metrics = mc.calculate_complexity(stats, config)
        assert 0 <= metrics["edge_density"] <= 1


class TestRateComplexity:
    def test_simple_is_ideal(self) -> None:
        config = mc.ThresholdConfig.from_preset("high")
        stats = mc.parse_mermaid_file(SIMPLE_FLOWCHART)
        metrics = mc.calculate_complexity(stats, config)
        rating, color = mc.rate_complexity(metrics["visual_complexity_score"], stats.nodes, config)
        assert rating == "ideal"
        assert color == "green"

    def test_rating_values(self) -> None:
        config = mc.ThresholdConfig.from_preset("low")
        # Force critical: many nodes
        content = "flowchart LR\n" + "\n".join(f"    N{i} --> N{i + 1}" for i in range(50))
        stats = mc.parse_mermaid_file(content)
        metrics = mc.calculate_complexity(stats, config)
        rating, _ = mc.rate_complexity(metrics["visual_complexity_score"], stats.nodes, config)
        assert rating in ("complex", "critical")


class TestThresholdConfig:
    def test_preset_aliases(self) -> None:
        assert mc.ThresholdConfig.from_preset("l").preset_name == "low-density"
        assert mc.ThresholdConfig.from_preset("med").preset_name == "medium-density"
        assert mc.ThresholdConfig.from_preset("h").preset_name == "high-density"

    def test_low_stricter_than_high(self) -> None:
        low = mc.ThresholdConfig.from_preset("low")
        high = mc.ThresholdConfig.from_preset("high")
        assert low.node_acceptable < high.node_acceptable
        assert low.vcs_acceptable < high.vcs_acceptable

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            mc.ThresholdConfig.from_preset("nonexistent")

    def test_from_env_preset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MERMAID_COMPLEXITY_PRESET", "low-density")
        config = mc.ThresholdConfig.from_env()
        assert config.preset_name == "low-density"


class TestAnalyzeFile:
    def test_returns_complexity_report(self, simple_mmd: Path) -> None:
        config = mc.ThresholdConfig()
        report = mc.analyze_file(simple_mmd, config)
        assert isinstance(report, mc.ComplexityReport)
        assert report.nodes == 3
        assert report.edges == 2

    def test_file_path_stored(self, simple_mmd: Path) -> None:
        report = mc.analyze_file(simple_mmd, mc.ThresholdConfig())
        assert report.file_path == str(simple_mmd)

    def test_complex_diagram_needs_subdivision_with_low_preset(self, temp_dir: Path) -> None:
        # 15 nodes exceeds low-density node_acceptable (12) — subdivision required
        big = temp_dir / "big.mmd"
        big.write_text("flowchart LR\n" + "\n".join(f"    N{i} --> N{i + 1}" for i in range(15)))
        config = mc.ThresholdConfig.from_preset("low")
        report = mc.analyze_file(big, config)
        assert report.needs_subdivision is True
        assert report.recommended_subdivisions >= 2


class TestMain:
    def test_analyze_single_file(self, monkeypatch: pytest.MonkeyPatch, simple_mmd: Path) -> None:
        monkeypatch.setattr(sys, "argv", ["mermaid_complexity.py", str(simple_mmd)])
        result = mc.main()
        assert result == 0

    def test_exit_code_1_on_complex(self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
        # Create a diagram that will fail low-density thresholds
        big = temp_dir / "big.mmd"
        big.write_text("flowchart LR\n" + "\n".join(f"    N{i} --> N{i + 1}" for i in range(40)))
        monkeypatch.setattr(sys, "argv", ["mermaid_complexity.py", str(big), "--preset", "low"])
        result = mc.main()
        assert result == 1

    def test_json_output(
        self, monkeypatch: pytest.MonkeyPatch, simple_mmd: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["mermaid_complexity.py", str(simple_mmd), "--json"])
        mc.main()
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["nodes"] == 3

    def test_directory_input(self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
        (temp_dir / "a.mmd").write_text(SIMPLE_FLOWCHART)
        (temp_dir / "b.mmd").write_text(SIMPLE_FLOWCHART)
        monkeypatch.setattr(sys, "argv", ["mermaid_complexity.py", str(temp_dir)])
        result = mc.main()
        assert result == 0

    def test_no_files_returns_1(self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
        monkeypatch.setattr(sys, "argv", ["mermaid_complexity.py", str(temp_dir)])
        result = mc.main()
        assert result == 1


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    sys.exit(pytest.main([__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]))
