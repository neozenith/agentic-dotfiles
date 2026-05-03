import { mkdirSync, writeFileSync } from "node:fs";
import { type Page, expect, test } from "@playwright/test";
import type { Request as PlaywrightRequest } from "@playwright/test";

/**
 * Universal Routes E2E Test Suite
 *
 * Site-map smoke test: every route declared in SECTIONS gets a generated
 * permutation test that:
 *   1. Navigates to the path
 *   2. Waits for React to mount + the network to settle
 *   3. Asserts zero browser console errors
 *   4. Takes a full-page screenshot
 *   5. Writes paired .log + .network.json artifacts keyed by the slug
 *
 * Slug format:
 *   E{id}_{ENGINE}-S{id}_{SECTION}.png
 *
 * To add a route to the smoke suite: append an entry to SECTIONS. Done.
 * To grow new axes (time ranges, viewport sizes, locales) when the app
 * gains filters, copy the ENGINES/SECTIONS shape and weave them into the
 * permutation loop at the bottom of this file.
 */

const ENGINES = { default: { id: 1, name: "default" } } as const;
type EngineKey = keyof typeof ENGINES;
type Engine = (typeof ENGINES)[EngineKey];

const getEngine = (): Engine => {
  const projectName = test.info().project.name as EngineKey;
  return ENGINES[projectName] ?? ENGINES.default;
};

const SECTIONS = [
  { id: 0, slug: "home", name: "Home", path: "/" },
] as const;
type Section = (typeof SECTIONS)[number];

interface CoverageEntry { section: Section }
const COVERAGE_MATRIX: CoverageEntry[] = SECTIONS.map((section) => ({ section }));

const pad = (n: number): string => String(n).padStart(2, "0");
const screenshotSlug = (engine: Engine, section: Section): string =>
  `E${pad(engine.id)}_${engine.name.toUpperCase()}-S${pad(section.id)}_${section.slug.toUpperCase()}`;

interface NetworkTiming {
  url: string;
  method: string;
  status: number | null;
  start_offset_ms: number;
  duration_ms: number;
  resource_type: string;
}

interface TestCollector {
  writeLog: (slug: string) => void;
  assertNoErrors: () => void;
}

const collectTestIO = (page: Page): TestCollector => {
  const testStart = Date.now();
  const lines: string[] = [];
  const errors: string[] = [];

  page.on("pageerror", (err) => {
    lines.push(`[PAGE_ERROR] ${err.message}`);
    errors.push(err.message);
  });
  page.on("console", (msg) => {
    const level = msg.type().toUpperCase().padEnd(7);
    lines.push(`[${level}] ${msg.text()}`);
    if (msg.type() === "error") errors.push(msg.text());
  });

  const network: NetworkTiming[] = [];
  const pending = new Map<PlaywrightRequest, number>();

  page.on("request", (req) => { pending.set(req, Date.now()); });
  page.on("requestfinished", async (req) => {
    const start = pending.get(req);
    if (start === undefined) return;
    pending.delete(req);
    const res = await req.response();
    network.push({
      url: req.url(), method: req.method(),
      status: res ? res.status() : null,
      start_offset_ms: start - testStart,
      duration_ms: Date.now() - start,
      resource_type: req.resourceType(),
    });
  });
  page.on("requestfailed", (req) => {
    const start = pending.get(req);
    if (start === undefined) return;
    pending.delete(req);
    network.push({
      url: req.url(), method: req.method(), status: null,
      start_offset_ms: start - testStart,
      duration_ms: Date.now() - start,
      resource_type: req.resourceType(),
    });
  });

  return {
    writeLog(slug: string): void {
      const dir = "e2e-screenshots";
      mkdirSync(dir, { recursive: true });
      writeFileSync(`${dir}/${slug}.log`, `${lines.join("\n")}\n`, "utf-8");
      const wallClockEnd = network.reduce(
        (max, n) => Math.max(max, n.start_offset_ms + n.duration_ms), 0,
      );
      const summary = {
        test_start_ms: testStart,
        wall_clock_duration_ms: wallClockEnd,
        total_requests: network.length,
        total_duration_ms: network.reduce((s, n) => s + n.duration_ms, 0),
        all_requests: [...network].sort((a, b) => a.start_offset_ms - b.start_offset_ms),
      };
      writeFileSync(`${dir}/${slug}.network.json`,
        `${JSON.stringify(summary, null, 2)}\n`, "utf-8");
    },
    assertNoErrors(): void {
      const real = errors.filter((e) =>
        !e.includes("act(") && !e.includes("favicon") && !e.includes("[vite]"));
      expect(real, `Browser console errors:\n${real.join("\n")}`).toHaveLength(0);
    },
  };
};

const waitForPageLoad = async (page: Page): Promise<void> => {
  await page.waitForFunction(
    () => (document.getElementById("root")?.children.length ?? 0) > 0,
    { timeout: 15_000 },
  );
  await page.waitForLoadState("networkidle", { timeout: 3_000 }).catch(() => {});
};

for (const entry of COVERAGE_MATRIX) {
  test.describe(`${entry.section.name} route`, () => {
    const testLabel = `S${pad(entry.section.id)}_${entry.section.slug}: ${entry.section.path}`;
    test(testLabel, async ({ page }) => {
      const engine = getEngine();
      const slug = screenshotSlug(engine, entry.section);
      const io = collectTestIO(page);
      await page.goto(entry.section.path);
      await waitForPageLoad(page);
      await page.screenshot({ path: `e2e-screenshots/${slug}.png`, fullPage: true });
      io.writeLog(slug);
      io.assertNoErrors();
    });
  });
}
