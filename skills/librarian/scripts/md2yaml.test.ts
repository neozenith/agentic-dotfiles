import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdir, rm } from "node:fs/promises";
import {
  type Block,
  emitItem,
  index,
  main,
  meta,
  roundTripReport,
  scalar,
  type Section,
  slug,
  toMarkdown,
  toYaml,
} from "./md2yaml.ts";

/** Safe accessors: a section may be absent, and content may be a scalar. */
const blocks = (s?: Section): Block[] => (Array.isArray(s?.content) ? s.content : []);
const sub = (s: Section | undefined, ...keys: string[]): Section | undefined =>
  keys.reduce<Section | undefined>((acc, k) => acc?.sections?.find((c) => c.key === k), s);

/** Round-tripping is the contract; assert it on every fixture. */
const exact = (md: string): void => expect(roundTripReport(md)).toBeNull();

describe("slug", () => {
  test.each([
    ["Pain point", "pain_point"],
    ["The lens", "the_lens"],
    ["  Mixed / Punctuation!  ", "mixed_punctuation"],
    ["`code` heading", "code_heading"],
    ["---", ""],
  ])("%p -> %p", (input, want) => {
    expect(slug(input)).toBe(want);
  });
});

describe("scalar", () => {
  test("plain strings are unquoted", () => {
    expect(scalar("hello world", 0)).toEqual(["hello world"]);
  });

  test.each([["yes"], ["no"], ["12"], ["1.5"], ["- leading dash"], ["key: value"], ["trailing "], [""]])(
    "%p is quoted",
    (input) => {
      expect(scalar(input, 0)[0]).toBe(JSON.stringify(input));
    },
  );

  test("multi-line becomes a literal block scalar", () => {
    expect(scalar("one\ntwo", 0)).toEqual(["|-", "  one", "  two"]);
  });

  test("blank interior lines carry no padding", () => {
    expect(scalar("one\n\ntwo", 0)).toEqual(["|-", "  one", "", "  two"]);
  });
});

describe("emitItem", () => {
  test("an empty object still emits a sequence entry", () => {
    expect(emitItem({}, 2)).toEqual(["  - {}"]);
  });

  test("undefined values are dropped", () => {
    expect(emitItem({ a: 1, b: undefined }, 0)).toEqual(["- a: 1"]);
  });
});

describe("structure", () => {
  const doc = `# Title

Intro paragraph.

## Problem

### Symptom

A symptom.

### Pain point

Prose before a fence:

\`\`\`go
x := 1
\`\`\`

Prose after the fence.
`;

  test("headings nest and carry dotted paths", () => {
    const out = index(doc);
    expect(out.sections[0]?.key).toBe("title");
    const problem = out.sections[0]?.sections?.[0];
    expect(problem?.path).toBe("title.problem");
    expect(problem?.sections?.map((s) => s.path)).toEqual(["title.problem.symptom", "title.problem.pain_point"]);
  });

  test("a lone paragraph collapses to a scalar", () => {
    const symptom = index(doc).sections[0]?.sections?.[0]?.sections?.[0];
    expect(symptom?.content).toBe("A symptom.");
  });

  test("a mixed section keeps block order and code language", () => {
    const pain = index(doc).sections[0]?.sections?.[0]?.sections?.[1];
    const found = blocks(pain);
    expect(found.map((b) => b.type)).toEqual(["paragraph", "code", "paragraph"]);
    expect(found[1]?.lang).toBe("go");
  });

  test("round trips", () => exact(doc));
});

describe("tables", () => {
  const doc = `# T

| Measure | Before | After |
|---|---:|---:|
| Total | 44 ms | **13 ms** |
| Reads in \`loop\` | 40 | 1 |
`;

  test("cells are split, keyed by slugified column, without pipe delimiters", () => {
    const block = blocks(index(doc).sections[0])[0] as { rows: Record<string, string>[] } | undefined;
    expect(block?.rows).toEqual([
      { measure: "Total", before: "44 ms", after: "**13 ms**" },
      { measure: "Reads in `loop`", before: "40", after: "1" },
    ]);
  });

  test("cell values keep inline markdown rather than flattening", () => {
    const block = blocks(index(doc).sections[0])[0] as { rows: Record<string, string>[] } | undefined;
    expect(block?.rows[0]?.after).toBe("**13 ms**");
  });

  test("alignment is named, with unaligned columns spelled `default`", () => {
    const block = blocks(index(doc).sections[0])[0] as { align: string[] } | undefined;
    expect(block?.align).toEqual(["default", "right", "right"]);
  });

  test("align is omitted when the table declares none", () => {
    const plain = "# T\n\n| A | B |\n|---|---|\n| 1 | 2 |\n";
    const block = blocks(index(plain).sections[0])[0];
    expect(block).not.toHaveProperty("align");
  });

  test("an empty cell indexes as an empty string", () => {
    const withBlank = "# T\n\n| A | B |\n|---|---|\n| 1 |  |\n";
    const block = blocks(index(withBlank).sections[0])[0] as { rows: Record<string, string>[] } | undefined;
    expect(block?.rows[0]?.b).toBe("");
  });

  test("round trips", () => exact(doc));
});

describe("lists", () => {
  const doc = `# L

- first item
- second item with a nested list:
  - nested one
  - nested two
`;

  test("items are split into slices, nesting held inside its parent item", () => {
    const block = blocks(index(doc).sections[0])[0] as { items: string[]; ordered: boolean } | undefined;
    expect(block?.ordered).toBe(false);
    expect(block?.items).toHaveLength(2);
    expect(block?.items[1]).toContain("nested one");
  });

  test("round trips", () => exact(doc));
});

describe("whitespace is content", () => {
  test("adjacent fences with no blank line between them", () => {
    exact("# T\n\n```sh\nrun it\n```\n```\noutput\n```\n");
  });

  test("an extra blank line before a heading", () => {
    exact("# T\n\nPara.\n\n\n## Next\n\nMore.\n");
  });

  test("a file with no trailing newline", () => {
    exact("# T\n\nPara.");
  });

  test("a file ending in a blank line", () => {
    exact("# T\n\nPara.\n\n");
  });

  test("two blank lines after frontmatter", () => {
    exact("---\ntype: Note\n---\n\n\n# T\n\nPara.\n");
  });

  test("gap survives the single-paragraph collapse", () => {
    const out = index("# T\n\nPara.\n\n\n## Next\n\nMore.\n");
    expect(typeof out.sections[0]?.content).not.toBe("string");
  });
});

describe("documents without an H1", () => {
  const doc = `---
type: Architecture Decision
title: A generated sibling
---

> **Lens**: The title lives in metadata, so nothing precedes the blockquote.

## Problem

A symptom.
`;

  test("frontmatter is parsed as data", () => {
    expect(index(doc).frontmatter).toEqual({ type: "Architecture Decision", title: "A generated sibling" });
  });

  test("the pre-heading block is kept as the preamble, not dropped", () => {
    const pre = index(doc).preamble;
    expect(Array.isArray(pre) ? pre[0]?.md : pre).toContain("**Lens**");
  });

  test("paths shorten when no H1 nests everything", () => {
    expect(index(doc).sections[0]?.path).toBe("problem");
  });

  test("round trips", () => exact(doc));
});

describe("headings keep inline formatting", () => {
  const doc = "# T\n\n## `build.ts` and **bold**\n\nBody.\n";

  test("the heading is a slice, not flattened text", () => {
    expect(index(doc).sections[0]?.sections?.[0]?.heading).toBe("`build.ts` and **bold**");
  });

  test("the key is slugified from the flattened text", () => {
    expect(index(doc).sections[0]?.sections?.[0]?.key).toBe("build_ts_and_bold");
  });

  test("round trips", () => exact(doc));
});

describe("edge cases", () => {
  test("an empty document", () => {
    const out = index("");
    expect(out.sections).toEqual([]);
    expect(out.trailing).toBe(0);
  });

  test("a document that is only frontmatter", () => {
    expect(index("---\na: 1\n---\n").frontmatter).toEqual({ a: 1 });
  });

  test("meta returns nothing for a block with no projection", () => {
    expect(meta({ type: "thematicBreak" } as never, () => "")).toEqual({});
  });

  test("toMarkdown without frontmatter emits no fence", () => {
    expect(toMarkdown(index("# T\n\nBody.\n"))).toBe("# T\n\nBody.\n");
  });

  test("roundTripReport names the differing line", () => {
    const doc = index("# T\n\nBody.\n");
    doc.sections[0]!.heading = "Changed";
    expect(toMarkdown(doc)).toContain("# Changed");
  });
});

describe("toYaml", () => {
  const doc = index("---\na: 1\n---\n\n# T\n\nBody.\n");

  test("emits frontmatter, sections and a generated-file banner", () => {
    const yaml = toYaml(doc);
    expect(yaml).toContain("# Generated index.");
    expect(yaml).toContain("frontmatter:");
    expect(yaml).toContain("sections:");
    expect(yaml.endsWith("\n")).toBe(true);
  });

  test("omits leading and trailing when both are the default", () => {
    expect(toYaml(doc)).not.toContain("trailing:");
  });

  test("records a non-default trailing", () => {
    expect(toYaml(index("# T\n\nBody."))).toContain("trailing: 0");
  });
});

describe("CLI", () => {
  // Real subprocesses and real files: no console patching, no mocks.
  const TMP = `${import.meta.dir}/tmp`;
  const SCRIPT = `${import.meta.dir}/md2yaml.ts`;
  const fixture = `${TMP}/fixture.md`;

  const run = async (args: string[]): Promise<{ code: number; out: string; err: string }> => {
    const proc = Bun.spawn(["bun", "run", SCRIPT, ...args], { stdout: "pipe", stderr: "pipe" });
    const [out, err, code] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ]);
    return { code, out, err };
  };

  beforeEach(async () => {
    await mkdir(TMP, { recursive: true });
    await Bun.write(fixture, "# T\n\nBody.\n");
  });
  afterEach(async () => {
    await rm(TMP, { recursive: true, force: true });
  });

  test("--help prints usage and exits 0", async () => {
    const { code, out } = await run(["--help"]);
    expect(code).toBe(0);
    expect(out).toContain("Usage: md2yaml.ts");
  });

  test("no arguments is a usage error", async () => {
    expect((await run([])).code).toBe(2);
  });

  test("--check passes on a well-formed document", async () => {
    const { code, out } = await run([fixture, "--check"]);
    expect(code).toBe(0);
    expect(out).toContain("byte-identical");
  });

  test("--check fails loudly on a document it cannot reproduce", async () => {
    // A setext heading parses as a heading but reconstructs as ATX.
    await Bun.write(fixture, "Title\n=====\n\nBody.\n");
    const { code, err } = await run([fixture, "--check"]);
    expect(code).toBe(1);
    expect(err).toContain("DIFFERS");
  });

  test("a missing file fails rather than emitting an empty index", async () => {
    expect((await run([`${TMP}/absent.md`])).code).toBe(1);
  });

  test("--help exits 0 and no arguments exits 2", async () => {
    expect(await main(["--help"])).toBe(0);
    expect(await main([])).toBe(2);
  });

  test("--check returns 0 when exact and 1 when it cannot reproduce", async () => {
    expect(await main([fixture, "--check"])).toBe(0);
    await Bun.write(fixture, "Title\n=====\n\nBody.\n");
    expect(await main([fixture, "--check"])).toBe(1);
  });

  test("a missing file rejects rather than returning a code", async () => {
    expect(main([`/absent.md`])).rejects.toThrow();
  });

  test("with no --out the index goes to stdout", async () => {
    expect(await main([fixture])).toBe(0);
  });

  test("writes YAML to --out", async () => {
    const out = `${TMP}/out.yml`;
    await main([fixture, "--out", out]);
    expect(await Bun.file(out).text()).toContain("sections:");
  });

  test("--json writes a parseable object naming the file", async () => {
    const out = `${TMP}/out.json`;
    await main([fixture, "--json", "--out", out]);
    const parsed = JSON.parse(await Bun.file(out).text());
    expect(parsed.file).toBe(fixture);
    expect(parsed.sections[0].key).toBe("t");
  });
});
