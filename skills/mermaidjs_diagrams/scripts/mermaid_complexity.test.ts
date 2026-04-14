// Tests for mermaid_complexity.ts.
//
// Strategy:
//   - Unit-test the metric formulas against known inputs (pure math, no parser).
//   - Parity-test against the existing Python implementation's published
//     outputs on the two `.mmd` fixtures in resources/examples/. Parity is the
//     scientific control — both implementations must agree on flowchart
//     (where Python's regex is decent) and the TS implementation is expected
//     to report MORE structure on architecture-beta (where Python's regex
//     returns zero nodes).

import { describe, expect, test } from "bun:test";
import { resolve } from "node:path";

import { analyzeContent, analyzeFile, main } from "./mermaid_complexity.ts";

const EXAMPLES_DIR = resolve(import.meta.dir, "../resources/examples");

// ─── Fixture parity ──────────────────────────────────────────────────────────

describe("canonical parser output vs Python regex baseline", () => {
  test("flowchart_fontawesome_icons.mmd — canonical parser gives cleaner node count", async () => {
    // Python regex reports nodes=11, vcs=30.8. The TS version uses
    // mermaid-core's JISON parser (via happy-dom shim) which counts 10
    // explicit vertex definitions — the Python regex over-counted by
    // picking up a subgraph label identifier. Edges and subgraphs agree.
    const [report] = await analyzeFile(
      resolve(EXAMPLES_DIR, "flowchart_fontawesome_icons.mmd"),
      highDensity(),
    );
    expect(report!.parser_used).toBe("mermaid-core");
    expect(report!.diagram_type).toBe("flowchart-v2");
    expect(report!.nodes).toBe(10);
    expect(report!.edges).toBe(10);
    expect(report!.subgraphs).toBe(4);
    expect(report!.max_depth).toBe(1);
    expect(report!.visual_complexity_score).toBe(29.7);
    expect(report!.rating).toBe("ideal");
    expect(report!.fence).toBeUndefined();
  });

  test("architecture_beta_iconify_logos.mmd — TS captures what Python regex misses", async () => {
    // Scientific validation: Python returns nodes=0 for architecture-beta
    // because its regex only handles flowchart-style syntax. TS uses the
    // Langium parser and returns the real structure.
    const [report] = await analyzeFile(
      resolve(EXAMPLES_DIR, "architecture_beta_iconify_logos.mmd"),
      highDensity(),
    );
    expect(report!.parser_used).toBe("langium");
    expect(report!.diagram_type).toBe("architecture-beta");
    expect(report!.nodes).toBeGreaterThan(0);
    expect(report!.subgraphs).toBeGreaterThan(0);
  });

  test("test_gallery.md — .md file yields one report per ```mermaid fence", async () => {
    const reports = await analyzeFile(
      resolve(EXAMPLES_DIR, "test_gallery.md"),
      highDensity(),
    );
    expect(reports.length).toBeGreaterThan(20); // 27 fences after scope narrowing
    // Every report carries a fence location
    for (const r of reports) {
      expect(r.fence).toBeDefined();
      expect(r.fence!.line_start).toBeGreaterThan(0);
      expect(r.fence!.line_end).toBeGreaterThan(r.fence!.line_start);
    }
    // At least one Langium-parsed diagram landed in the gallery
    const langiumReports = reports.filter((r) => r.parser_used === "langium");
    expect(langiumReports.length).toBeGreaterThan(0);
  });
});

// ─── Metric math ─────────────────────────────────────────────────────────────

describe("VCS formula", () => {
  test("all-zero diagram gives zero VCS and cyclomatic=max(1, 0-0+2)=2", async () => {
    const report = await analyzeContent("info\n", highDensity());
    expect(report.visual_complexity_score).toBe(0);
    expect(report.edges).toBe(0);
    expect(report.cyclomatic_complexity).toBe(2);
    expect(report.rating).toBe("ideal");
  });

  test("breakdown sums to final_vcs", async () => {
    const content = `flowchart LR
  A --> B
  B --> C
  subgraph G
    D --> E
  end
`;
    const report = await analyzeContent(content, highDensity());
    const bd = report.vcs_breakdown;
    const expectedBase = bd.nodes_contribution + bd.edges_contribution + bd.subgraphs_contribution;
    expect(bd.base_vcs).toBeCloseTo(expectedBase, 2);
    expect(bd.final_vcs).toBeCloseTo(bd.base_vcs * bd.depth_multiplier, 2);
  });

  test("edge_density = E / (N*(N-1))", async () => {
    const content = `flowchart LR
  A --> B
  B --> C
  C --> A
`;
    const report = await analyzeContent(content, highDensity());
    // 3 nodes, 3 edges → 3 / (3*2) = 0.5
    expect(report.edge_density).toBe(0.5);
  });
});

// ─── Rating thresholds ──────────────────────────────────────────────────────

describe("rating thresholds", () => {
  test("a large flowchart is rated complex or critical", async () => {
    const nodes = Array.from({ length: 60 }, (_, i) => `N${i}[node${i}]`).join("\n");
    const edges = Array.from({ length: 40 }, (_, i) => `N${i} --> N${(i + 1) % 60}`).join("\n");
    const content = `flowchart LR\n${nodes}\n${edges}\n`;
    const report = await analyzeContent(content, highDensity());
    expect(["complex", "critical"]).toContain(report.rating);
    expect(report.needs_subdivision).toBe(true);
  });
});

// ─── CLI entry ──────────────────────────────────────────────────────────────

describe("main() CLI", () => {
  test("--help exits 0 without throwing", async () => {
    const code = await main(["--help"]);
    expect(code).toBe(0);
  });

  test("no arguments prints help and returns 2", async () => {
    const code = await main([]);
    expect(code).toBe(2);
  });

  test("running on the flowchart fixture returns 0 (ideal)", async () => {
    const code = await main([
      "--quiet",
      "--json",
      resolve(EXAMPLES_DIR, "flowchart_fontawesome_icons.mmd"),
    ]);
    expect(code).toBe(0);
  });
});

// ─── Shared test config ──────────────────────────────────────────────────────

function highDensity() {
  return {
    node_ideal: 20, node_acceptable: 35, node_complex: 50, node_hard_limit: 100,
    vcs_ideal: 35, vcs_acceptable: 60, vcs_complex: 100, vcs_critical: 150,
    node_target: 25, vcs_target: 40,
    edge_weight: 0.5, subgraph_weight: 3.0, depth_weight: 0.1,
    preset_name: "high-density",
  };
}
