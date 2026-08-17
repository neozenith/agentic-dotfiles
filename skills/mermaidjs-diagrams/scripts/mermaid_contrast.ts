#!/usr/bin/env bun
// Mermaid Source Contrast Auditor.
//
// Extracts every classDef/style/linkStyle color directive from a mermaid .mmd
// or .md file and scores two kinds of color pair:
//
//   text:    fill × color     (body text vs node background — must be >= 4.5)
//   border:  fill × stroke    (node border vs fill — UI-component rule, >= 3)
//
// Only pairs where BOTH sides are explicitly declared are scored; unset
// properties fall back to mermaid theme defaults that we can't statically
// resolve without rendering. Those are flagged separately as "skipped".
//
// Companion to mermaid_complexity.ts — same CLI shape, same exit conventions.
// For ad-hoc color comparison (e.g. colors eyedropped from a screenshot), use
// color_contrast.ts directly.
//
// Usage:
//   bun run mermaid_contrast.ts path/to/diagram.mmd
//   bun run mermaid_contrast.ts docs/diagrams/
//   bun run mermaid_contrast.ts docs/architecture.md --json
//
// Exit codes: 0 all pairs >= AA, 1 any pair fails AA (text <4.5 or border <3).

import { parseArgs } from "node:util";
import { existsSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";

import { extractMarkdownFences } from "./mermaid_complexity.ts";
import {
  compositeOver,
  extractStyleDirectives,
  wcagAssess,
  type ContrastAssessment,
  type StyleDirective,
} from "./color_contrast.ts";

// ─── Profiles (context-aware: who controls the label text?) ──────────────────
//
// github (default for plain .md / .mmd): YOU control the text — score the
//   declared fill×color (text) and fill×stroke (border) as authored.
//
// mkdocs-material: the HOST theme FORCES the label text per theme and overrides
//   any classDef color:. A diagram is correct only if it reads in BOTH themes.
//   So we ignore color:, composite the (often translucent) fill over each theme's
//   page background, and score the host's forced text against the resulting box
//   in light AND dark. See resources/color_theming.md §11.

export type Profile = "github" | "mkdocs-material";

// Material for MkDocs stock-theme anchors (read off --md-* CSS vars; see §11).
// dark bg ≈ rgb(30,33,41); dark text ≈ hsl(225,18%,86%) at 0.82 alpha.
const MKDOCS_MATERIAL = {
  light: { bg: "#ffffff", text: "#36464e" },
  dark: { bg: "#1e2129", text: "hsl(225 18% 86% / 0.82)" },
} as const;

// ─── Types ───────────────────────────────────────────────────────────────────

export type PairKind = "text" | "border";
export type Theme = "light" | "dark";

export interface ContrastPair {
  kind: PairKind; // text = fill×color, border = fill×stroke
  selector: string; // classDef/style name
  directive_kind: StyleDirective["kind"];
  foreground: string; // text: color, border: stroke (composited under mkdocs)
  background: string; // fill (composited box under mkdocs)
  line: number; // where the directive appears
  assessment: ContrastAssessment;
  passes: boolean; // text: ratio >= 4.5; border: ratio >= 3
  theme?: Theme; // set only under the mkdocs-material profile (light/dark pass)
  advisory?: boolean; // reported but NOT gating (mkdocs border: stroke on a faint
  // fill can't clear 3:1 in both themes for a saturated hue; the category is also
  // carried by the AAA label + tint, so the border is reinforcement, not gating).
}

export interface SkippedDirective {
  selector: string;
  directive_kind: StyleDirective["kind"];
  line: number;
  reason: string; // e.g. "no fill declared", "no color or stroke declared"
}

export interface DiagramContrastReport {
  file_path: string;
  profile: Profile;
  fence?: {
    index: number;
    line_start: number;
    line_end: number;
  };
  pairs: ContrastPair[];
  skipped: SkippedDirective[];
  pass_count: number;
  fail_count: number;
}

// ─── Scoring ─────────────────────────────────────────────────────────────────

const AA_NORMAL = 4.5; // text rule
const AA_NON_TEXT = 3.0; // UI-component / border rule

function scorePair(kind: PairKind, directive: StyleDirective, fg: string, bg: string): ContrastPair {
  const assessment = wcagAssess(fg, bg);
  const threshold = kind === "text" ? AA_NORMAL : AA_NON_TEXT;
  return {
    kind,
    selector: directive.selector,
    directive_kind: directive.kind,
    foreground: fg,
    background: bg,
    line: directive.line,
    assessment,
    passes: assessment.ratio >= threshold,
  };
}

/**
 * Score one diagram's worth of style directives.
 * Only classDef and style kinds carry fill/color/stroke; inlineClass and
 * linkStyle are informational and skipped here.
 */
export function scoreDirectives(directives: StyleDirective[]): {
  pairs: ContrastPair[];
  skipped: SkippedDirective[];
} {
  const pairs: ContrastPair[] = [];
  const skipped: SkippedDirective[] = [];

  for (const d of directives) {
    if (d.kind !== "classDef" && d.kind !== "style") continue;

    const fill = d.properties.fill;
    const color = d.properties.color;
    const stroke = d.properties.stroke;

    if (!fill) {
      // Without fill we have no background anchor for either pair.
      skipped.push({
        selector: d.selector,
        directive_kind: d.kind,
        line: d.line,
        reason:
          color || stroke ? "no fill declared — can't anchor text/border contrast" : "no color properties declared",
      });
      continue;
    }

    if (color) {
      try {
        pairs.push(scorePair("text", d, color, fill));
      } catch (err) {
        skipped.push({
          selector: d.selector,
          directive_kind: d.kind,
          line: d.line,
          reason: `text pair unparseable: ${(err as Error).message}`,
        });
      }
    }
    if (stroke) {
      try {
        pairs.push(scorePair("border", d, stroke, fill));
      } catch (err) {
        skipped.push({
          selector: d.selector,
          directive_kind: d.kind,
          line: d.line,
          reason: `border pair unparseable: ${(err as Error).message}`,
        });
      }
    }
    if (!color && !stroke) {
      skipped.push({
        selector: d.selector,
        directive_kind: d.kind,
        line: d.line,
        reason: "only fill declared — text/border use theme defaults",
      });
    }
  }

  return { pairs, skipped };
}

// ─── mkdocs-material scoring (host forces text; composite over both themes) ──

const mkdocsBox = (fill: string, theme: Theme): string => compositeOver(fill, MKDOCS_MATERIAL[theme].bg);

function scoreMkdocsPair(kind: PairKind, d: StyleDirective, theme: Theme, fgRaw: string, box: string): ContrastPair {
  // The foreground (host text or stroke) may itself be translucent — composite it
  // onto the already-composited box, then score the two opaque colours.
  const fgEff = compositeOver(fgRaw, box);
  const assessment = wcagAssess(fgEff, box);
  const threshold = kind === "text" ? AA_NORMAL : AA_NON_TEXT;
  return {
    kind,
    selector: d.selector,
    directive_kind: d.kind,
    foreground: fgEff,
    background: box,
    line: d.line,
    assessment,
    passes: assessment.ratio >= threshold,
    theme,
    advisory: kind === "border", // mkdocs borders are reported but not gating
  };
}

/**
 * Score directives under the mkdocs-material profile: `color:` is ignored (the
 * host forces it), and each fill is composited over BOTH theme backgrounds, then
 * the host-forced label text is scored against the resulting box in light + dark.
 * An opaque fill that only worked for one theme now fails the other — by design.
 */
export function scoreDirectivesMkdocs(directives: StyleDirective[]): {
  pairs: ContrastPair[];
  skipped: SkippedDirective[];
} {
  const pairs: ContrastPair[] = [];
  const skipped: SkippedDirective[] = [];
  const themes: Theme[] = ["light", "dark"];

  for (const d of directives) {
    if (d.kind !== "classDef" && d.kind !== "style") continue;
    const fill = d.properties.fill;
    const stroke = d.properties.stroke;

    if (!fill) {
      skipped.push({
        selector: d.selector,
        directive_kind: d.kind,
        line: d.line,
        reason: "no fill declared — host theme controls text; nothing to anchor",
      });
      continue;
    }
    if (d.properties.color) {
      skipped.push({
        selector: d.selector,
        directive_kind: d.kind,
        line: d.line,
        reason: "color: ignored under mkdocs-material (host theme forces label text)",
      });
    }

    for (const theme of themes) {
      let box: string;
      try {
        box = mkdocsBox(fill, theme);
      } catch (err) {
        skipped.push({
          selector: d.selector,
          directive_kind: d.kind,
          line: d.line,
          reason: `fill unparseable: ${(err as Error).message}`,
        });
        break;
      }
      // The forced text and the composited box are both known-valid here, so the
      // text pair can't throw (only the fill — handled above — or a bad stroke can).
      pairs.push(scoreMkdocsPair("text", d, theme, MKDOCS_MATERIAL[theme].text, box));
      if (stroke) {
        try {
          pairs.push(scoreMkdocsPair("border", d, theme, stroke, box));
        } catch (err) {
          skipped.push({
            selector: d.selector,
            directive_kind: d.kind,
            line: d.line,
            reason: `border pair unparseable: ${(err as Error).message}`,
          });
        }
      }
    }
  }
  return { pairs, skipped };
}

/** Dispatch scoring by profile. */
export function scoreForProfile(
  directives: StyleDirective[],
  profile: Profile,
): { pairs: ContrastPair[]; skipped: SkippedDirective[] } {
  return profile === "mkdocs-material" ? scoreDirectivesMkdocs(directives) : scoreDirectives(directives);
}

/** Auto-detect the render context: an ancestor `mkdocs.yml` ⇒ mkdocs-material. */
export function detectProfile(filePath: string): Profile {
  let dir = dirname(resolve(filePath));
  for (let i = 0; i < 20; i++) {
    if (existsSync(join(dir, "mkdocs.yml")) || existsSync(join(dir, "mkdocs.yaml"))) return "mkdocs-material";
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return "github";
}

// ─── File analysis ───────────────────────────────────────────────────────────

interface DiagramEntry {
  content: string;
  fence?: DiagramContrastReport["fence"];
}

function isMarkdownFile(filePath: string): boolean {
  const lower = filePath.toLowerCase();
  return lower.endsWith(".md") || lower.endsWith(".markdown");
}

async function readDiagrams(filePath: string): Promise<DiagramEntry[]> {
  const content = await Bun.file(filePath).text();
  if (isMarkdownFile(filePath)) {
    return extractMarkdownFences(content).map((entry) => ({
      content: entry.content,
      fence: entry.fence
        ? { index: entry.fence.index, line_start: entry.fence.line_start, line_end: entry.fence.line_end }
        : undefined,
    }));
  }
  return [{ content }];
}

export async function auditFile(
  filePath: string,
  profileArg: Profile | "auto" = "auto",
): Promise<DiagramContrastReport[]> {
  const profile = profileArg === "auto" ? detectProfile(filePath) : profileArg;
  const diagrams = await readDiagrams(filePath);
  const out: DiagramContrastReport[] = [];
  for (const entry of diagrams) {
    const directives = extractStyleDirectives(entry.content);
    const { pairs, skipped } = scoreForProfile(directives, profile);
    // Fence-local line numbers → absolute markdown line numbers so users can
    // jump straight to the offending directive in their editor.
    const offset = entry.fence ? entry.fence.line_start : 0;
    const offsetPairs = pairs.map((p) => ({ ...p, line: p.line + offset }));
    const offsetSkipped = skipped.map((s) => ({ ...s, line: s.line + offset }));
    out.push({
      file_path: filePath,
      profile,
      fence: entry.fence,
      pairs: offsetPairs,
      skipped: offsetSkipped,
      pass_count: offsetPairs.filter((p) => p.passes).length,
      fail_count: offsetPairs.filter((p) => !p.passes && !p.advisory).length,
    });
  }
  return out;
}

export function auditContent(
  content: string,
  filePath = "<inline>",
  profile: Profile = "github",
): DiagramContrastReport {
  const directives = extractStyleDirectives(content);
  const { pairs, skipped } = scoreForProfile(directives, profile);
  return {
    file_path: filePath,
    profile,
    pairs,
    skipped,
    pass_count: pairs.filter((p) => p.passes).length,
    fail_count: pairs.filter((p) => !p.passes && !p.advisory).length,
  };
}

// ─── Formatting ──────────────────────────────────────────────────────────────

const C = {
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  dim: "\x1b[2m",
  bold: "\x1b[1m",
  reset: "\x1b[0m",
};

function formatReport(r: DiagramContrastReport): string {
  const lines: string[] = [];
  const profileTag = r.profile === "mkdocs-material" ? ` ${C.dim}[profile mkdocs-material]${C.reset}` : "";
  const header = `${C.bold}${basename(r.file_path)}${C.reset}${profileTag}${r.fence ? ` ${C.dim}[fence ${r.fence.index} L${r.fence.line_start}-L${r.fence.line_end}]${C.reset}` : ""}`;
  lines.push(`\n${header}`);

  if (r.pairs.length === 0 && r.skipped.length === 0) {
    lines.push(`  ${C.dim}(no style directives found)${C.reset}`);
    return lines.join("\n");
  }

  for (const p of r.pairs) {
    // Advisory (non-gating) failures show as a yellow ⚠, not a red ✗.
    const icon = p.passes ? `${C.green}✓${C.reset}` : p.advisory ? `${C.yellow}⚠${C.reset}` : `${C.red}✗${C.reset}`;
    const ratio = p.assessment.ratio.toFixed(2).padStart(5);
    const rating = p.assessment.rating;
    const ratingColor = rating === "AAA" || rating === "AA" ? C.green : rating === "AA Large" ? C.yellow : C.red;
    const threshold = p.kind === "text" ? "≥4.5" : "≥3.0";
    const themeTag = p.theme ? `${C.dim}${p.theme.padEnd(5)}${C.reset} ` : "";
    const advisoryTag = p.advisory && !p.passes ? ` ${C.dim}(advisory)${C.reset}` : "";
    lines.push(
      `  ${icon} L${String(p.line).padStart(3)} ${themeTag}${p.directive_kind} ${C.bold}${p.selector}${C.reset}  ${p.kind.padEnd(6)} ${ratio}:1 (${threshold}) ${ratingColor}${rating}${C.reset}  ${C.dim}${p.foreground} on ${p.background}${C.reset}${advisoryTag}`,
    );
  }

  for (const s of r.skipped) {
    lines.push(
      `  ${C.dim}- L${String(s.line).padStart(3)} ${s.directive_kind} ${s.selector}  skipped: ${s.reason}${C.reset}`,
    );
  }

  return lines.join("\n");
}

function formatSummary(reports: DiagramContrastReport[]): string {
  const totalPass = reports.reduce((n, r) => n + r.pass_count, 0);
  const totalFail = reports.reduce((n, r) => n + r.fail_count, 0);
  const totalSkip = reports.reduce((n, r) => n + r.skipped.length, 0);
  const color = totalFail > 0 ? C.red : C.green;
  return `\n${color}${C.bold}Summary:${C.reset} ${totalPass} pass, ${totalFail} fail, ${totalSkip} skipped across ${reports.length} diagram(s).`;
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

const DIRECTORY_FILE_EXTS = new Set([".mmd", ".md", ".markdown"]);

function collectFiles(paths: string[]): string[] {
  const out: string[] = [];
  for (const p of paths) {
    const abs = resolve(p);
    try {
      const st = statSync(abs);
      if (st.isDirectory()) {
        for (const name of readdirSync(abs)) {
          if (DIRECTORY_FILE_EXTS.has(extname(name).toLowerCase())) {
            out.push(join(abs, name));
          }
        }
      } else {
        out.push(abs);
      }
    } catch {
      console.error(`warning: cannot stat ${abs}`);
    }
  }
  return out;
}

function printHelp(): void {
  console.log(`\
mermaid_contrast.ts — WCAG contrast audit for mermaid style directives

Usage:
  bun run mermaid_contrast.ts <file-or-dir>... [--json] [--quiet]

Scores every classDef/style fill×color (text) and fill×stroke (border) pair
against WCAG AA thresholds (4.5:1 for text, 3:1 for UI borders).

The audit is context-aware (see resources/color_theming.md §11):
  github          You control the text — score declared fill×color / fill×stroke.
  mkdocs-material The host theme FORCES label text and ignores color:. Each fill is
                  composited over BOTH theme backgrounds and the forced text is
                  scored in light AND dark — translucent dual-theme fills.
  auto (default)  mkdocs-material if an ancestor mkdocs.yml exists, else github.

Options:
  --profile P   auto | github | mkdocs-material  (default: auto)
  --json        Machine-readable output (array of DiagramContrastReport)
  --summary     Print only the per-file summary, not every pair
  --quiet, -q   Suppress non-failure lines
  -h, --help    Show this help

Exit codes: 0 if all pairs pass, 1 if any fail, 2 on usage error.

For ad-hoc color comparison (e.g. from a screenshot), use color_contrast.ts
(its --over flag composites a translucent fill over a page bg).`);
}

export async function main(argv: string[] = Bun.argv.slice(2)): Promise<number> {
  let parsed: ReturnType<typeof parseArgs>;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        json: { type: "boolean", default: false },
        summary: { type: "boolean", default: false },
        quiet: { type: "boolean", short: "q", default: false },
        profile: { type: "string", default: "auto" },
        help: { type: "boolean", short: "h", default: false },
      },
      allowPositionals: true,
      strict: true,
    });
  } catch (err) {
    console.error(`error: ${(err as Error).message}`);
    printHelp();
    return 2;
  }
  const { values, positionals } = parsed;

  if (values.help) {
    printHelp();
    return 0;
  }
  if (positionals.length === 0) {
    printHelp();
    return 2;
  }

  const profileArg = String(values.profile) as Profile | "auto";
  if (profileArg !== "auto" && profileArg !== "github" && profileArg !== "mkdocs-material") {
    console.error(`error: --profile must be auto, github, or mkdocs-material (got '${profileArg}')`);
    return 2;
  }

  const files = collectFiles(positionals);
  if (files.length === 0) {
    console.error("error: no matching files");
    return 1;
  }

  const reports: DiagramContrastReport[] = [];
  for (const f of files.sort()) {
    reports.push(...(await auditFile(f, profileArg)));
  }

  if (values.json) {
    console.log(JSON.stringify(reports, null, 2));
  } else if (values.summary) {
    console.log(formatSummary(reports));
  } else {
    for (const r of reports) {
      if (values.quiet && r.fail_count === 0) continue;
      console.log(formatReport(r));
    }
    console.log(formatSummary(reports));
  }

  const anyFail = reports.some((r) => r.fail_count > 0);
  return anyFail ? 1 : 0;
}

if (import.meta.main) {
  main()
    .then((code) => process.exit(code))
    .catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`fatal: ${msg}`);
      process.exit(1);
    });
}
