#!/usr/bin/env python3
"""
Mermaid Diagram Complexity Analyzer

Deterministically scores Mermaid diagrams based on cognitive load research.
Provides recommendations for subdivision when diagrams exceed visual clarity thresholds.

Research basis:
- Huang et al. (2020): "Scalability of Network Visualisation from a Cognitive Load Perspective"
  https://arxiv.org/abs/2008.07944
- Key finding: 50 nodes is difficulty threshold, 100 nodes is hard limit
- Cyclomatic complexity: E - N + 2P (edges - nodes + 2×components)

Configuration (in order of precedence):
1. CLI arguments (--node-acceptable=40)
2. Environment variables (MERMAID_COMPLEXITY_NODE_ACCEPTABLE=40)
3. .env file in current directory
4. Preset defaults (strict, balanced, permissive)

Usage:
    python .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py path/to/diagram.mmd
    python .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/  # Analyze all .mmd files
    python .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/*.mmd --show-working

    # With custom thresholds
    python .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/ --node-target=30 --vcs-target=50
    MERMAID_NODE_TARGET=30 python .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.py docs/diagrams/
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import NamedTuple


# =============================================================================
# Configuration System
# =============================================================================

# Threshold presets by detail density: low < medium < high (default, research-backed)
# Density refers to how many nodes/edges are acceptable per diagram
PRESETS: dict[str, dict[str, int | float]] = {
    # Low density - simple, focused diagrams with minimal nodes
    # Use when: executive summaries, quick reference, embedded diagrams, overviews
    "low-density": {
        "node_ideal": 8,
        "node_acceptable": 12,
        "node_complex": 20,
        "node_hard_limit": 35,
        "vcs_ideal": 15,
        "vcs_acceptable": 25,
        "vcs_complex": 40,
        "vcs_critical": 60,
        "node_target": 10,
        "vcs_target": 20,
    },
    # Medium density - balanced for most documentation
    # Use when: README diagrams, component docs, API overviews
    "medium-density": {
        "node_ideal": 12,
        "node_acceptable": 20,
        "node_complex": 35,
        "node_hard_limit": 60,
        "vcs_ideal": 25,
        "vcs_acceptable": 40,
        "vcs_complex": 70,
        "vcs_critical": 100,
        "node_target": 15,
        "vcs_target": 30,
    },
    # High density - research-backed maximum limits (default)
    # Use when: detailed architecture docs, comprehensive system diagrams
    "high-density": {
        "node_ideal": 20,
        "node_acceptable": 35,
        "node_complex": 50,
        "node_hard_limit": 100,
        "vcs_ideal": 35,
        "vcs_acceptable": 60,
        "vcs_complex": 100,
        "vcs_critical": 150,
        "node_target": 25,
        "vcs_target": 40,
    },
}

# Aliases for convenience
PRESETS["low"] = PRESETS["low-density"]
PRESETS["med"] = PRESETS["medium-density"]
PRESETS["medium"] = PRESETS["medium-density"]
PRESETS["high"] = PRESETS["high-density"]
PRESETS["l"] = PRESETS["low-density"]
PRESETS["m"] = PRESETS["medium-density"]
PRESETS["h"] = PRESETS["high-density"]
PRESETS["default"] = PRESETS["high-density"]
# Legacy aliases for backwards compatibility
PRESETS["strict"] = PRESETS["low-density"]
PRESETS["balanced"] = PRESETS["medium-density"]
PRESETS["permissive"] = PRESETS["high-density"]


@dataclass
class ThresholdConfig:
    """Configuration for complexity thresholds. All values are tunable."""

    # Node count thresholds (based on Huang et al. research)
    node_ideal: int = 20  # Easily comprehensible
    node_acceptable: int = 35  # Manageable with effort
    node_complex: int = 50  # Significant difficulty (research threshold)
    node_hard_limit: int = 100  # Cognitive overload limit

    # Visual Complexity Score (VCS) thresholds
    vcs_ideal: int = 35  # Clear and easily digestible
    vcs_acceptable: int = 60  # Moderate cognitive effort required
    vcs_complex: int = 100  # Needs subdivision consideration
    vcs_critical: int = 150  # Strongly recommend subdivision

    # Subdivision targets (for calculating recommended splits)
    node_target: int = 25  # Target nodes per sub-diagram
    vcs_target: int = 40  # Target VCS per sub-diagram

    # VCS formula weights
    edge_weight: float = 0.5  # Edges are easier to trace than nodes
    subgraph_weight: float = 3.0  # Nested structures add complexity
    depth_weight: float = 0.1  # Per-level depth multiplier

    # Track which preset was used (for display)
    preset_name: str = "high-density"

    @classmethod
    def from_preset(cls, name: str) -> "ThresholdConfig":
        """Create config from a named preset."""
        name = name.lower()
        if name not in PRESETS:
            valid = ["low-density", "medium-density", "high-density"]
            raise ValueError(f"Unknown preset '{name}'. Valid: {valid}")
        preset = PRESETS[name]
        # Normalize alias to canonical name
        canonical_map = {
            "l": "low-density", "low": "low-density", "strict": "low-density",
            "m": "medium-density", "med": "medium-density", "medium": "medium-density", "balanced": "medium-density",
            "h": "high-density", "high": "high-density", "permissive": "high-density", "default": "high-density",
        }
        canonical = canonical_map.get(name, name)
        return cls(
            node_ideal=int(preset["node_ideal"]),
            node_acceptable=int(preset["node_acceptable"]),
            node_complex=int(preset["node_complex"]),
            node_hard_limit=int(preset["node_hard_limit"]),
            vcs_ideal=int(preset["vcs_ideal"]),
            vcs_acceptable=int(preset["vcs_acceptable"]),
            vcs_complex=int(preset["vcs_complex"]),
            vcs_critical=int(preset["vcs_critical"]),
            node_target=int(preset["node_target"]),
            vcs_target=int(preset["vcs_target"]),
            preset_name=canonical,
        )

    @classmethod
    def from_env(
        cls, env_prefix: str = "MERMAID_COMPLEXITY_", base_preset: str = "high-density"
    ) -> ThresholdConfig:
        """Load configuration from environment variables, starting from a preset."""
        # Check for preset in environment first
        preset_name = os.environ.get(f"{env_prefix}PRESET", base_preset)
        config = cls.from_preset(preset_name)

        # Override with individual env vars
        for field_name in config.__dataclass_fields__:
            if field_name == "preset_name":
                continue
            env_key = f"{env_prefix}{field_name.upper()}"
            if env_key in os.environ:
                value = os.environ[env_key]
                field_type = config.__dataclass_fields__[field_name].type
                if field_type is float:
                    setattr(config, field_name, float(value))
                elif field_type is int:
                    setattr(config, field_name, int(value))
                config.preset_name = "custom"  # Mark as customized
        return config

    @classmethod
    def load_dotenv(cls, path: Path | None = None) -> None:
        """Load .env file into environment (simple implementation)."""
        env_path = path or Path(".env")
        if not env_path.exists():
            # Also check parent directories up to 3 levels
            for parent in [Path.cwd()] + list(Path.cwd().parents)[:3]:
                candidate = parent / ".env"
                if candidate.exists():
                    env_path = candidate
                    break
            else:
                return  # No .env found

        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if key.startswith("MERMAID_COMPLEXITY_"):
                        os.environ.setdefault(key, value)


# Global config instance (will be initialized in main)
CONFIG: ThresholdConfig = ThresholdConfig()


# =============================================================================
# Data Structures
# =============================================================================


class MermaidStats(NamedTuple):
    """Raw statistics from Mermaid diagram parsing."""

    nodes: int
    edges: int
    subgraphs: int
    max_subgraph_depth: int
    node_ids: list[str]
    subgraph_names: list[str]


@dataclass
class SubdivisionWorkingOut:
    """Detailed calculation breakdown for subdivision recommendation."""

    # Input values
    nodes: int
    vcs: float
    subgraphs: int

    # Threshold comparisons
    nodes_exceeds_acceptable: bool
    nodes_exceeds_complex: bool
    vcs_exceeds_acceptable: bool

    # Individual calculations
    node_based_splits: int
    node_based_formula: str
    vcs_based_splits: int
    vcs_based_formula: str

    # Subgraph adjustment
    subgraph_adjusted_splits: int
    subgraph_adjustment_reason: str

    # Final recommendation
    final_splits: int
    needs_subdivision: bool

    # Recursive analysis (if applicable)
    estimated_per_split: list[dict] = field(default_factory=list)


@dataclass
class ComplexityReport:
    """Complexity analysis report for a Mermaid diagram."""

    file_path: str

    # Raw counts
    nodes: int
    edges: int
    subgraphs: int
    max_depth: int

    # Computed metrics
    visual_complexity_score: float
    edge_density: float
    cyclomatic_complexity: int

    # VCS formula breakdown
    vcs_formula: str
    vcs_breakdown: dict

    # Thresholds and ratings
    rating: str  # "ideal", "acceptable", "complex", "critical"
    color: str  # "green", "yellow", "orange", "red"

    # Recommendations
    needs_subdivision: bool
    recommended_subdivisions: int
    subdivision_rationale: str
    working_out: SubdivisionWorkingOut | None

    # Metadata for subdivision
    subgraph_names: list[str]

    # Thresholds used (for reference)
    thresholds_used: dict


# =============================================================================
# Parsing
# =============================================================================


def parse_mermaid_file(content: str) -> MermaidStats:
    """
    Parse a Mermaid diagram and extract node/edge/subgraph counts.

    Handles:
    - Node definitions: NodeId["Label"] or NodeId or NodeId(("Label"))
    - Edge definitions: A --> B, A -.-> B, A ==> B, A -- text --> B
    - Subgraphs: subgraph "Name" ... end
    - Comments: %% comment
    - Class definitions: classDef, class
    - Link styles: linkStyle
    """
    lines = content.split("\n")

    nodes: set[str] = set()
    edges: int = 0
    subgraph_stack: list[str] = []
    subgraph_names: list[str] = []
    max_depth: int = 0

    # Regex patterns for Mermaid syntax
    node_patterns = [
        r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\[",  # NodeId["label"]
        r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\(",  # NodeId("label")
        r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\{",  # NodeId{"label"} - rhombus
        r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\>",  # NodeId>"label"] - asymmetric
        r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)@\{",  # NodeId@{ icon: "..."}
    ]

    # Edge detection patterns
    simple_edge_pattern = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*"
        r"(?:-->|-.->|==>|~~~|<-->|--[^-].*-->|-\.-.*-\.->|==.*==>)"
        r"\s*([A-Za-z_][A-Za-z0-9_]*)"
    )
    arrow_pattern = re.compile(r"(?:-->|-.->|==>|~~~|<-->)")

    subgraph_pattern = re.compile(
        r"^[ \t]*subgraph\s+(?:\"([^\"]+)\"|(\S+))?", re.IGNORECASE
    )
    end_pattern = re.compile(r"^[ \t]*end\s*$", re.IGNORECASE)
    comment_pattern = re.compile(r"^[ \t]*%%")
    directive_pattern = re.compile(
        r"^[ \t]*(?:graph|flowchart|sequenceDiagram|classDiagram|"
        r"stateDiagram|erDiagram|gantt|pie|journey)\s",
        re.IGNORECASE,
    )
    style_pattern = re.compile(
        r"^[ \t]*(?:classDef|class|linkStyle|style)\s", re.IGNORECASE
    )

    for line in lines:
        if comment_pattern.match(line):
            continue
        if directive_pattern.match(line):
            continue
        if style_pattern.match(line):
            continue
        if not line.strip():
            continue

        # Check for subgraph start
        subgraph_match = subgraph_pattern.match(line)
        if subgraph_match:
            name = (
                subgraph_match.group(1)
                or subgraph_match.group(2)
                or f"subgraph_{len(subgraph_names)}"
            )
            subgraph_stack.append(name)
            subgraph_names.append(name)
            max_depth = max(max_depth, len(subgraph_stack))
            continue

        # Check for subgraph end
        if end_pattern.match(line):
            if subgraph_stack:
                subgraph_stack.pop()
            continue

        # Count edges (arrows) on this line
        arrows_found = len(arrow_pattern.findall(line))
        edges += arrows_found

        # Extract node IDs from edges
        for match in simple_edge_pattern.finditer(line):
            nodes.add(match.group(1))
            nodes.add(match.group(2))

        # Extract node IDs from definitions (with shapes/labels)
        for pattern in node_patterns:
            for match in re.finditer(pattern, line):
                nodes.add(match.group(1))

        # Capture standalone node references in edges
        potential_nodes = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", line)
        keywords = {
            "graph", "flowchart", "subgraph", "end", "TB", "TD", "BT", "RL", "LR",
            "classDef", "class", "linkStyle", "style", "click", "callback",
            "direction", "default", "fill", "stroke", "color", "width",
        }
        for pn in potential_nodes:
            if pn.lower() not in {k.lower() for k in keywords}:
                if (
                    re.search(rf"\b{pn}\b\s*(?:-->|-.->|==>|<--|<-.|-<)", line)
                    or re.search(rf"(?:-->|-.->|==>|<--|<-.|-<)\s*\b{pn}\b", line)
                ):
                    nodes.add(pn)

    return MermaidStats(
        nodes=len(nodes),
        edges=edges,
        subgraphs=len(subgraph_names),
        max_subgraph_depth=max_depth,
        node_ids=sorted(nodes),
        subgraph_names=subgraph_names,
    )


# =============================================================================
# Complexity Calculation
# =============================================================================


def calculate_complexity(stats: MermaidStats, config: ThresholdConfig) -> dict:
    """
    Calculate complexity metrics from parsed stats.

    Returns dict with metrics and formula breakdown.
    """
    n = stats.nodes
    e = stats.edges
    s = stats.subgraphs
    d = stats.max_subgraph_depth

    # Visual Complexity Score (VCS)
    depth_multiplier = 1 + (d * config.depth_weight)
    base_vcs = n + (e * config.edge_weight) + (s * config.subgraph_weight)
    vcs = base_vcs * depth_multiplier

    # Edge Density: actual edges / maximum possible edges
    max_edges = n * (n - 1) if n > 1 else 1
    edge_density = e / max_edges if max_edges > 0 else 0

    # Cyclomatic Complexity: E - N + 2P (P=1 for single component)
    cyclomatic = e - n + 2

    # Formula breakdown for transparency
    formula = (
        f"({n} + {e}×{config.edge_weight} + {s}×{config.subgraph_weight}) "
        f"× (1 + {d}×{config.depth_weight})"
    )
    breakdown = {
        "nodes_contribution": n,
        "edges_contribution": round(e * config.edge_weight, 2),
        "subgraphs_contribution": round(s * config.subgraph_weight, 2),
        "base_vcs": round(base_vcs, 2),
        "depth_multiplier": round(depth_multiplier, 2),
        "final_vcs": round(vcs, 2),
    }

    return {
        "visual_complexity_score": round(vcs, 2),
        "edge_density": round(edge_density, 4),
        "cyclomatic_complexity": max(1, cyclomatic),
        "vcs_formula": formula,
        "vcs_breakdown": breakdown,
    }


def rate_complexity(
    vcs: float, nodes: int, config: ThresholdConfig
) -> tuple[str, str]:
    """Rate the diagram complexity. Returns (rating, color)."""
    if nodes <= config.node_ideal and vcs <= config.vcs_ideal:
        return "ideal", "green"
    elif nodes <= config.node_acceptable and vcs <= config.vcs_acceptable:
        return "acceptable", "yellow"
    elif nodes <= config.node_complex and vcs <= config.vcs_complex:
        return "complex", "orange"
    else:
        return "critical", "red"


# =============================================================================
# Subdivision Recommendation with Working Out
# =============================================================================


def recommend_subdivisions(
    vcs: float,
    nodes: int,
    edges: int,
    subgraphs: int,
    subgraph_names: list[str],
    config: ThresholdConfig,
) -> tuple[bool, int, str, SubdivisionWorkingOut]:
    """
    Recommend subdivisions with full working-out breakdown.

    Returns (needs_subdivision, recommended_count, rationale, working_out).
    """
    # Check threshold violations
    nodes_exceeds_acceptable = nodes > config.node_acceptable
    nodes_exceeds_complex = nodes > config.node_complex
    vcs_exceeds_acceptable = vcs > config.vcs_acceptable

    needs = nodes_exceeds_acceptable or vcs_exceeds_acceptable

    # Calculate node-based splits
    if nodes_exceeds_acceptable:
        node_splits = math.ceil(nodes / config.node_target)
        node_formula = f"ceil({nodes} / {config.node_target}) = {node_splits}"
    else:
        node_splits = 1
        node_formula = f"{nodes} ≤ {config.node_acceptable}, no split needed"

    # Calculate VCS-based splits
    if vcs_exceeds_acceptable:
        vcs_splits = math.ceil(vcs / config.vcs_target)
        vcs_formula = f"ceil({vcs:.1f} / {config.vcs_target}) = {vcs_splits}"
    else:
        vcs_splits = 1
        vcs_formula = f"{vcs:.1f} ≤ {config.vcs_acceptable}, no split needed"

    # Take maximum of the two
    count = max(node_splits, vcs_splits)

    # Subgraph adjustment
    subgraph_adjusted = count
    subgraph_reason = "No adjustment needed"
    if needs and subgraphs >= 2:
        # Use subgraphs as natural boundaries, but cap at count + 1
        suggested = min(subgraphs, count + 1)
        if suggested >= count:
            subgraph_adjusted = suggested
            subgraph_reason = (
                f"Adjusted from {count} to {suggested} to align with "
                f"{subgraphs} existing subgraphs"
            )

    final_count = subgraph_adjusted

    # Build rationale
    rationale_parts = []
    if nodes_exceeds_acceptable:
        rationale_parts.append(
            f"Node count ({nodes}) exceeds threshold ({config.node_acceptable})"
        )
    if vcs_exceeds_acceptable:
        rationale_parts.append(
            f"VCS ({vcs:.1f}) exceeds threshold ({config.vcs_acceptable})"
        )
    if nodes_exceeds_complex:
        rationale_parts.append(
            f"⚠️ Nodes ({nodes}) exceed cognitive limit ({config.node_complex})"
        )
    if subgraph_adjusted != count:
        rationale_parts.append(f"Using {subgraphs} subgraphs as boundaries")

    rationale = "; ".join(rationale_parts) if rationale_parts else "Within limits"

    # Calculate estimated complexity per split (recursive check)
    estimated_per_split = []
    if needs and final_count > 1:
        # Estimate how nodes/edges would distribute
        est_nodes = math.ceil(nodes / final_count)
        est_edges = math.ceil(edges / final_count)
        est_subgraphs = max(1, subgraphs // final_count)

        for i in range(final_count):
            # Estimate VCS for each split
            est_vcs = (
                est_nodes
                + est_edges * config.edge_weight
                + est_subgraphs * config.subgraph_weight
            )
            est_rating, _ = rate_complexity(est_vcs, est_nodes, config)

            split_info = {
                "split_number": i + 1,
                "estimated_nodes": est_nodes,
                "estimated_edges": est_edges,
                "estimated_vcs": round(est_vcs, 1),
                "estimated_rating": est_rating,
                "would_need_further_subdivision": est_rating in ("complex", "critical"),
            }
            estimated_per_split.append(split_info)

            # If any split would still be complex, recommend more splits
            if split_info["would_need_further_subdivision"]:
                # Recursive: calculate how many MORE splits needed
                additional = math.ceil(est_vcs / config.vcs_target)
                if additional > 1:
                    split_info["recursive_recommendation"] = (
                        f"This split would need {additional} further subdivisions"
                    )

    working_out = SubdivisionWorkingOut(
        nodes=nodes,
        vcs=vcs,
        subgraphs=subgraphs,
        nodes_exceeds_acceptable=nodes_exceeds_acceptable,
        nodes_exceeds_complex=nodes_exceeds_complex,
        vcs_exceeds_acceptable=vcs_exceeds_acceptable,
        node_based_splits=node_splits,
        node_based_formula=node_formula,
        vcs_based_splits=vcs_splits,
        vcs_based_formula=vcs_formula,
        subgraph_adjusted_splits=subgraph_adjusted,
        subgraph_adjustment_reason=subgraph_reason,
        final_splits=final_count,
        needs_subdivision=needs,
        estimated_per_split=estimated_per_split,
    )

    return needs, final_count, rationale, working_out


# =============================================================================
# Analysis
# =============================================================================


def analyze_file(file_path: Path, config: ThresholdConfig) -> ComplexityReport:
    """Analyze a single Mermaid file and return a complexity report."""
    content = file_path.read_text()
    stats = parse_mermaid_file(content)
    metrics = calculate_complexity(stats, config)

    vcs = metrics["visual_complexity_score"]
    rating, color = rate_complexity(vcs, stats.nodes, config)
    needs, count, rationale, working_out = recommend_subdivisions(
        vcs,
        stats.nodes,
        stats.edges,
        stats.subgraphs,
        stats.subgraph_names,
        config,
    )

    return ComplexityReport(
        file_path=str(file_path),
        nodes=stats.nodes,
        edges=stats.edges,
        subgraphs=stats.subgraphs,
        max_depth=stats.max_subgraph_depth,
        visual_complexity_score=vcs,
        edge_density=metrics["edge_density"],
        cyclomatic_complexity=metrics["cyclomatic_complexity"],
        vcs_formula=metrics["vcs_formula"],
        vcs_breakdown=metrics["vcs_breakdown"],
        rating=rating,
        color=color,
        needs_subdivision=needs,
        recommended_subdivisions=count,
        subdivision_rationale=rationale,
        working_out=working_out,
        subgraph_names=stats.subgraph_names,
        thresholds_used={
            "node_acceptable": config.node_acceptable,
            "node_complex": config.node_complex,
            "vcs_acceptable": config.vcs_acceptable,
            "node_target": config.node_target,
            "vcs_target": config.vcs_target,
        },
    )


# =============================================================================
# Output Formatting
# =============================================================================


def format_report(report: ComplexityReport, show_working: bool = False) -> str:
    """Format a complexity report for display."""
    color_codes = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "orange": "\033[38;5;208m",
        "red": "\033[91m",
        "reset": "\033[0m",
        "dim": "\033[2m",
        "bold": "\033[1m",
    }

    c = color_codes.get(report.color, "")
    r = color_codes["reset"]
    dim = color_codes["dim"]
    bold = color_codes["bold"]

    rating_emoji = {
        "ideal": "✅",
        "acceptable": "🟡",
        "complex": "🟠",
        "critical": "🔴",
    }

    lines = [
        "",
        "=" * 70,
        f"📊 {bold}{Path(report.file_path).name}{r}",
        "=" * 70,
        "",
        "📈 Raw Metrics:",
        f"   Nodes:     {report.nodes:4d}  {dim}(acceptable ≤{report.thresholds_used['node_acceptable']}){r}",
        f"   Edges:     {report.edges:4d}",
        f"   Subgraphs: {report.subgraphs:4d}  (depth: {report.max_depth})",
        "",
        "📐 Visual Complexity Score (VCS):",
        f"   Formula:  {dim}{report.vcs_formula}{r}",
        f"   Result:   {c}{bold}{report.visual_complexity_score:6.1f}{r}  {dim}(acceptable ≤{report.thresholds_used['vcs_acceptable']}){r}",
    ]

    # VCS breakdown
    bd = report.vcs_breakdown
    lines.extend([
        "",
        f"   {dim}Breakdown:{r}",
        f"     Nodes:     {bd['nodes_contribution']:6.1f}",
        f"     Edges:   + {bd['edges_contribution']:6.1f}  {dim}({report.edges} × edge_weight){r}",
        f"     Subgraphs:+ {bd['subgraphs_contribution']:6.1f}  {dim}({report.subgraphs} × subgraph_weight){r}",
        f"     Base VCS:  {bd['base_vcs']:6.1f}",
        f"     × Depth:   {bd['depth_multiplier']:6.2f}  {dim}(1 + {report.max_depth} × depth_weight){r}",
        f"     ─────────────────",
        f"     Final:     {bd['final_vcs']:6.1f}",
    ])

    lines.extend([
        "",
        f"   Edge Density:          {report.edge_density:6.4f}",
        f"   Cyclomatic Complexity: {report.cyclomatic_complexity:6d}",
        "",
        f"🎯 Rating: {rating_emoji.get(report.rating, '❓')} {c}{bold}{report.rating.upper()}{r}",
    ])

    if report.needs_subdivision:
        lines.extend([
            "",
            f"⚠️  {bold}SUBDIVISION RECOMMENDED{r}",
            f"   Recommended splits: {bold}{report.recommended_subdivisions}{r}",
            f"   Rationale: {report.subdivision_rationale}",
        ])

        if report.subgraph_names:
            names = ", ".join(report.subgraph_names[:5])
            if len(report.subgraph_names) > 5:
                names += f" (+{len(report.subgraph_names) - 5} more)"
            lines.append(f"   Potential boundaries: {names}")

        # Show working out if requested
        if show_working and report.working_out:
            wo = report.working_out
            lines.extend([
                "",
                f"📝 {bold}Calculation Working Out:{r}",
                "",
                "   Step 1: Check thresholds",
                f"     Nodes ({wo.nodes}) > acceptable ({report.thresholds_used['node_acceptable']})? "
                f"{'YES ❌' if wo.nodes_exceeds_acceptable else 'NO ✓'}",
                f"     VCS ({wo.vcs:.1f}) > acceptable ({report.thresholds_used['vcs_acceptable']})? "
                f"{'YES ❌' if wo.vcs_exceeds_acceptable else 'NO ✓'}",
                "",
                "   Step 2: Calculate node-based splits",
                f"     {wo.node_based_formula}",
                f"     → {wo.node_based_splits} split(s) needed",
                "",
                "   Step 3: Calculate VCS-based splits",
                f"     {wo.vcs_based_formula}",
                f"     → {wo.vcs_based_splits} split(s) needed",
                "",
                "   Step 4: Take maximum",
                f"     max({wo.node_based_splits}, {wo.vcs_based_splits}) = "
                f"{max(wo.node_based_splits, wo.vcs_based_splits)}",
            ])

            if wo.subgraph_adjusted_splits != max(wo.node_based_splits, wo.vcs_based_splits):
                lines.extend([
                    "",
                    "   Step 5: Subgraph adjustment",
                    f"     {wo.subgraph_adjustment_reason}",
                ])

            lines.extend([
                "",
                f"   {bold}Final recommendation: {wo.final_splits} split(s){r}",
            ])

            # Show recursive analysis
            if wo.estimated_per_split:
                lines.extend([
                    "",
                    f"🔄 {bold}Estimated Per-Split Complexity:{r}",
                ])
                any_needs_further = False
                for split in wo.estimated_per_split:
                    split_color = color_codes.get(
                        {"ideal": "green", "acceptable": "yellow", "complex": "orange", "critical": "red"}
                        .get(split["estimated_rating"], ""),
                        ""
                    )
                    status = "✓" if split["estimated_rating"] in ("ideal", "acceptable") else "⚠️"
                    lines.append(
                        f"   Split {split['split_number']}: ~{split['estimated_nodes']} nodes, "
                        f"~{split['estimated_vcs']:.0f} VCS → "
                        f"{split_color}{split['estimated_rating']}{r} {status}"
                    )
                    if split.get("would_need_further_subdivision"):
                        any_needs_further = True
                        if "recursive_recommendation" in split:
                            lines.append(f"      └─ {dim}{split['recursive_recommendation']}{r}")

                if any_needs_further:
                    lines.extend([
                        "",
                        f"   ⚠️  {bold}Warning:{r} Some splits would still exceed thresholds.",
                        f"      Consider increasing splits or reducing detail level.",
                    ])
    else:
        lines.extend([
            "",
            "✅ No subdivision needed - diagram is within visual clarity thresholds",
        ])

    return "\n".join(lines)


def format_json_report(reports: list[ComplexityReport]) -> str:
    """Format reports as JSON for programmatic use."""
    def serialize(obj):
        if hasattr(obj, "__dict__"):
            return asdict(obj)
        return obj

    output = []
    for r in reports:
        d = asdict(r)
        if r.working_out:
            d["working_out"] = asdict(r.working_out)
        output.append(d)
    return json.dumps(output, indent=2, default=serialize)


def format_summary(reports: list[ComplexityReport]) -> str:
    """Format a summary of all reports."""
    lines = [
        "",
        "=" * 70,
        f"📊 SUMMARY: {len(reports)} diagram(s) analyzed",
        "=" * 70,
    ]

    by_rating = {"ideal": [], "acceptable": [], "complex": [], "critical": []}
    for r in reports:
        by_rating[r.rating].append(r)

    needs_work = by_rating["complex"] + by_rating["critical"]

    lines.extend([
        "",
        f"  ✅ Ideal:      {len(by_rating['ideal']):3d}",
        f"  🟡 Acceptable: {len(by_rating['acceptable']):3d}",
        f"  🟠 Complex:    {len(by_rating['complex']):3d}",
        f"  🔴 Critical:   {len(by_rating['critical']):3d}",
    ])

    if needs_work:
        lines.extend([
            "",
            "📋 Diagrams needing attention:",
        ])
        for r in sorted(needs_work, key=lambda x: -x.visual_complexity_score):
            lines.append(
                f"   • {Path(r.file_path).name}: VCS={r.visual_complexity_score:.1f}, "
                f"nodes={r.nodes}, recommend {r.recommended_subdivisions} split(s)"
            )

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point."""
    import argparse

    # Load .env file first (lowest priority)
    ThresholdConfig.load_dotenv()

    parser = argparse.ArgumentParser(
        description="Analyze Mermaid diagram complexity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s diagram.mmd                      # Analyze single file
  %(prog)s docs/diagrams/                   # Analyze directory
  %(prog)s docs/diagrams/ --show-working    # Show calculation details
  %(prog)s *.mmd --json                     # Output as JSON
  %(prog)s docs/diagrams/ --summary-only    # Show only summary

  # Use density presets for different contexts
  %(prog)s docs/diagrams/ --preset low      # Executive summaries, embedded diagrams
  %(prog)s docs/diagrams/ --preset med      # README, component docs
  %(prog)s docs/diagrams/ --preset high     # Detailed architecture (default)

  # Custom thresholds via CLI (override preset)
  %(prog)s docs/diagrams/ --preset med --node-target=18

  # Via environment
  MERMAID_COMPLEXITY_PRESET=low %(prog)s docs/diagrams/

Density Presets (low < medium < high):
  ┌───────────────┬─────────┬──────────┬────────────┐
  │ Preset        │ Nodes   │ VCS      │ Target/split│
  ├───────────────┼─────────┼──────────┼────────────┤
  │ low-density   │ ≤12/20  │ ≤25/40   │ 10 / 20    │
  │ medium-density│ ≤20/35  │ ≤40/70   │ 15 / 30    │
  │ high-density  │ ≤35/50  │ ≤60/100  │ 25 / 40    │
  └───────────────┴─────────┴──────────┴────────────┘
  (Nodes: acceptable/complex, VCS: acceptable/complex)
  Aliases: low/l, med/medium/m, high/h

Configuration precedence: CLI args > Environment variables > .env file > Preset

Environment variables (prefix MERMAID_COMPLEXITY_):
  MERMAID_COMPLEXITY_PRESET (low-density, medium-density, high-density)
  MERMAID_COMPLEXITY_NODE_IDEAL, MERMAID_COMPLEXITY_NODE_ACCEPTABLE
  MERMAID_COMPLEXITY_VCS_IDEAL, MERMAID_COMPLEXITY_VCS_ACCEPTABLE
  MERMAID_COMPLEXITY_NODE_TARGET, MERMAID_COMPLEXITY_VCS_TARGET
""",
    )
    parser.add_argument(
        "paths", nargs="+", help="Mermaid files or directories to analyze"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--summary-only", action="store_true", help="Show only summary")
    parser.add_argument(
        "--show-working", "-w", action="store_true",
        help="Show detailed calculation working out"
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    # Preset argument
    parser.add_argument(
        "--preset", "-p",
        choices=["low-density", "medium-density", "high-density", "low", "med", "high", "l", "m", "h"],
        help="Detail density preset: low (fewest nodes), medium, high (most nodes, default)"
    )

    # Threshold arguments
    thresh = parser.add_argument_group("Threshold Configuration")
    thresh.add_argument("--node-ideal", type=int, help="Node count for 'ideal' rating")
    thresh.add_argument(
        "--node-acceptable", type=int, help="Node count for 'acceptable' rating"
    )
    thresh.add_argument(
        "--node-complex", type=int, help="Node count for 'complex' rating"
    )
    thresh.add_argument("--vcs-ideal", type=int, help="VCS for 'ideal' rating")
    thresh.add_argument("--vcs-acceptable", type=int, help="VCS for 'acceptable' rating")
    thresh.add_argument("--vcs-complex", type=int, help="VCS for 'complex' rating")
    thresh.add_argument(
        "--node-target", type=int, help="Target nodes per sub-diagram"
    )
    thresh.add_argument("--vcs-target", type=int, help="Target VCS per sub-diagram")
    thresh.add_argument(
        "--edge-weight", type=float, help="Weight for edges in VCS formula"
    )
    thresh.add_argument(
        "--subgraph-weight", type=float, help="Weight for subgraphs in VCS formula"
    )
    thresh.add_argument(
        "--depth-weight", type=float, help="Per-level depth multiplier"
    )

    args = parser.parse_args()

    # Build config: CLI preset > env preset > high-density (default)
    # from_env already checks MERMAID_COMPLEXITY_PRESET, so we just override if CLI provided
    base_preset = args.preset if args.preset else "high-density"
    config = ThresholdConfig.from_env(base_preset=base_preset)

    # Apply individual CLI threshold overrides
    cli_threshold_fields = [
        "node_ideal", "node_acceptable", "node_complex",
        "vcs_ideal", "vcs_acceptable", "vcs_complex",
        "node_target", "vcs_target",
        "edge_weight", "subgraph_weight", "depth_weight",
    ]
    for field_name in cli_threshold_fields:
        arg_value = getattr(args, field_name, None)
        if arg_value is not None:
            setattr(config, field_name, arg_value)
            config.preset_name = "custom"  # Mark as customized

    # Show config info (unless quiet or json output)
    if not args.quiet and not args.json:
        print(f"\n🔧 Using preset: {config.preset_name}")
        print(f"   Thresholds: nodes ≤{config.node_acceptable}/{config.node_complex}, "
              f"VCS ≤{config.vcs_acceptable}/{config.vcs_complex}, "
              f"targets: {config.node_target}/{config.vcs_target}")

    # Collect all .mmd files
    files: list[Path] = []
    for path_str in args.paths:
        path = Path(path_str)
        if path.is_dir():
            files.extend(path.glob("*.mmd"))
        elif path.is_file() and path.suffix == ".mmd":
            files.append(path)
        elif path.is_file():
            files.append(path)

    if not files:
        print("❌ No .mmd files found", file=sys.stderr)
        return 1

    # Analyze all files
    reports = [analyze_file(f, config) for f in sorted(files)]

    # Output
    if args.json:
        print(format_json_report(reports))
    elif args.summary_only:
        print(format_summary(reports))
    else:
        for report in reports:
            if not args.quiet:
                print(format_report(report, show_working=args.show_working))

        if len(reports) > 1:
            print(format_summary(reports))

    # Exit code: 0 if all ideal/acceptable, 1 if any complex/critical
    has_issues = any(r.rating in ("complex", "critical") for r in reports)
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
