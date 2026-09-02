// Tests for render_mermaid.sh — the render failure-triage surface.
//
// render_mermaid.sh is Bash, so it is tested by driving its CLI rather than by
// importing it. What matters here is the part that rots silently: the mapping
// from a real stderr signature to a failure class. Every fixture below is a
// verbatim fragment of output observed from npm, Puppeteer, Chromium, or
// Mermaid — if a tool changes its wording, these tests are where it surfaces.
//
// The render path itself is deliberately NOT exercised: it needs a browser, and
// a test that silently skips when one is missing is worse than no test.

import { describe, expect, test } from "bun:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SCRIPT = join(SCRIPT_DIR, "render_mermaid.sh");

const classify = async (stderr: string): Promise<string> => {
  const proc = Bun.spawn(["bash", SCRIPT, "--classify"], { stdin: "pipe", stdout: "pipe", stderr: "pipe" });
  proc.stdin.write(stderr);
  await proc.stdin.end();
  return (await new Response(proc.stdout).text()).trim();
};

const run = async (args: string[]): Promise<{ code: number; stdout: string; stderr: string }> => {
  const proc = Bun.spawn(["bash", SCRIPT, ...args], { stdout: "pipe", stderr: "pipe" });
  const [stdout, stderr] = await Promise.all([new Response(proc.stdout).text(), new Response(proc.stderr).text()]);
  return { code: await proc.exited, stdout, stderr };
};

// ─── Classification ──────────────────────────────────────────────────────────

describe("classify — package cache", () => {
  test("npm EPERM on the shared cache is a cache problem, not a browser one", async () => {
    const stderr = "npm ERR! code EPERM\nnpm ERR! syscall open\nnpm ERR! path /Users/x/.npm/_cacache/index-v5/aa";
    expect(await classify(stderr)).toBe("NPM_CACHE_PERMISSION");
  });

  test("EACCES is the same class", async () => {
    expect(await classify("npm ERR! Error: EACCES: permission denied, mkdir '/Users/x/.npm'")).toBe(
      "NPM_CACHE_PERMISSION",
    );
  });
});

describe("classify — browser discovery", () => {
  test("Puppeteer's missing-Chrome message", async () => {
    const stderr = "Error: Could not find Chrome (ver. 131.0.6778.204). This can occur if either\n";
    expect(await classify(stderr)).toBe("BROWSER_MISSING");
  });

  test("a missing chrome-headless-shell is browser discovery, not a sandbox denial", async () => {
    const stderr = "The browser chrome-headless-shell is not found at /Users/x/.cache/puppeteer";
    expect(await classify(stderr)).toBe("BROWSER_MISSING");
  });
});

describe("classify — execution class", () => {
  test("macOS port-registration denial is a sandbox problem", async () => {
    const stderr = [
      "[0820/101500.123456:ERROR:mach_port_rendezvous.cc(392)] MachPortRendezvousServer",
      "bootstrap_check_in org.chromium.MachPortRendezvousServer: Permission denied (1100)",
    ].join("\n");
    expect(await classify(stderr)).toBe("SANDBOX_DENIED");
  });

  test("Puppeteer's generic launch-failure wrapper does not demote a sandbox denial to BROWSER_MISSING", async () => {
    // Real stderr: Puppeteer prints its own wrapper line first, then Chromium's reason.
    // Classifying this as BROWSER_MISSING would trigger the one remedy the doc forbids here: a retry.
    const stderr = [
      "Error: Failed to launch the browser process!",
      "[0820/101500.123456:ERROR:mach_port_rendezvous.cc(392)] MachPortRendezvousServer",
      "bootstrap_check_in org.chromium.MachPortRendezvousServer: Permission denied (1100)",
    ].join("\n");
    expect(await classify(stderr)).toBe("SANDBOX_DENIED");
  });
});

describe("classify — network", () => {
  test("an unreachable registry is its own class", async () => {
    expect(await classify("npm ERR! getaddrinfo ENOTFOUND registry.npmjs.org")).toBe("NETWORK_UNREACHABLE");
  });
});

describe("classify — diagram source", () => {
  test("a Mermaid parse error is the ONLY class that means 'edit the diagram'", async () => {
    const stderr = "Error: Parse error on line 4:\n...    A[Start --> B\n---------------^\nExpecting 'SQE'";
    expect(await classify(stderr)).toBe("DIAGRAM_SYNTAX");
  });

  test("an unknown diagram type is also diagram source", async () => {
    expect(await classify("UnknownDiagramError: No diagram type detected matching given configuration")).toBe(
      "DIAGRAM_SYNTAX",
    );
  });
});

describe("classify — precedence and fallback", () => {
  test("an earlier-failing input wins: a cache error that also mentions Chrome is still a cache error", async () => {
    const stderr = "npm ERR! code EPERM while installing puppeteer\nCould not find Chrome";
    expect(await classify(stderr)).toBe("NPM_CACHE_PERMISSION");
  });

  test("unrecognised output is UNKNOWN — never silently blamed on the diagram", async () => {
    expect(await classify("something nobody has seen before")).toBe("UNKNOWN");
  });
});

// ─── CLI surfaces ────────────────────────────────────────────────────────────

describe("--doctor", () => {
  test("reports the cache, a browser verdict, a tier, and where to read the triage", async () => {
    const { code, stdout } = await run(["--doctor"]);
    expect(code).toBe(0);
    expect(stdout).toContain("npm_cache:");
    expect(stdout).toContain("browser:");
    expect(stdout).toMatch(/^tier: [AB]/m);
    expect(stdout).toContain("render_troubleshooting.md");
  });
});

describe("--verify", () => {
  test("a non-PNG fails the artifact check — exit 0 from a renderer proves nothing", async () => {
    const { code, stderr } = await run(["--verify", SCRIPT]);
    expect(code).toBe(1);
    expect(stderr).toContain("BAD:");
  });

  test("a real PNG with non-zero dimensions passes", async () => {
    const png = join(SCRIPT_DIR, "..", "resources", "examples", "layout_dagre_classic.png");
    const { code, stdout } = await run(["--verify", png]);
    expect(code).toBe(0);
    expect(stdout).toContain("ok:");
  });
});

describe("no arguments", () => {
  test("prints usage and exits non-zero", async () => {
    const { code, stderr } = await run([]);
    expect(code).toBe(1);
    expect(stderr).toContain("Usage:");
  });
});
