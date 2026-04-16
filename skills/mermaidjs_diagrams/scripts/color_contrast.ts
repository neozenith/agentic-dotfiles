#!/usr/bin/env bun
// WCAG contrast ratio calculator + universal color parser.
//
// Two use cases:
//   1. Standalone CLI — LLM extracts colors from a screenshot (any CSS syntax)
//      and pipes them to this tool to get ratings.
//   2. Shared library — mermaid_contrast.ts imports extractStyleDirectives()
//      and wcagAssess() to audit classDef/style/linkStyle directives in
//      mermaid sources.
//
// Universal parsing is delegated to colorjs.io, which accepts every CSS Color
// Level 4 syntax: hex, rgb(), hsl(), hwb(), lab(), lch(), oklab(), oklch(),
// color(display-p3 ...), named colors, and modern space-separated forms with
// alpha.
//
// Usage:
//   bun run color_contrast.ts <fg> <bg>
//   bun run color_contrast.ts "#ffffff" "#2563eb"
//   bun run color_contrast.ts "rgb(55 65 81)" "oklch(0.98 0 0)" --json
//   echo '[["#fff","#777"],["red","blue"]]' | bun run color_contrast.ts --stdin --json
//
// Exit codes: 0 all pairs pass AA (>= 4.5:1), 1 any pair fails, 2 usage error.

import Color from "colorjs.io";
import { parseArgs } from "node:util";

// ─── Types ───────────────────────────────────────────────────────────────────

export type WcagRating = "AAA" | "AA" | "AA Large" | "Fail";

export interface ContrastAssessment {
  foreground: string;           // user-provided string
  background: string;           // user-provided string
  foreground_hex: string;       // normalized #rrggbb (or #rrggbbaa if alpha < 1)
  background_hex: string;
  ratio: number;                // WCAG 2.x contrast ratio, 1..21, rounded to 2dp
  rating: WcagRating;           // pass tier
  passes_aa_normal: boolean;    // ratio >= 4.5
  passes_aa_large: boolean;     // ratio >= 3
  passes_aaa_normal: boolean;   // ratio >= 7
  apca_lc: number;              // signed APCA Lc (-108..+106), rounded to 1dp
}

export interface StyleDirective {
  kind: "classDef" | "style" | "linkStyle" | "inlineClass";
  selector: string;             // class name, node id, link index, or node id (for inlineClass)
  class_name?: string;          // only for inlineClass: the class applied
  properties: Record<string, string>; // { fill: "#2563eb", color: "#fff", stroke: "..." }
  line: number;                 // 1-based line number in the source
}

// ─── Contrast math (all via colorjs.io) ──────────────────────────────────────

/** WCAG 2.1 contrast ratio in [1, 21]. Throws if either input can't be parsed. */
export function wcagRatio(fg: string, bg: string): number {
  const f = new Color(fg);
  const b = new Color(bg);
  // colorjs.io returns the ratio with numerator/denominator already ordered by
  // luminance, so the value is always >= 1.
  return f.contrast(b, "WCAG21");
}

/** APCA Lc value. Negative = dark text on light bg; positive = light on dark. */
export function apcaLc(fg: string, bg: string): number {
  return new Color(fg).contrast(new Color(bg), "APCA");
}

/** Classify a WCAG ratio into the rating tier most commonly cited. */
export function wcagRating(ratio: number): WcagRating {
  if (ratio >= 7) return "AAA";
  if (ratio >= 4.5) return "AA";
  if (ratio >= 3) return "AA Large";
  return "Fail";
}

/** Normalize any CSS color to #rrggbb or #rrggbbaa. */
function toHex(color: string): string {
  // colorjs.io uses `null` coords for powerless channels (e.g. hue of a pure
  // gray in hsl). After converting to sRGB those map to 0 without ambiguity.
  const c = new Color(color).to("srgb");
  const [r, g, b] = c.coords.map((v) => Math.round(Math.max(0, Math.min(1, v ?? 0)) * 255));
  const a = c.alpha ?? 1;
  const hex = (n: number) => n.toString(16).padStart(2, "0");
  const base = `#${hex(r!)}${hex(g!)}${hex(b!)}`;
  return a < 1 ? `${base}${hex(Math.round(a * 255))}` : base;
}

/** Full assessment bundling ratio, rating, and per-tier pass/fail flags. */
export function wcagAssess(fg: string, bg: string): ContrastAssessment {
  const ratio = wcagRatio(fg, bg);
  const rounded = Math.round(ratio * 100) / 100;
  const apca = Math.round(apcaLc(fg, bg) * 10) / 10;
  return {
    foreground: fg,
    background: bg,
    foreground_hex: toHex(fg),
    background_hex: toHex(bg),
    ratio: rounded,
    rating: wcagRating(rounded),
    passes_aa_normal: rounded >= 4.5,
    passes_aa_large: rounded >= 3,
    passes_aaa_normal: rounded >= 7,
    apca_lc: apca,
  };
}

// ─── Mermaid style-directive extraction ──────────────────────────────────────

// Mermaid allows these style-bearing line forms:
//   classDef NAME  fill:#X,stroke:#Y,color:#Z,stroke-width:2px
//   style NODEID   fill:#X,stroke:#Y,color:#Z
//   linkStyle 0,1  stroke:#X,stroke-width:2px
//   A:::className                         (inline class application)
//   A[label]:::className --> B            (inline class during node declaration)
//
// We extract all of them. Downstream contrast auditors decide which pairs to
// check (fill×color for text, fill×stroke for border).

const CLASSDEF_RE = /^[ \t]*classDef\s+(\S+)\s+(.+?)\s*;?\s*$/i;
const STYLE_RE = /^[ \t]*style\s+(\S+)\s+(.+?)\s*;?\s*$/i;
const LINKSTYLE_RE = /^[ \t]*linkStyle\s+(\S+)\s+(.+?)\s*;?\s*$/i;
// Inline `:::className` — captures node id and the class applied.
// Matches:  A:::good   or   A[label]:::good   or   A("label"):::good
const INLINE_CLASS_RE = /([A-Za-z_][\w-]*)(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|>[^<]*)?:::([A-Za-z_][\w-]*)/g;

function parseProperties(raw: string): Record<string, string> {
  // Mermaid supports both `,` and `;` separators between properties. Values
  // never contain `,` or `;` in well-formed mermaid (hex colors, px units,
  // keywords), so simple split is safe.
  const props: Record<string, string> = {};
  for (const pair of raw.split(/[,;]/)) {
    const [k, ...rest] = pair.split(":");
    if (!k || rest.length === 0) continue;
    const key = k.trim().toLowerCase();
    const value = rest.join(":").trim();
    if (key && value) props[key] = value;
  }
  return props;
}

/**
 * Extract every style-bearing directive from a mermaid source. Returns them
 * with 1-based line numbers for reporting.
 */
export function extractStyleDirectives(source: string): StyleDirective[] {
  const out: StyleDirective[] = [];
  const lines = source.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const lineNo = i + 1;

    let m = CLASSDEF_RE.exec(line);
    if (m) {
      out.push({ kind: "classDef", selector: m[1]!, properties: parseProperties(m[2]!), line: lineNo });
      continue;
    }
    m = STYLE_RE.exec(line);
    if (m) {
      out.push({ kind: "style", selector: m[1]!, properties: parseProperties(m[2]!), line: lineNo });
      continue;
    }
    m = LINKSTYLE_RE.exec(line);
    if (m) {
      out.push({ kind: "linkStyle", selector: m[1]!, properties: parseProperties(m[2]!), line: lineNo });
      continue;
    }

    // Inline `:::className` can occur on any line — scan separately.
    INLINE_CLASS_RE.lastIndex = 0;
    let inlineMatch: RegExpExecArray | null;
    while ((inlineMatch = INLINE_CLASS_RE.exec(line)) !== null) {
      out.push({
        kind: "inlineClass",
        selector: inlineMatch[1]!,
        class_name: inlineMatch[2]!,
        properties: {},
        line: lineNo,
      });
    }
  }
  return out;
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

function printHelp(): void {
  console.log(`\
color_contrast.ts — WCAG contrast calculator (accepts any CSS color syntax)

Usage:
  bun run color_contrast.ts <foreground> <background> [--json]
  bun run color_contrast.ts --stdin [--json]

Examples:
  bun run color_contrast.ts "#ffffff" "#2563eb"
  bun run color_contrast.ts "rgb(55 65 81)" "oklch(0.98 0 0)" --json
  echo '[["#fff","#777"],["red","blue"]]' | bun run color_contrast.ts --stdin --json

Output:
  Default: human-readable ratio + AA/AAA verdict + APCA Lc.
  --json:  machine-readable assessment object (or array for --stdin).

Exit codes: 0 if ALL pairs pass AA (>= 4.5:1), 1 if any fail, 2 on usage error.`);
}

function formatAssessment(a: ContrastAssessment): string {
  const tick = (ok: boolean) => (ok ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m");
  const r = a.ratio.toFixed(2);
  const apca = a.apca_lc.toFixed(1);
  const rating =
    a.rating === "AAA"
      ? `\x1b[32m${a.rating}\x1b[0m`
      : a.rating === "AA"
        ? `\x1b[32m${a.rating}\x1b[0m`
        : a.rating === "AA Large"
          ? `\x1b[33m${a.rating}\x1b[0m`
          : `\x1b[31m${a.rating}\x1b[0m`;
  return [
    `${a.foreground} on ${a.background}`,
    `  ${a.foreground_hex} / ${a.background_hex}`,
    `  WCAG 2.1:  ${r}:1   ${rating}`,
    `  APCA Lc:   ${apca}`,
    `  ${tick(a.passes_aaa_normal)} AAA normal (≥7)    ${tick(a.passes_aa_normal)} AA normal (≥4.5)    ${tick(a.passes_aa_large)} AA large (≥3)`,
  ].join("\n");
}

async function readStdin(): Promise<string> {
  const chunks: Uint8Array[] = [];
  const decoder = new TextDecoder();
  for await (const chunk of Bun.stdin.stream()) chunks.push(chunk);
  return chunks.map((c) => decoder.decode(c)).join("");
}

export async function main(argv: string[] = Bun.argv.slice(2)): Promise<number> {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        json: { type: "boolean", default: false },
        stdin: { type: "boolean", default: false },
        help: { type: "boolean", short: "h", default: false },
      },
      allowPositionals: true,
      strict: true,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`error: ${msg}`);
    printHelp();
    return 2;
  }
  const { values, positionals } = parsed;

  if (values.help) { printHelp(); return 0; }

  // ── stdin mode: JSON array of [fg, bg] pairs in, array of assessments out ──
  if (values.stdin) {
    const raw = await readStdin();
    let pairs: unknown;
    try {
      pairs = JSON.parse(raw);
    } catch (err) {
      console.error(`error: stdin is not valid JSON: ${(err as Error).message}`);
      return 2;
    }
    if (!Array.isArray(pairs)) {
      console.error("error: --stdin expects a JSON array of [fg, bg] pairs");
      return 2;
    }

    const results: ContrastAssessment[] = [];
    let anyFailure = false;
    for (const [idx, entry] of pairs.entries()) {
      if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== "string" || typeof entry[1] !== "string") {
        console.error(`error: pair ${idx} is not a [string, string] tuple`);
        return 2;
      }
      try {
        const assessment = wcagAssess(entry[0], entry[1]);
        results.push(assessment);
        if (!assessment.passes_aa_normal) anyFailure = true;
      } catch (err) {
        console.error(`error: pair ${idx} (${entry[0]} / ${entry[1]}): ${(err as Error).message}`);
        return 2;
      }
    }

    if (values.json) {
      console.log(JSON.stringify(results, null, 2));
    } else {
      for (const a of results) {
        console.log(formatAssessment(a));
        console.log();
      }
    }
    return anyFailure ? 1 : 0;
  }

  // ── Pair mode: positional fg, bg ─────────────────────────────────────────
  if (positionals.length !== 2) {
    if (positionals.length === 0) { printHelp(); return 2; }
    console.error(`error: expected 2 positional args (foreground, background), got ${positionals.length}`);
    return 2;
  }

  let assessment: ContrastAssessment;
  try {
    assessment = wcagAssess(positionals[0]!, positionals[1]!);
  } catch (err) {
    console.error(`error: could not parse colors: ${(err as Error).message}`);
    return 2;
  }

  if (values.json) {
    console.log(JSON.stringify(assessment, null, 2));
  } else {
    console.log(formatAssessment(assessment));
  }
  return assessment.passes_aa_normal ? 0 : 1;
}

// Only run main() when executed directly, not when imported as a library.
if (import.meta.main) {
  main().then((code) => process.exit(code)).catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`fatal: ${msg}`);
    process.exit(1);
  });
}
