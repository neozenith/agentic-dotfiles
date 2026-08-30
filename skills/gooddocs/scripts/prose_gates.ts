#!/usr/bin/env bun
// Deterministic prose gates for the gooddocs doctrine (prose_style.md,
// structure.md rule 13). Parses markdown to mdast once per document, builds
// a shared model (paragraph and text views with code spans exempted by
// construction), and runs each PG rule as its own named function over that
// model. To add a rule: write one check function, register it in RULES, and
// add a catalogue row.

// ── Imports ───────────────────────────────────────────────────────────────
import { parseArgs } from "node:util";
import type { Code, InlineCode, Node, Paragraph, Root, Text } from "mdast";
import { fromMarkdown } from "mdast-util-from-markdown";
import { gfmFromMarkdown } from "mdast-util-gfm";
import { gfm } from "micromark-extension-gfm";
import { visitParents } from "unist-util-visit-parents";

// ── Configuration ─────────────────────────────────────────────────────────
const DEFAULT_MAX_WORDS = 25;
const TERMINALS = new Set([".", "!", "?", ":", ";"]);

// Fenced blocks in these languages hold markdown templates (e.g. a
// conventions or skeleton file shown verbatim): their prose is audited as
// embedded markdown instead of being exempt as code. Check-only — the
// reflow fix never rewrites through a fence boundary.
const MARKDOWN_FENCE_LANGS = new Set(["markdown", "md"]);

const RULE = {
  WRAP: "PG001",
  LENGTH: "PG002",
  SEMICOLON_LIST: "PG003",
  EM_DASH: "PG004",
  INTERPUNCT: "PG005",
  INTERPUNCT_RUN: "PG006",
  INLINE_ENUM: "PG007",
  LABELLED_RUN: "PG008",
  STACKED_RUNS: "PG009",
} as const;

const RULE_CATALOG: Array<{ id: string; summary: string }> = [
  { id: RULE.WRAP, summary: "mid-sentence line wrap (one sentence per line)" },
  { id: RULE.LENGTH, summary: "sentence longer than the word budget (default 25)" },
  { id: RULE.SEMICOLON_LIST, summary: "semicolon-delimited list (2+ ';' in one sentence)" },
  { id: RULE.EM_DASH, summary: "em-dash U+2014 in prose" },
  { id: RULE.INTERPUNCT, summary: "interpunct U+00B7 in prose" },
  { id: RULE.INTERPUNCT_RUN, summary: "interpunct-joined inline list (2+ separators)" },
  { id: RULE.INLINE_ENUM, summary: "enumeration markers (a)/(b) or (1)/(2) inlined in prose" },
  { id: RULE.LABELLED_RUN, summary: "comma-joined labelled run (3+ labelled segments)" },
  { id: RULE.STACKED_RUNS, summary: "interpunct runs stacked on several lines (nested list)" },
];

const USAGE = `usage: prose_gates.ts <file.md> [...more] [--fix] [--json] [--max-words N]

Deterministic prose gates:
${RULE_CATALOG.map((r) => `  ${r.id}  ${r.summary}`).join("\n")}

Code blocks are exempt, except fences tagged markdown/md: those hold
markdown templates and their body is audited recursively (check-only).

--fix reflows top-level and list paragraphs to one sentence per line
(${RULE.WRAP} only; every other finding is report-only). Exits 1 when
findings remain, 2 on usage error.`;

// ── Document model ────────────────────────────────────────────────────────
export interface Finding {
  file: string;
  line: number;
  rule: string;
  message: string;
}

// One paragraph with everything the rules need, derived in a single walk.
interface ParagraphView {
  raw: string; // exact source slice
  line: number;
  startOffset: number;
  endOffset: number;
  startColumn: number;
  prose: string; // text values joined; inline code becomes one CODE token
  codeRanges: Array<[number, number]>; // inline-code offsets in src
  inTable: boolean; // check rules skip table cells
  fixable: boolean; // reflow skips blockquotes and tables
}

interface TextView {
  value: string;
  line: number;
  offset: number | undefined;
}

// A fenced code block tagged markdown/md: a template whose body is itself
// markdown prose, audited recursively.
interface FenceView {
  value: string; // fence body (starts on the line after the opening fence)
  line: number; // line of the opening fence
}

interface DocModel {
  src: string;
  paragraphs: ParagraphView[];
  texts: TextView[]; // every prose text node, including headings and lists
  fences: FenceView[]; // embedded-markdown fences, audited recursively
}

const buildDocModel = (src: string): DocModel => {
  const tree: Root = fromMarkdown(src, {
    extensions: [gfm()],
    mdastExtensions: [gfmFromMarkdown()],
  });
  const paragraphs: ParagraphView[] = [];
  const texts: TextView[] = [];
  const fences: FenceView[] = [];
  const viewOf = new Map<Paragraph, ParagraphView>();
  const proseParts = new Map<Paragraph, string[]>();

  visitParents(tree, (node: Node, ancestors: Node[]) => {
    if (node.type === "code") {
      const c = node as Code;
      if (c.lang != null && MARKDOWN_FENCE_LANGS.has(c.lang) && c.position) {
        fences.push({ value: c.value, line: c.position.start.line });
      }
      return;
    }
    if (node.type === "paragraph") {
      const p = node as Paragraph;
      const pos = p.position;
      if (!pos || pos.start.offset == null || pos.end.offset == null) return;
      const inTable = ancestors.some((a) => a.type === "table" || a.type === "tableCell");
      const view: ParagraphView = {
        raw: src.slice(pos.start.offset, pos.end.offset),
        line: pos.start.line,
        startOffset: pos.start.offset,
        endOffset: pos.end.offset,
        startColumn: pos.start.column,
        prose: "",
        codeRanges: [],
        inTable,
        fixable: !inTable && !ancestors.some((a) => a.type === "blockquote"),
      };
      paragraphs.push(view);
      viewOf.set(p, view);
      proseParts.set(p, []);
    }
    const paragraph = [...ancestors].reverse().find((a): a is Paragraph => a.type === "paragraph");
    if (node.type === "text") {
      const t = node as Text;
      texts.push({ value: t.value, line: t.position?.start.line ?? 0, offset: t.position?.start.offset });
      if (paragraph) proseParts.get(paragraph)?.push(t.value);
    } else if (node.type === "inlineCode" && paragraph) {
      const c = node as InlineCode;
      proseParts.get(paragraph)?.push("CODE");
      const view = viewOf.get(paragraph);
      if (view && c.position?.start.offset != null && c.position.end.offset != null) {
        view.codeRanges.push([c.position.start.offset, c.position.end.offset]);
      }
    }
  });

  for (const [p, parts] of proseParts) {
    const view = viewOf.get(p);
    if (view) view.prose = parts.join(" ").replace(/\s+/g, " ").trim();
  }
  return { src, paragraphs, texts, fences };
};

const inRanges = (offset: number, ranges: Array<[number, number]>): boolean =>
  ranges.some(([a, b]) => offset >= a && offset < b);

const sentences = (text: string): string[] =>
  text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

// ── Rules (one named function each) ───────────────────────────────────────

// PG001: a newline inside a paragraph whose preceding non-space character
// does not end a sentence is a mid-sentence wrap.
const checkMidSentenceWrap = (doc: DocModel, file: string): Finding[] => {
  const findings: Finding[] = [];
  for (const p of doc.paragraphs) {
    if (p.inTable) continue;
    for (let i = 0; i < p.raw.length; i++) {
      if (p.raw[i] !== "\n") continue;
      if (inRanges(p.startOffset + i, p.codeRanges)) continue;
      let j = i - 1;
      while (j >= 0 && (p.raw[j] === " " || p.raw[j] === "\t" || p.raw[j] === "\\")) j--;
      if (j >= 0 && !TERMINALS.has(p.raw[j] as string)) {
        const line = p.line + p.raw.slice(0, i).split("\n").length - 1;
        findings.push({ file, line, rule: RULE.WRAP, message: "mid-sentence line wrap; write one sentence per line" });
      }
    }
  }
  return findings;
};

// PG002: sentences over the word budget are hard to unpack, especially for
// ESL readers and translators.
const checkSentenceBudget = (doc: DocModel, file: string, maxWords: number): Finding[] => {
  const findings: Finding[] = [];
  for (const p of doc.paragraphs) {
    if (p.inTable) continue;
    for (const s of sentences(p.prose)) {
      const words = s.split(/\s+/).length;
      if (words > maxWords) {
        findings.push({
          file,
          line: p.line,
          rule: RULE.LENGTH,
          message: `sentence has ${words} words (budget ${maxWords}): "${s.slice(0, 60)}..."`,
        });
      }
    }
  }
  return findings;
};

// PG003: a run of items joined by semicolons is a wall of text hiding a list.
const checkSemicolonList = (doc: DocModel, file: string): Finding[] => {
  const findings: Finding[] = [];
  for (const p of doc.paragraphs) {
    if (p.inTable) continue;
    for (const s of sentences(p.prose)) {
      const semis = (s.match(/;/g) ?? []).length;
      if (semis >= 2) {
        findings.push({
          file,
          line: p.line,
          rule: RULE.SEMICOLON_LIST,
          message: `semicolon-delimited list (${semis} ';'); promote to a bullet list`,
        });
      }
    }
  }
  return findings;
};

// PG007: parenthesised enumerators inlined in one paragraph are a hidden
// list. Requiring the first two members of a family keeps citations and a
// lone "(a)" reference from firing.
const ENUM_FAMILIES: Array<[string, string]> = [
  ["(a)", "(b)"],
  ["(1)", "(2)"],
  ["(i)", "(ii)"],
];

const checkInlineEnumeration = (doc: DocModel, file: string): Finding[] => {
  const findings: Finding[] = [];
  for (const p of doc.paragraphs) {
    if (p.inTable) continue;
    for (const [first, second] of ENUM_FAMILIES) {
      if (p.prose.includes(first) && p.prose.includes(second)) {
        findings.push({
          file,
          line: p.line,
          rule: RULE.INLINE_ENUM,
          message: `enumeration ${first} ${second} ... inlined in prose; promote to a bullet list`,
        });
        break;
      }
    }
  }
  return findings;
};

// PG008: one sentence stringing 3+ comma-separated segments each led by a
// label (an inline-code span, or an identifier like PG001 / MD025 / S4)
// WITH content after it is a hidden list of labelled items. Bare labels
// ("A, B, and C are interchangeable") are a subject enumeration, not a
// list. An optional "Rules: " style intro on the first segment, and a
// joining "and"/"or", are tolerated.
const LABELLED_SEGMENT = /^(?:and\s+|or\s+)?(?:[A-Za-z][\w\s-]{0,24}:\s*)?(?:CODE|[A-Z][A-Za-z]*\d[\w/-]*)\s+\S/;

const checkLabelledRun = (doc: DocModel, file: string): Finding[] => {
  const findings: Finding[] = [];
  for (const p of doc.paragraphs) {
    if (p.inTable) continue;
    for (const s of sentences(p.prose)) {
      const labelled = s.split(/,\s+/).filter((seg) => LABELLED_SEGMENT.test(seg)).length;
      if (labelled >= 3) {
        findings.push({
          file,
          line: p.line,
          rule: RULE.LABELLED_RUN,
          message: `comma-joined run of ${labelled} labelled items; promote to a bullet list`,
        });
      }
    }
  }
  return findings;
};

// Paragraphs whose prose joins a run of items with 2+ interpunct
// separators. Shared by PG006/PG009 (report the run) and PG005 (suppressed
// inside a reported run) as an explicit data dependency, not shared state.
interface InterpunctRun {
  range: [number, number];
  line: number;
  separators: number;
  lines: number; // source lines of the paragraph that carry a separator
}

const interpunctRuns = (doc: DocModel): InterpunctRun[] => {
  const runs: InterpunctRun[] = [];
  for (const p of doc.paragraphs) {
    if (p.inTable) continue;
    const separators = (p.prose.match(/·/g) ?? []).length;
    if (separators >= 2) {
      const lines = p.raw.split("\n").filter((l) => l.includes("·")).length;
      runs.push({ range: [p.startOffset, p.endOffset], line: p.line, separators, lines });
    }
  }
  return runs;
};

// PG006: a single-line interpunct-joined run is a disguised flat list.
// PG009: runs stacked on 2+ source lines of one paragraph are a two-level
// structure; the fix is a nested list (one parent per line), so PG009
// replaces PG006 for that paragraph.
const checkInterpunctRun = (runs: InterpunctRun[], file: string): Finding[] =>
  runs.map((r) =>
    r.lines >= 2
      ? {
          file,
          line: r.line,
          rule: RULE.STACKED_RUNS,
          message: `interpunct runs stacked on ${r.lines} lines; promote to a nested list`,
        }
      : {
          file,
          line: r.line,
          rule: RULE.INTERPUNCT_RUN,
          message: `interpunct-joined inline list (${r.separators + 1} items); promote to a bullet list`,
        },
  );

// PG004/PG005: glyph tells in prose text nodes only, so code is exempt by
// construction. A stray interpunct inside a reported run is not re-flagged.
const checkEmDash = (doc: DocModel, file: string): Finding[] =>
  doc.texts
    .filter((t) => t.value.includes("—"))
    .map((t) => ({
      file,
      line: t.line,
      rule: RULE.EM_DASH,
      message: "em-dash in prose; use comma, colon, parentheses, or two sentences",
    }));

const checkInterpunct = (doc: DocModel, file: string, suppressed: Array<[number, number]>): Finding[] =>
  doc.texts
    .filter((t) => t.value.includes("·") && !(t.offset != null && inRanges(t.offset, suppressed)))
    .map((t) => ({
      file,
      line: t.line,
      rule: RULE.INTERPUNCT,
      message: "interpunct in prose; use a comma, slash, or a list",
    }));

// ── Composition ───────────────────────────────────────────────────────────
const checkModel = (doc: DocModel, file: string, maxWords: number): Finding[] => {
  const runs = interpunctRuns(doc);
  const findings = [
    ...checkMidSentenceWrap(doc, file),
    ...checkSentenceBudget(doc, file, maxWords),
    ...checkSemicolonList(doc, file),
    ...checkInlineEnumeration(doc, file),
    ...checkLabelledRun(doc, file),
    ...checkEmDash(doc, file),
    ...checkInterpunct(
      doc,
      file,
      runs.map((r) => r.range),
    ),
    ...checkInterpunctRun(runs, file),
  ];
  // Embedded markdown templates: audit the fence body as its own document
  // and shift findings to file coordinates (body starts one line below the
  // opening fence).
  for (const fence of doc.fences) {
    for (const f of checkModel(buildDocModel(fence.value), file, maxWords)) {
      findings.push({ ...f, line: fence.line + f.line });
    }
  }
  return findings.sort((a, b) => a.line - b.line || a.rule.localeCompare(b.rule));
};

export const checkMarkdown = (src: string, file: string, maxWords: number = DEFAULT_MAX_WORDS): Finding[] =>
  checkModel(buildDocModel(src), file, maxWords);

// ── Fix: sentence-per-line reflow (PG001 only) ────────────────────────────
const reflowEdits = (doc: DocModel): Array<{ start: number; end: number; text: string }> => {
  const edits: Array<{ start: number; end: number; text: string }> = [];
  for (const p of doc.paragraphs) {
    if (!p.fixable) continue;

    // Continuation lines keep the paragraph's own indent column.
    const indent = " ".repeat(p.startColumn - 1);
    const joined = p.raw.replace(/[ \t]*\n[ \t]*/g, " ");

    // Sentence terminals inside code spans must not split; masking the
    // backtick spans keeps boundaries honest without offset bookkeeping.
    const masked = joined.replace(/`[^`]*`/g, (m) => "x".repeat(m.length));
    const out: string[] = [];
    let last = 0;
    const boundary = /[.!?]\s+(?=[A-Z`"'([])/g;
    let m: RegExpExecArray | null = boundary.exec(masked);
    while (m !== null) {
      out.push(joined.slice(last, m.index + 1));
      last = m.index + m[0].length;
      m = boundary.exec(masked);
    }
    out.push(joined.slice(last));
    const text = out.map((s, i) => (i === 0 ? s.trim() : indent + s.trim())).join("\n");
    if (text !== p.raw) edits.push({ start: p.startOffset, end: p.endOffset, text });
  }
  return edits;
};

const applyEdits = (src: string, edits: Array<{ start: number; end: number; text: string }>): string => {
  let result = src;
  for (const e of edits.sort((a, b) => b.start - a.start)) {
    result = result.slice(0, e.start) + e.text + result.slice(e.end);
  }
  return result;
};

export const fixMarkdown = (src: string): string => applyEdits(src, reflowEdits(buildDocModel(src)));

// ── CLI ───────────────────────────────────────────────────────────────────
export const main = async (argv: string[] = Bun.argv.slice(2)): Promise<number> => {
  let values: { fix?: boolean; json?: boolean; help?: boolean; "max-words"?: string };
  let positionals: string[];
  try {
    ({ values, positionals } = parseArgs({
      args: argv,
      options: {
        fix: { type: "boolean", default: false },
        json: { type: "boolean", default: false },
        help: { type: "boolean", short: "h", default: false },
        "max-words": { type: "string" },
      },
      allowPositionals: true,
      strict: true,
    }));
  } catch (err) {
    console.error(`error: ${err instanceof Error ? err.message : String(err)}`);
    console.error(USAGE);
    return 2;
  }
  if (values.help) {
    console.log(USAGE);
    return 0;
  }
  const maxWords = values["max-words"] === undefined ? DEFAULT_MAX_WORDS : Number(values["max-words"]);
  if (positionals.length === 0 || Number.isNaN(maxWords) || maxWords < 1) {
    console.error(USAGE);
    return 2;
  }

  // Files are independent; parse once per file and re-parse only when a
  // fix actually changed the bytes (offsets move). Index order keeps the
  // output deterministic.
  const perFile = await Promise.all(
    positionals.map(async (file) => {
      const src = await Bun.file(file).text();
      let doc = buildDocModel(src);
      if (values.fix) {
        const edits = reflowEdits(doc);
        if (edits.length > 0) {
          const fixed = applyEdits(src, edits);
          await Bun.write(file, fixed);
          doc = buildDocModel(fixed);
        }
      }
      return checkModel(doc, file, maxWords);
    }),
  );
  const all = perFile.flat();

  if (values.json) {
    console.log(JSON.stringify({ findings: all, files: positionals.length }, null, 2));
  } else {
    for (const f of all) console.log(`${f.file}:${f.line} ${f.rule} ${f.message}`);
    console.log(`${all.length} finding(s) in ${positionals.length} file(s)`);
  }
  return all.length > 0 ? 1 : 0;
};

if (import.meta.main) {
  main().then(
    (code) => process.exit(code),
    (err: unknown) => {
      console.error(`error: ${err instanceof Error ? err.message : String(err)}`);
      process.exit(1);
    },
  );
}
