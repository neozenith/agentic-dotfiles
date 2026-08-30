#!/usr/bin/env bun
// Index a markdown document into a queryable YAML (or JSON) sibling, reversibly.
//
// The strategy is: use mdast to find BOUNDARIES, not to represent CONTENT.
// Every mdast node carries position offsets, so a block's exact source text is a
// slice of the original file. Storing the slice rather than a re-serialisation
// keeps inline formatting, keeps fenced code verbatim, keeps block order, and
// makes the round trip byte-exact - which is what lets a generated sibling be
// regenerated without ever reformatting the document it indexes.

// ── Imports (stdlib first, then packages) ─────────────────────────────────
import { parseArgs } from "node:util";
import type { Heading, Root, RootContent, TableCell } from "mdast";
import { toString as mdToString } from "mdast-util-to-string";
import remarkFrontmatter from "remark-frontmatter";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import { unified } from "unified";
import { parse as parseYaml } from "yaml";

// ── Types ─────────────────────────────────────────────────────────────────

/** Anything mdast has located in the source: all `slice` needs. */
export type Positioned = {
  position?: { start: { offset?: number }; end: { offset?: number } };
};

export type Block = { type: string; md: string; [meta: string]: unknown };

export type Section = {
  key: string;
  path: string;
  heading: string;
  depth: number;
  gap?: number;
  content?: string | Block[];
  sections?: Section[];
};

export type Indexed = {
  frontmatter?: unknown;
  preamble?: string | Block[];
  sections: Section[];
  leading: number;
  trailing: number;
};

// ── Configuration ─────────────────────────────────────────────────────────

const RESERVED = new Set(["y", "n", "yes", "no", "true", "false", "on", "off", "null", "~"]);

const parser = unified().use(remarkParse).use(remarkFrontmatter, ["yaml"]).use(remarkGfm);

// ── Core ──────────────────────────────────────────────────────────────────

export const slug = (s: string): string =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");

/**
 * Derived metadata per block type, so a consumer can query without re-parsing
 * the slice. Structural blocks expose their parts: a table becomes a header plus
 * one map per row, a list becomes an array of item slices. `md` stays the
 * byte-exact source and remains what reconstruction reads, so a projection can
 * never cost fidelity - it is an index over the slice, not a replacement.
 *
 * Cell and item values are themselves slices, so inline formatting survives into
 * the index: a cell reading `**13 ms**` indexes as `**13 ms**`, not as flattened
 * text. Flattening is lossy in one direction only, and `mdToString` is available
 * to any consumer that wants the other.
 */
export const meta = (node: RootContent, between: (a: Positioned, b: Positioned) => string): Record<string, unknown> => {
  const slice = (n: Positioned): string => between(n, n);
  switch (node.type) {
    case "code":
      return node.lang ? { lang: node.lang } : {};
    case "list":
      return { ordered: !!node.ordered, items: node.children.map((li) => slice(li).trim()) };
    case "table": {
      const [head, ...body] = node.children;
      if (!head) return {};
      const header = head.children.map((c) => mdToString(c));
      const keys = header.map(slug);
      // A tableCell's own offsets span its `|` delimiters, so slicing the cell
      // yields "| 44 ms". Span its children instead: first child start to last
      // child end is the content without the table syntax around it.
      const cell = (c: TableCell): string => {
        const first = c.children[0];
        const last = c.children[c.children.length - 1];
        return first && last ? between(first, last).trim() : "";
      };
      const declared = node.align?.filter((a) => a) ?? [];
      return {
        header,
        // mdast spells an unaligned column `null`; say so in words, and omit the
        // key entirely when the table declares no alignment at all.
        ...(declared.length ? { align: node.align?.map((a) => a ?? "default") } : {}),
        rows: body.map((row) => Object.fromEntries(row.children.map((c, i) => [keys[i] ?? `col_${i + 1}`, cell(c)]))),
      };
    }
    case "heading":
      return { depth: node.depth };
    default:
      return {};
  }
};

/** Offsets are optional in the mdast types but always present after a parse. */
const startOf = (n: Positioned): number => n.position?.start.offset ?? 0;
const endOf = (n: Positioned): number => n.position?.end.offset ?? 0;

export const index = (source: string): Indexed => {
  const tree = parser.parse(source) as Root;
  // The slice is the content. mdast only says where it starts and stops.
  const between = (a: Positioned, b: Positioned): string => source.slice(startOf(a), endOf(b));
  const slice = (n: Positioned): string => between(n, n);

  let frontmatter: unknown;
  const root: Section[] = [];
  // Blocks before any heading. A document whose title lives in frontmatter has
  // no H1, so this is not an edge case - it is the normal shape for a generated
  // sibling, and dropping it silently loses the document's opening.
  const preamble: Block[] = [];
  const open = new Map<number, Section>();

  // Blank lines after each top-level node. Normally one; where it is not - two
  // fences butted together to show a command and its output, or an extra line
  // before a heading - it must be recorded, because "join everything with a
  // blank line" silently reformats the document.
  const gapAfter = new Map<RootContent, number>();
  tree.children.forEach((node, i) => {
    const next = tree.children[i + 1];
    if (!next || node.type === "yaml") return;
    gapAfter.set(node, source.slice(endOf(node), startOf(next)).split("\n").length - 2);
  });

  const push = (node: RootContent): void => {
    const target = open.get(Math.max(...[...open.keys()], 0));
    const block: Block = { type: node.type, md: slice(node), ...meta(node, between) };
    const gap = gapAfter.get(node);
    if (gap !== undefined && gap !== 1) block.gap = gap;
    if (!target) {
      preamble.push(block);
      return;
    }
    if (Array.isArray(target.content)) target.content.push(block);
    else target.content = [block];
  };

  for (const node of tree.children) {
    if (node.type === "yaml") {
      frontmatter = parseYaml(node.value);
      continue;
    }
    if (node.type === "heading") {
      const h = node as Heading;
      for (const d of [...open.keys()]) if (d >= h.depth) open.delete(d);
      const parent = open.get(Math.max(...[...open.keys()], 0));
      const key = slug(mdToString(h));
      // The heading is a slice like everything else, or `### \`build.ts\`` comes
      // back as `### build.ts`. Only `key` uses the flattened text, because a
      // slug wants it; anything reconstruction reads must be the slice.
      const first = h.children[0];
      const last = h.children[h.children.length - 1];
      const gap = gapAfter.get(node);
      const section: Section = {
        key,
        // Dotted address, so a query selects a section directly instead of
        // recursing: .sections[] | select(.path == "problem.symptom")
        path: parent ? `${parent.path}.${key}` : key,
        heading: first && last ? between(first, last) : "",
        depth: h.depth,
        ...(gap !== undefined && gap !== 1 ? { gap } : {}),
      };
      if (parent) {
        parent.sections = parent.sections ?? [];
        parent.sections.push(section);
      } else root.push(section);
      open.set(h.depth, section);
      continue;
    }
    push(node);
  }

  // A section holding exactly one paragraph collapses to a plain scalar - the
  // common case, and it keeps the YAML readable. Only when the block carries no
  // gap: collapsing to a bare string would throw the gap away, and a shortcut
  // that discards a field is indistinguishable from a bug.
  const collapse = (s: Section): void => {
    const c = s.content as Block[] | undefined;
    if (c?.length === 1 && c[0]?.type === "paragraph" && c[0]?.gap === undefined) s.content = c[0].md;
    s.sections?.forEach(collapse);
  };
  root.forEach(collapse);

  const last = tree.children[tree.children.length - 1];
  const trailing = last ? (source.slice(endOf(last)).match(/\n/g) ?? []).length : 0;

  // The symmetric case: blank lines before the first block, whether the file
  // opens with them or the frontmatter is followed by more than one.
  const yamlNode = tree.children.find((c) => c.type === "yaml");
  const firstNode = tree.children.find((c) => c.type !== "yaml");
  const leading = firstNode
    ? source.slice(yamlNode ? endOf(yamlNode) : 0, startOf(firstNode)).split("\n").length - (yamlNode ? 2 : 1)
    : 0;

  const pre =
    preamble.length === 0
      ? undefined
      : preamble.length === 1 && preamble[0]?.type === "paragraph"
        ? preamble[0].md
        : preamble;

  return { frontmatter, preamble: pre, sections: root, leading, trailing };
};

// ── YAML emission (hand-rolled, for block-scalar control) ─────────────────

export const scalar = (s: string, indent: number): string[] => {
  if (s.includes("\n")) {
    const pad = " ".repeat(indent + 2);
    // `|-` keeps every internal newline and drops the trailing one, which is
    // what makes a sentence-per-line prose convention survive the round trip.
    return ["|-", ...s.split("\n").map((l) => (l ? pad + l : ""))];
  }
  const first = s[0] ?? "";
  const needsQuote =
    s === "" ||
    ">|*&!%@`-?{}[],#'\" ".includes(first) ||
    ": ".includes(s[s.length - 1] ?? "") ||
    s.includes(": ") ||
    s.includes(" #") ||
    RESERVED.has(s.toLowerCase()) ||
    /^[-+]?[\d._eE:]+$/.test(s);
  return [needsQuote ? JSON.stringify(s) : s];
};

export const emitValue = (key: string, value: unknown, indent: number): string[] => {
  const pad = " ".repeat(indent);
  if (typeof value === "string") {
    const [head, ...rest] = scalar(value, indent);
    return [`${pad}${key}: ${head}`, ...rest];
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return [`${pad}${key}: []`];
    if (value.every((v) => v === null || typeof v === "string" || typeof v === "number")) {
      const items = value.map((v) => (v === null ? "null" : scalar(String(v), 0)[0]));
      return [`${pad}${key}: [${items.join(", ")}]`];
    }
    return [`${pad}${key}:`, ...value.flatMap((item) => emitItem(item as object, indent + 2))];
  }
  if (value && typeof value === "object") {
    return [`${pad}${key}:`, ...Object.entries(value).flatMap(([k, v]) => emitValue(k, v, indent + 2))];
  }
  return [`${pad}${key}: ${value === undefined ? "null" : String(value)}`];
};

export const emitItem = (obj: object, indent: number): string[] => {
  const lines = Object.entries(obj)
    .filter(([, v]) => v !== undefined)
    .flatMap(([k, v]) => emitValue(k, v, indent + 2));
  const head = lines[0];
  if (head === undefined) return [`${" ".repeat(indent)}- {}`];
  lines[0] = `${" ".repeat(indent)}- ${head.slice(indent + 2)}`;
  return lines;
};

export const toYaml = (doc: Indexed): string => {
  const lines: string[] = [
    "# Generated index. Every `md:` value is a byte-exact slice of the source",
    "# markdown, located by its mdast node's position offsets. Edit the markdown.",
  ];
  if (doc.frontmatter) lines.push(...emitValue("frontmatter", doc.frontmatter, 0));
  if (doc.preamble !== undefined) lines.push(...emitValue("preamble", doc.preamble, 0));
  if (doc.leading !== 1) lines.push(`leading: ${doc.leading}`);
  if (doc.trailing !== 1) lines.push(`trailing: ${doc.trailing}`);
  lines.push(...emitValue("sections", doc.sections, 0));
  return `${lines.join("\n")}\n`;
};

// ── Reconstruction (the proof the index is lossless) ──────────────────────

export const toMarkdown = (doc: Indexed, rawFrontmatter?: string): string => {
  const out: string[] = [];
  const blanks = (n: number): void => {
    for (let i = 0; i < n; i++) out.push("");
  };
  const emitBlocks = (blocks: Block[]): void => {
    for (const b of blocks) {
      out.push(b.md);
      blanks(typeof b.gap === "number" ? b.gap : 1);
    }
  };
  if (rawFrontmatter !== undefined) out.push("---", rawFrontmatter, "---");
  blanks(doc.leading ?? (rawFrontmatter !== undefined ? 1 : 0));
  if (typeof doc.preamble === "string") out.push(doc.preamble, "");
  else if (Array.isArray(doc.preamble)) emitBlocks(doc.preamble);
  const walk = (s: Section): void => {
    out.push(`${"#".repeat(s.depth)} ${s.heading}`);
    blanks(typeof s.gap === "number" ? s.gap : 1);
    if (typeof s.content === "string") out.push(s.content, "");
    else if (Array.isArray(s.content)) emitBlocks(s.content);
    s.sections?.forEach(walk);
  };
  doc.sections.forEach(walk);
  return out.join("\n").replace(/\n+$/, "") + "\n".repeat(doc.trailing ?? 1);
};

/** Returns null when the round trip is exact, else a short line-level report. */
export const roundTripReport = (source: string): string | null => {
  const doc = index(source);
  const raw = /^---\n([\s\S]*?)\n---\n/.exec(source);
  const rebuilt = toMarkdown(doc, raw ? raw[1] : undefined);
  if (rebuilt === source) return null;
  const a = source.split("\n");
  const b = rebuilt.split("\n");
  const lines: string[] = [];
  for (let i = 0; i < Math.max(a.length, b.length) && lines.length < 30; i++) {
    if (a[i] !== b[i])
      lines.push(`  line ${i + 1}\n    src: ${JSON.stringify(a[i])}\n    out: ${JSON.stringify(b[i])}`);
  }
  return lines.join("\n");
};

// ── CLI ───────────────────────────────────────────────────────────────────

/**
 * Returns the process exit code rather than calling `process.exit`, so the
 * failure paths are reachable from a test without killing the test runner.
 */
export const main = async (argv: string[] = Bun.argv.slice(2)): Promise<number> => {
  const { values, positionals } = parseArgs({
    args: argv,
    options: {
      check: { type: "boolean", default: false },
      json: { type: "boolean", default: false },
      out: { type: "string" },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help || positionals.length === 0) {
    console.log(
      [
        "Usage: md2yaml.ts <file.md> [--check | --json] [--out FILE]",
        "",
        "  --check   Reconstruct the markdown from the index and report any drift.",
        "            Exit 0 only when the round trip is byte-identical.",
        "  --json    Emit JSON instead of YAML, for jq. Adds a `file` key.",
        "  --out     Write to FILE instead of stdout.",
      ].join("\n"),
    );
    return values.help ? 0 : 2;
  }

  const file = positionals[0] as string;
  const source = await Bun.file(file).text();

  if (values.check) {
    const drift = roundTripReport(source);
    if (drift === null) {
      console.log(`round trip: byte-identical (${source.length} bytes)`);
      return 0;
    }
    console.error(`round trip: DIFFERS\n${drift}`);
    return 1;
  }

  const doc = index(source);
  const text = values.json ? `${JSON.stringify({ file, ...doc })}\n` : toYaml(doc);
  if (values.out) await Bun.write(values.out, text);
  else process.stdout.write(text);
  return 0;
};

if (import.meta.main) {
  main()
    .then((code) => process.exit(code))
    .catch((err: unknown) => {
      console.error(`error: ${err instanceof Error ? err.message : String(err)}`);
      process.exit(1);
    });
}
