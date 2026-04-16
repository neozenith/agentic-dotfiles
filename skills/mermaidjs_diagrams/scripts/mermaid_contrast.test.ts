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
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
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
    expect(pairs[0]?.kind).toBe("text");
    expect(pairs[0]?.passes).toBe(true);
    expect(pairs[0]?.assessment.ratio).toBeCloseTo(5.17, 2);
    expect(skipped).toHaveLength(0);
  });

  test("fill+stroke pair is scored as border (AA threshold 3.0)", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "x", properties: { fill: "#ffffff", stroke: "#777777" }, line: 1 },
    ];
    const { pairs } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(1);
    expect(pairs[0]?.kind).toBe("border");
    // #777 on #fff = 4.48 — passes 3.0 border threshold.
    expect(pairs[0]?.passes).toBe(true);
    expect(pairs[0]?.assessment.ratio).toBeCloseTo(4.48, 2);
  });

  test("fill+color AND fill+stroke yields TWO pairs (text + border)", () => {
    const dirs: StyleDirective[] = [
      {
        kind: "classDef",
        selector: "both",
        properties: { fill: "#2563eb", color: "#fff", stroke: "#1e40af" },
        line: 1,
      },
    ];
    const { pairs } = scoreDirectives(dirs);
    expect(pairs.map((p) => p.kind).sort()).toEqual(["border", "text"]);
  });

  test("missing fill skips the directive with a clear reason", () => {
    const dirs: StyleDirective[] = [{ kind: "classDef", selector: "orphan", properties: { color: "#fff" }, line: 1 }];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped).toHaveLength(1);
    expect(skipped[0]?.reason).toMatch(/no fill declared/);
  });

  test("only fill declared — skipped because theme defaults would apply", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "fill-only", properties: { fill: "#2563eb" }, line: 1 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped[0]?.reason).toMatch(/theme defaults/);
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
    expect(pairs[0]?.passes).toBe(false);
    expect(pairs[0]?.assessment.rating).toBe("Fail");
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
    const textPair = report.pairs.find((p) => p.kind === "text");
    expect(textPair).toBeDefined();
    expect(textPair?.passes).toBe(true);
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
    expect(reports[0]?.fence?.line_start).toBe(5);
    // classDef is on fence-local line 3, so absolute line = 5 + 3 = 8.
    expect(reports[0]?.pairs[0]?.line).toBe(8);
  });

  test(".mmd file gets no fence offset (file-relative line numbers)", async () => {
    const src = `flowchart LR
    A --> B
    classDef good fill:#2563eb,color:#ffffff
`;
    const path = join(tmp, "sample.mmd");
    writeFileSync(path, src);
    const reports = await auditFile(path);
    expect(reports[0]?.fence).toBeUndefined();
    expect(reports[0]?.pairs[0]?.line).toBe(3);
  });
});

// ─── scoreDirectives — unparseable color catch branches ────────────────────

describe("scoreDirectives — unparseable colors route to skipped with reasons", () => {
  test("unparseable color (text pair) is routed to skipped with 'text pair unparseable'", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "bad-text", properties: { fill: "#2563eb", color: "not-a-color" }, line: 7 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped).toHaveLength(1);
    expect(skipped[0]?.reason).toMatch(/text pair unparseable/);
    expect(skipped[0]?.line).toBe(7);
  });

  test("unparseable color (border pair) is routed to skipped with 'border pair unparseable'", () => {
    const dirs: StyleDirective[] = [
      { kind: "classDef", selector: "bad-border", properties: { fill: "#2563eb", stroke: "not-a-color" }, line: 9 },
    ];
    const { pairs, skipped } = scoreDirectives(dirs);
    expect(pairs).toHaveLength(0);
    expect(skipped).toHaveLength(1);
    expect(skipped[0]?.reason).toMatch(/border pair unparseable/);
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

  test("unknown flag returns 2 (argparse error path)", async () => {
    // Exercises the parseArgs catch branch (lines 325-327).
    expect(await main(["--nonsense-flag"])).toBe(2);
  });

  test("non-existent path returns 1 (no matching files)", async () => {
    // collectFiles logs a warning via statSync catch (line 283) and returns 0
    // files → main returns 1 via "no matching files" (lines 343-344).
    const bogus = join(tmp, `does-not-exist-${Date.now()}`);
    expect(await main([bogus])).toBe(1);
  });

  test("passes a DIRECTORY — exercises collectFiles directory branch + default output", async () => {
    // collectFiles directory branch (lines 275-279) filters by extension.
    // Default (non-json, non-summary) output path exercises formatReport + formatSummary
    // (lines 226-252, 256-260, 354-360).
    const dir = join(tmp, `dirtest-${Date.now()}`);
    mkdirSync(dir, { recursive: true });
    writeFileSync(
      join(dir, "a.mmd"),
      `flowchart LR\n    A --> B\n    classDef good fill:#2563eb,color:#ffffff,stroke:#1e40af\n`,
    );
    writeFileSync(join(dir, "b.mmd"), `flowchart LR\n    A --> B\n    classDef bad fill:#fbbf24,color:#f3f4f6\n`);
    writeFileSync(join(dir, "ignored.txt"), "not a mermaid file");
    // Run in default output mode (no --json, no --summary) to exercise formatReport.
    const code = await main([dir]);
    // Mix of pass and fail → should return 1.
    expect(code).toBe(1);
  });

  test("--summary mode exercises formatSummary-only path", async () => {
    // Lines 354-355: values.summary branch in main().
    const path = join(tmp, "summary.mmd");
    writeFileSync(path, `flowchart LR\n    classDef good fill:#2563eb,color:#ffffff\n`);
    expect(await main(["--summary", path])).toBe(0);
  });

  test("--quiet suppresses passing reports in default output", async () => {
    // Line 358: values.quiet && r.fail_count === 0 → continue.
    const path = join(tmp, "quiet.mmd");
    writeFileSync(path, `flowchart LR\n    classDef good fill:#2563eb,color:#ffffff\n`);
    expect(await main(["--quiet", path])).toBe(0);
  });

  test("default output path prints per-report + summary for failing file", async () => {
    // Lines 357-361: the for/formatReport loop + final formatSummary.
    const path = join(tmp, "default-out.mmd");
    writeFileSync(path, `flowchart LR\n    classDef bad fill:#fbbf24,color:#f3f4f6\n`);
    expect(await main([path])).toBe(1);
  });

  test("empty-directives file renders the '(no style directives found)' branch", async () => {
    // Line 231-233: r.pairs.length === 0 && r.skipped.length === 0.
    const path = join(tmp, "empty.mmd");
    writeFileSync(path, `flowchart LR\n    A --> B\n`);
    expect(await main([path])).toBe(0);
  });

  test("markdown file with fence exercises the fence header branch in formatReport", async () => {
    // Line 228: r.fence truthy branch — needs a .md file with a mermaid fence.
    const path = join(tmp, "with-fence.md");
    writeFileSync(path, `# Doc\n\n\`\`\`mermaid\nflowchart LR\n    classDef bad fill:#fbbf24,color:#f3f4f6\n\`\`\`\n`);
    expect(await main([path])).toBe(1);
  });

  test("AA Large rating exercises the yellow rating color branch in formatReport", async () => {
    // rating === "AA Large" → yellow branch (line 240).
    const path = join(tmp, "aalarge.mmd");
    // #888 on #fff ≈ 3.54 (AA Large) — text fails 4.5 but not 3.0.
    writeFileSync(path, `flowchart LR\n    classDef border-ish fill:#ffffff,color:#888888\n`);
    expect(await main([path])).toBe(1);
  });

  test("skipped directive is rendered in default output (no-fill branch)", async () => {
    // Line 247-251: the r.skipped for-loop.
    const path = join(tmp, "skipped.mmd");
    writeFileSync(path, `flowchart LR\n    classDef orphan color:#ffffff\n`);
    // No fill → skipped, no pairs → fail_count=0 → returns 0.
    expect(await main([path])).toBe(0);
  });
});

// ─── CLI bootstrap via subprocess (exercises import.meta.main block) ────────

describe("CLI subprocess", () => {
  const scriptPath = new URL("./mermaid_contrast.ts", import.meta.url).pathname;
  const tmp = mkdtempSync(join(tmpdir(), "mermaid-contrast-sub-"));

  test("bootstrap runs end-to-end on a passing file", async () => {
    // Covers lines 369-373: main().then(process.exit).
    const path = join(tmp, "ok.mmd");
    writeFileSync(path, `flowchart LR\n    classDef good fill:#2563eb,color:#ffffff\n`);
    const proc = Bun.spawn(["bun", "run", scriptPath, "--json", path], {
      stdout: "pipe",
      stderr: "pipe",
    });
    expect(await proc.exited).toBe(0);
  });
});
