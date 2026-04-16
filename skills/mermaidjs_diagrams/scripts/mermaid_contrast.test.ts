// Tests for mermaid_contrast.ts.
//
// Strategy:
//   - Unit-test scoreDirectives() against hand-crafted StyleDirective arrays
//     (no parsing — pure scoring logic).
//   - Integration-test auditContent() against mermaid sources that exercise
//     classDef, style, fill+color pairs, fill+stroke pairs, and the
//     "only-fill-declared" skipped case.
//   - Verify the CLI returns exit 1 on any AA failure and 0 on all pass.

import { describe, expect, test } from "bun:test";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { auditContent, auditFile, main, scoreDirectives } from "./mermaid_contrast.ts";
import type { StyleDirective } from "./color_contrast.ts";

// ─── Scoring logic (hand-crafted directives, no parser involved) ─────────────

describe("scoreDirectives", () => {
  test("fill+color pair is scored as text (AA threshold 4.5)", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "good", properties: { fill: "#2563eb", color: "#ffffff" }, line: 1 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(1);
    expect(pairs[0]!.kind).toBe("text");
    expect(pairs[0]!.passes).toBe(true);
    expect(pairs[0]!.assessment.ratio).toBeCloseTo(5.17, 2);
    expect(skipped).toHaveLength(0);
  });

  test("fill+stroke pair is scored as border (AA threshold 3.0)", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "x", properties: { fill: "#ffffff", stroke: "#777777" }, line: 1 },
    ];
    const { pairs } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(1);
    expect(pairs[0]!.kind).toBe("border");
    // #777 on #fff = 4.48 — passes 3.0 border threshold.
    expect(pairs[0]!.passes).toBe(true);
    expect(pairs[0]!.assessment.ratio).toBeCloseTo(4.48, 2);
  });

  test("fill+color AND fill+stroke yields TWO pairs (text + border)", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "both", properties: { fill: "#2563eb", color: "#fff", stroke: "#1e40af" }, line: 1 },
    ];
    const { pairs } = scoreDirectives(dirs);
    expect(pairs.map((p) => p.kind).sort()).toEqual(["border", "text"]);
  });

  test("missing fill skips the directive with a clear reason", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "orphan", properties: { color: "#fff" }, line: 1 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped).toHaveLength(1);
    expect(skipped[0]!.reason).toMatch(/no fill declared/);
  });

  test("only fill declared — skipped because theme defaults would apply", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "fill-only", properties: { fill: "#2563eb" }, line: 1 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped[0]!.reason).toMatch(/theme defaults/);
  });

  test("inlineClass and linkStyle are NOT scored (informational)", () => {
    const dirs: StyleDirective[] = [
      { kind: "inlineClass", selector: "A", class_name: "good", properties: {}, line: 1 },
      { kind: "linkStyle", selector: "0", properties: { stroke: "#777" }, line: 2 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped).toHaveLength(0);
  });

  test("failing text pair is flagged", () => {
    const dirs: StyleDirective[] = [
      // Yellow-on-yellow-ish: fails AA hard.
      { kind: "classDef", selector: "bad", properties: { fill: "#fbbf24", color: "#f3f4f6" }, line: 1 },
    ];
    const { pairs } = scoreDirectives(dirs);
    expect(pairs[0]!.passes).toBe(false);
    expect(pairs[0]!.assessment.rating).toBe("Fail");
  });
});

// ─── Integration: mermaid source → report ────────────────────────────────────

describe("auditContent", () => {
  test("full flowchart source: passing + failing pairs counted correctly", () => {
    const src = `flowchart LR
    A:::good --> B:::bad
    classDef good fill:#2563eb,stroke:#1e40af,color:#ffffff
    classDef bad  fill:#fbbf24,color:#f3f4f6
`;
    const report = auditContent(src);
    expect(report.pass_count).toBe(1); // good/text passes (5.17)
    expect(report.fail_count).toBe(2); // good/border fails (1.69), bad/text fails (1.52)
  });

  test("mixed color syntaxes round-trip through the parser", () => {
    const src = `flowchart LR
    classDef mixed fill:rgb(37 99 235),color:oklch(0.98 0 0),stroke:hsl(220 80% 30%)
`;
    const report = auditContent(src);
    expect(report.pairs).toHaveLength(2);
    // text pair should pass (oklch near-white on blue ≈ 4.88)
    const textPair = report.pairs.find((p) => p.kind === "text")!;
    expect(textPair.passes).toBe(true);
  });
});

// ─── Integration: markdown file with fences (absolute line numbers) ──────────

describe("auditFile — absolute line numbers", () => {
  const tmp = mkdtempSync(join(tmpdir(), "mermaid-contrast-"));

  test("line numbers are offset by fence start in .md files", async () => {
    const md = `# Doc

Prose above the diagram.

\`\`\`mermaid
flowchart LR
    A --> B
    classDef good fill:#2563eb,color:#ffffff
\`\`\`
`;
    const path = join(tmp, "sample.md");
    writeFileSync(path, md);
    const reports = await auditFile(path);
    expect(reports).toHaveLength(1);
    expect(reports[0]!.fence?.line_start).toBe(5);
    // classDef is on fence-local line 3, so absolute line = 5 + 3 = 8.
    expect(reports[0]!.pairs[0]!.line).toBe(8);
  });

  test(".mmd file gets no fence offset (file-relative line numbers)", async () => {
    const src = `flowchart LR
    A --> B
    classDef good fill:#2563eb,color:#ffffff
`;
    const path = join(tmp, "sample.mmd");
    writeFileSync(path, src);
    const reports = await auditFile(path);
    expect(reports[0]!.fence).toBeUndefined();
    expect(reports[0]!.pairs[0]!.line).toBe(3);
  });
});

// ─── CLI entry ───────────────────────────────────────────────────────────────

describe("main() CLI", () => {
  const tmp = mkdtempSync(join(tmpdir(), "mermaid-contrast-cli-"));

  test("--help returns 0", async () => {
    expect(await main(["--help"])).toBe(0);
  });

  test("no args returns 2", async () => {
    expect(await main([])).toBe(2);
  });

  test("passing file returns 0", async () => {
    const path = join(tmp, "pass.mmd");
    writeFileSync(path, `flowchart LR\n    A --> B\n    classDef good fill:#2563eb,color:#ffffff\n`);
    expect(await main(["--json", path])).toBe(0);
  });

  test("failing file returns 1", async () => {
    const path = join(tmp, "fail.mmd");
    writeFileSync(path, `flowchart LR\n    A --> B\n    classDef bad fill:#fbbf24,color:#f3f4f6\n`);
    expect(await main(["--json", path])).toBe(1);
  });
});
