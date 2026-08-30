import { describe, expect, test } from "bun:test";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { checkMarkdown, fixMarkdown, main } from "./prose_gates.ts";

const rules = (src: string, maxWords?: number) => checkMarkdown(src, "doc.md", maxWords).map((f) => f.rule);

describe("PG001 mid-sentence line wrap", () => {
  test("flags a sentence wrapped across lines", () => {
    expect(rules("This sentence continues on\nthe next line for no reason.\n")).toContain("PG001");
  });

  test("accepts one sentence per line", () => {
    expect(rules("First sentence here.\nSecond sentence follows.\n")).toHaveLength(0);
  });

  test("ignores wraps inside fenced code blocks", () => {
    expect(rules("```text\nnot a sentence just\nwrapped code\n```\n")).toHaveLength(0);
  });

  test("reports the wrapped line number", () => {
    const findings = checkMarkdown("# Title\n\nGood line here.\nBad wrap starts\nhere.\n", "doc.md");
    expect(findings).toHaveLength(1);
    expect(findings[0]?.line).toBe(4);
  });
});

describe("PG002 sentence word budget", () => {
  test("flags a sentence over 25 words", () => {
    const long = `${Array.from({ length: 30 }, (_, i) => `word${i}`).join(" ")}.`;
    expect(rules(`${long}\n`)).toContain("PG002");
  });

  test("respects a custom budget", () => {
    expect(rules("One two three four five six seven eight.\n", 5)).toContain("PG002");
  });

  test("counts inline code as one word", () => {
    const words = Array.from({ length: 20 }, (_, i) => `w${i}`).join(" ");
    const found = rules(`${words} \`a very long inline code span with many words inside it\`.\n`);
    expect(found.filter((r) => r === "PG002")).toHaveLength(0);
  });
});

describe("PG003 semicolon lists", () => {
  test("flags two or more semicolons in one sentence", () => {
    expect(rules("We ship parsing; then linting; then fixing.\n")).toContain("PG003");
  });

  test("allows a single joining semicolon", () => {
    expect(rules("The cache is warm; queries are fast.\n").filter((r) => r === "PG003")).toHaveLength(0);
  });
});

describe("PG004/PG005 glyph tells", () => {
  test("flags em-dash and interpunct in prose but not in code", () => {
    const found = rules("A tell — right here.\n\nAlso a · dot.\n\n```\ncode — with · glyphs\n```\n");
    expect(found).toContain("PG004");
    expect(found).toContain("PG005");
    expect(found).toHaveLength(2);
  });
});

describe("PG006 interpunct-joined inline list", () => {
  test("flags a separator run as one disguised list, not per-glyph PG005 spam", () => {
    const found = rules("[a](https://a) · [b](https://b) · [c](https://c) · plain d\n");
    expect(found).toEqual(["PG006"]);
  });

  test("counts the items in the message", () => {
    const findings = checkMarkdown("one · two · three · four\n", "doc.md");
    expect(findings[0]?.message).toContain("4 items");
  });

  test("a single stray interpunct stays PG005", () => {
    expect(rules("A stray · here.\n")).toEqual(["PG005"]);
  });
});

describe("PG007 inline enumeration", () => {
  test("flags (a)/(b) enumerators inlined in one paragraph", () => {
    const src = "Two duties: (a) *name things* using canonical terms; (b) *keep it current* in the same change.\n";
    expect(rules(src)).toContain("PG007");
  });

  test("flags numeric (1)/(2) families", () => {
    expect(rules("Steps: (1) parse the file and (2) emit findings.\n")).toContain("PG007");
  });

  test("a lone (a) back-reference does not fire", () => {
    expect(rules("See item (a) above.\n").filter((r) => r === "PG007")).toHaveLength(0);
  });

  test("enumerators inside code are exempt", () => {
    expect(rules("Run `f((a), (b))` here.\n").filter((r) => r === "PG007")).toHaveLength(0);
  });
});

describe("PG008 comma-joined labelled run", () => {
  test("flags a sentence of 3+ comma-joined labelled items", () => {
    const src = "Rules: PG001 mid-sentence wrap, PG002 word budget, PG003 semicolon list, PG004 em-dash tell.\n";
    expect(rules(src)).toContain("PG008");
  });

  test("counts inline-code labels too", () => {
    expect(rules("Targets: `fmt` formats, `vet` inspects, `race` detects data races.\n")).toContain("PG008");
  });

  test("plain comma prose without labels does not fire", () => {
    expect(rules("We need eggs, milk, butter, and flour today.\n")).toHaveLength(0);
  });

  test("two labelled segments stay under the threshold", () => {
    expect(rules("Use PG001 for wraps, PG002 for budgets.\n").filter((r) => r === "PG008")).toHaveLength(0);
  });

  test("a bare-label subject enumeration does not fire", () => {
    const src = "The files `README.md`, `AGENTS.md`, and `CLAUDE.md` serve one role together.\n";
    expect(rules(src).filter((r) => r === "PG008")).toHaveLength(0);
  });
});

describe("PG009 stacked interpunct runs", () => {
  test("runs stacked across lines replace PG006 and ask for a nested list", () => {
    const src =
      "Group A: [a](https://a) · [b](https://b) · [c](https://c).\nGroup B: [d](https://d) · [e](https://e) · [f](https://f).\n";
    const findings = checkMarkdown(src, "doc.md");
    expect(findings.map((f) => f.rule)).toEqual(["PG009"]);
    expect(findings[0]?.message).toContain("nested list");
  });

  test("a single-line run stays PG006", () => {
    expect(rules("[a](https://a) · [b](https://b) · [c](https://c)\n")).toEqual(["PG006"]);
  });
});

describe("embedded markdown fences", () => {
  test("audits a ```markdown fence body and maps the finding to the file line", () => {
    const src = "Intro sentence.\n\n```markdown\nA wrapped sentence goes\nonward here.\n```\n";
    const findings = checkMarkdown(src, "doc.md");
    expect(findings).toHaveLength(1);
    expect(findings[0]?.rule).toBe("PG001");
    expect(findings[0]?.line).toBe(4);
  });

  test("other fence languages stay exempt", () => {
    expect(rules("```text\nA wrapped sentence goes\nonward here.\n```\n")).toHaveLength(0);
  });

  test("code fences nested inside the template stay exempt", () => {
    const src = "````markdown\nClean sentence.\n\n```sh\nwrapped code stays\nexempt here\n```\n````\n";
    expect(rules(src)).toHaveLength(0);
  });

  test("--fix never rewrites through a fence boundary", () => {
    const src = "```markdown\nA wrapped sentence goes\nonward here.\n```\n";
    expect(fixMarkdown(src)).toBe(src);
  });
});

describe("fixMarkdown sentence-per-line reflow", () => {
  test("reflows a wrapped paragraph and passes the gate afterwards", () => {
    const fixed = fixMarkdown("First sentence wraps over\nthis line. Second sentence also\nwraps badly here.\n");
    expect(fixed).toBe("First sentence wraps over this line.\nSecond sentence also wraps badly here.\n");
    expect(checkMarkdown(fixed, "doc.md")).toHaveLength(0);
  });

  test("is idempotent", () => {
    const content = "One clean sentence.\nAnother clean sentence.\n";
    expect(fixMarkdown(content)).toBe(content);
  });

  test("splits a single line holding two sentences", () => {
    expect(fixMarkdown("Run `tool.exe now` then check. Done here.\n")).toBe(
      "Run `tool.exe now` then check.\nDone here.\n",
    );
  });

  test("keeps list-item indentation", () => {
    expect(fixMarkdown("- A list item sentence that wraps\n  onto a second line. And more.\n")).toBe(
      "- A list item sentence that wraps onto a second line.\n  And more.\n",
    );
  });

  test("leaves blockquotes alone", () => {
    const content = "> Quoted text that wraps\n> mid-sentence stays put.\n";
    expect(fixMarkdown(content)).toBe(content);
  });
});

describe("main CLI", () => {
  const tempFile = (content: string): string => {
    const dir = mkdtempSync(join(tmpdir(), "prose-gates-"));
    const file = join(dir, "doc.md");
    writeFileSync(file, content);
    return file;
  };

  test("exits 0 on a clean file and 1 on findings", async () => {
    expect(await main([tempFile("One clean sentence.\n")])).toBe(0);
    expect(await main([tempFile("A wrapped sentence goes\nonward here.\n")])).toBe(1);
  });

  test("--fix rewrites the file in place", async () => {
    const file = tempFile("A wrapped sentence goes\nonward here.\n");
    expect(await main([file, "--fix"])).toBe(0);
    expect(readFileSync(file, "utf8")).toBe("A wrapped sentence goes onward here.\n");
  });

  test("--json emits parseable findings", async () => {
    const file = tempFile("A tell — here.\n");
    expect(await main([file, "--json"])).toBe(1);
  });

  test("usage errors exit 2", async () => {
    expect(await main([])).toBe(2);
    expect(await main(["--nope"])).toBe(2);
    expect(await main([tempFile("x.\n"), "--max-words", "zero"])).toBe(2);
  });

  test("--help exits 0", async () => {
    expect(await main(["--help"])).toBe(0);
  });
});
