// Tests for color_contrast.ts.
//
// Strategy:
//   - Verify the WCAG formula against canonical reference values (white/black=21,
//     gray #777/#fff=4.48 — the classic "just-below-AA" gotcha).
//   - Confirm universal parser accepts hex, rgb(), hsl(), oklch(), named colors.
//   - Verify rating tiers match the WCAG 2.1 table.
//   - Smoke-test the Mermaid style-directive extractor and the CLI entry.

import { describe, expect, test } from "bun:test";

import { apcaLc, extractStyleDirectives, main, wcagAssess, wcagRating, wcagRatio } from "./color_contrast.ts";

// ─── Canonical ratio values ──────────────────────────────────────────────────

describe("wcagRatio — reference values", () => {
  test("white on black is the 21:1 maximum", () => {
    expect(wcagRatio("#ffffff", "#000000")).toBe(21);
  });

  test("identical colors yield 1:1", () => {
    expect(wcagRatio("#2563eb", "#2563eb")).toBe(1);
  });

  test("#777 on white is the classic 4.48 — just below AA", () => {
    // Manually derived in the earlier conversation: L_gray ≈ 0.1845 → 4.48
    expect(wcagRatio("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
  });

  test("order doesn't matter — contrast is symmetric", () => {
    expect(wcagRatio("#000", "#fff")).toBeCloseTo(wcagRatio("#fff", "#000"), 6);
  });
});

// ─── Universal parser (the main reason colorjs.io is here) ───────────────────

describe("wcagRatio — accepts any CSS color syntax", () => {
  test("rgb() and hex of the same color produce the same ratio", () => {
    const a = wcagRatio("rgb(37 99 235)", "white");
    const b = wcagRatio("#2563eb", "#ffffff");
    expect(a).toBeCloseTo(b, 4);
  });

  test("hsl() accepted", () => {
    const r = wcagRatio("hsl(220 80% 30%)", "#ffffff");
    expect(r).toBeGreaterThan(4.5);
  });

  test("oklch() accepted", () => {
    const r = wcagRatio("oklch(0.98 0 0)", "rgb(55 65 81)");
    expect(r).toBeGreaterThan(4.5);
  });

  test("named colors accepted (rebeccapurple ~ 8.4:1 on white)", () => {
    expect(wcagRatio("rebeccapurple", "white")).toBeCloseTo(8.41, 2);
  });

  test("legacy comma-separated rgb() accepted", () => {
    const r = wcagRatio("rgb(255, 0, 0)", "rgb(0, 0, 255)");
    expect(r).toBeCloseTo(2.15, 2);
  });
});

// ─── Rating tiers ────────────────────────────────────────────────────────────

describe("wcagRating tiers", () => {
  test("≥7 → AAA", () => {
    expect(wcagRating(7.01)).toBe("AAA");
  });
  test("[4.5, 7) → AA", () => {
    expect(wcagRating(5.0)).toBe("AA");
  });
  test("[3, 4.5) → AA Large", () => {
    expect(wcagRating(3.5)).toBe("AA Large");
  });
  test("<3 → Fail", () => {
    expect(wcagRating(2.0)).toBe("Fail");
  });
});

// ─── wcagAssess bundles the flags correctly ──────────────────────────────────

describe("wcagAssess", () => {
  test("white/blue passes AA but not AAA", () => {
    const a = wcagAssess("#ffffff", "#2563eb");
    expect(a.ratio).toBeCloseTo(5.17, 2);
    expect(a.rating).toBe("AA");
    expect(a.passes_aa_normal).toBe(true);
    expect(a.passes_aaa_normal).toBe(false);
  });

  test("normalizes input to #rrggbb", () => {
    const a = wcagAssess("white", "rebeccapurple");
    expect(a.foreground_hex).toBe("#ffffff");
    expect(a.background_hex).toBe("#663399");
  });

  test("throws on unparseable input", () => {
    expect(() => wcagAssess("not-a-color", "#000")).toThrow();
  });
});

// ─── APCA sanity ─────────────────────────────────────────────────────────────

describe("apcaLc — sign matters (polarity)", () => {
  test("dark text on light bg has NEGATIVE Lc", () => {
    expect(apcaLc("#000000", "#ffffff")).toBeLessThan(0);
  });

  test("light text on dark bg has POSITIVE Lc", () => {
    expect(apcaLc("#ffffff", "#000000")).toBeGreaterThan(0);
  });
});

// ─── Mermaid directive extraction ────────────────────────────────────────────

describe("extractStyleDirectives", () => {
  test("extracts classDef with all color properties", () => {
    const src = "classDef good fill:#2563eb,stroke:#1e40af,color:#ffffff,stroke-width:2px\n";
    const dirs = extractStyleDirectives(src);
    expect(dirs).toHaveLength(1);
    expect(dirs[0]?.kind).toBe("classDef");
    expect(dirs[0]?.selector).toBe("good");
    expect(dirs[0]?.properties.fill).toBe("#2563eb");
    expect(dirs[0]?.properties.color).toBe("#ffffff");
    expect(dirs[0]?.properties.stroke).toBe("#1e40af");
    expect(dirs[0]?.properties["stroke-width"]).toBe("2px");
    expect(dirs[0]?.line).toBe(1);
  });

  test("extracts style (per-node) directive", () => {
    const src = "\nstyle A fill:#ef4444,color:#000\n";
    const dirs = extractStyleDirectives(src);
    expect(dirs).toHaveLength(1);
    expect(dirs[0]?.kind).toBe("style");
    expect(dirs[0]?.selector).toBe("A");
    expect(dirs[0]?.line).toBe(2);
  });

  test("extracts linkStyle with indices", () => {
    const src = "linkStyle 0,1 stroke:#6b7280\n";
    const dirs = extractStyleDirectives(src);
    expect(dirs).toHaveLength(1);
    expect(dirs[0]?.kind).toBe("linkStyle");
    expect(dirs[0]?.selector).toBe("0,1");
  });

  test("inline ::: classes detected with node id and class name", () => {
    const src = "flowchart LR\n    A[Start]:::good --> B:::bad\n";
    const dirs = extractStyleDirectives(src);
    const inline = dirs.filter((d) => d.kind === "inlineClass");
    expect(inline).toHaveLength(2);
    expect(inline.map((d) => [d.selector, d.class_name])).toEqual([
      ["A", "good"],
      ["B", "bad"],
    ]);
  });

  test("accepts both comma and semicolon property separators", () => {
    const src = "classDef x fill:#fff;color:#000;stroke:#777\n";
    const dirs = extractStyleDirectives(src);
    expect(dirs[0]?.properties).toMatchObject({ fill: "#fff", color: "#000", stroke: "#777" });
  });

  test("empty source yields no directives", () => {
    expect(extractStyleDirectives("flowchart LR\n  A --> B\n")).toEqual([]);
  });
});

// ─── CLI ─────────────────────────────────────────────────────────────────────

describe("main() CLI", () => {
  test("--help returns 0", async () => {
    expect(await main(["--help"])).toBe(0);
  });

  test("no args returns 2 (usage error)", async () => {
    expect(await main([])).toBe(2);
  });

  test("passing pair returns 0", async () => {
    // white on black — passes everything.
    expect(await main(["#ffffff", "#000000", "--json"])).toBe(0);
  });

  test("failing pair returns 1", async () => {
    // red on blue — ratio ~2.15, fails AA.
    expect(await main(["red", "blue", "--json"])).toBe(1);
  });

  test("unknown flag returns 2", async () => {
    expect(await main(["--nonsense"])).toBe(2);
  });

  test("default (non-json) output path exercises formatAssessment for passing pair", async () => {
    // white on black — passes AA; exercises non-json formatter (line 322 branch).
    expect(await main(["#ffffff", "#000000"])).toBe(0);
  });

  test("default (non-json) output path for failing pair exercises Fail rating color branch", async () => {
    // red on blue — fails AA; exercises the red/Fail color branch in formatAssessment.
    expect(await main(["red", "blue"])).toBe(1);
  });

  test("default (non-json) output for AA Large rating exercises yellow branch", async () => {
    // Find a pair in the [3, 4.5) band: #767676 on #fff gives ~4.54 (just AA),
    // #999 on #fff gives ~2.85 (Fail). #888 on #fff lands around 3.54 (AA Large).
    expect(await main(["#888888", "#ffffff"])).toBe(1); // AA Large fails AA normal
  });

  test("default (non-json) output for AAA rating exercises the AAA color branch", async () => {
    // white on black = 21:1 => AAA.
    expect(await main(["#ffffff", "#000000"])).toBe(0);
  });

  test("one positional arg (not 2) returns 2 with error message", async () => {
    // positionals.length === 1 → hits the "expected 2 positional args" branch (lines 307-309).
    expect(await main(["#fff"])).toBe(2);
  });

  test("three positional args returns 2 with error message", async () => {
    // positionals.length === 3 → also hits the "expected 2 positional args" branch.
    expect(await main(["#fff", "#000", "#abc"])).toBe(2);
  });

  test("unparseable color in pair mode returns 2 with error", async () => {
    // lines 315-316: wcagAssess throws → caught → return 2.
    expect(await main(["not-a-color", "#000"])).toBe(2);
  });

  test("--stdin with empty stdin yields JSON parse error (returns 2)", async () => {
    // Within bun:test, Bun.stdin is an empty stream at EOF, so readStdin returns ""
    // and JSON.parse("") throws. Exercises lines 226-229 (readStdin) and 261-267
    // (stdin read + JSON parse error branch) in-process (coverage-traced).
    expect(await main(["--stdin"])).toBe(2);
  });

  test("--stdin --json with empty stdin yields JSON parse error (returns 2)", async () => {
    // Same path as above but with --json; both set values.stdin before values.json.
    expect(await main(["--stdin", "--json"])).toBe(2);
  });
});

// ─── CLI via subprocess (exercises main-as-module bootstrap + stdin) ─────────

describe("CLI subprocess — stdin mode", () => {
  const scriptPath = new URL("./color_contrast.ts", import.meta.url).pathname;

  test("--stdin with valid JSON pairs returns 0 if all pass (--json mode)", async () => {
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin", "--json"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write('[["#ffffff","#000000"],["#ffffff","#2563eb"]]');
    await proc.stdin.end();
    const exitCode = await proc.exited;
    const out = await new Response(proc.stdout).text();
    expect(exitCode).toBe(0);
    const parsed = JSON.parse(out);
    expect(parsed).toHaveLength(2);
    expect(parsed[0].ratio).toBe(21);
  });

  test("--stdin with a failing pair returns 1", async () => {
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin", "--json"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write('[["red","blue"]]');
    await proc.stdin.end();
    expect(await proc.exited).toBe(1);
  });

  test("--stdin with default (non-json) output path formats each assessment", async () => {
    // Exercises the non-json for-loop inside stdin mode (lines 293-297).
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write('[["#ffffff","#000000"]]');
    await proc.stdin.end();
    const exitCode = await proc.exited;
    const out = await new Response(proc.stdout).text();
    expect(exitCode).toBe(0);
    expect(out).toContain("WCAG 2.1");
    expect(out).toContain("APCA Lc");
  });

  test("--stdin with invalid JSON returns 2", async () => {
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write("not-json-at-all");
    await proc.stdin.end();
    const exitCode = await proc.exited;
    const err = await new Response(proc.stderr).text();
    expect(exitCode).toBe(2);
    expect(err).toContain("not valid JSON");
  });

  test("--stdin with non-array JSON returns 2", async () => {
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write('{"not":"an array"}');
    await proc.stdin.end();
    const exitCode = await proc.exited;
    const err = await new Response(proc.stderr).text();
    expect(exitCode).toBe(2);
    expect(err).toContain("expects a JSON array");
  });

  test("--stdin with malformed tuple returns 2", async () => {
    // Non-tuple entry (single-element array) triggers the "not a [string, string] tuple" branch.
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write('[["#fff"]]');
    await proc.stdin.end();
    const exitCode = await proc.exited;
    const err = await new Response(proc.stderr).text();
    expect(exitCode).toBe(2);
    expect(err).toContain("is not a [string, string] tuple");
  });

  test("--stdin with unparseable color in a pair returns 2", async () => {
    // Both strings, but colorjs.io rejects "not-a-color" → catch branch (lines 285-287).
    const proc = Bun.spawn(["bun", "run", scriptPath, "--stdin"], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    proc.stdin.write('[["not-a-color","#000"]]');
    await proc.stdin.end();
    const exitCode = await proc.exited;
    const err = await new Response(proc.stderr).text();
    expect(exitCode).toBe(2);
    expect(err).toContain("not-a-color");
  });

  test("CLI bootstrap: running script directly with valid pair exits 0", async () => {
    // Exercises lines 330-334 (import.meta.main branch + .then(process.exit)).
    const proc = Bun.spawn(["bun", "run", scriptPath, "#ffffff", "#000000", "--json"], {
      stdout: "pipe",
      stderr: "pipe",
    });
    expect(await proc.exited).toBe(0);
  });
});
