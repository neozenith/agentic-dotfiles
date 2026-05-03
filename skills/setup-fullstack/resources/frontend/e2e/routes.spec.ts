import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { type Page, type Request as PWRequest, expect, test } from "@playwright/test";
import { MATRIX } from "./matrix.ts";

/**
 * Generated route smoke tests:
 *   1. Navigate to the section path
 *   2. Wait for React mount + network to settle
 *   3. Assert zero (filtered) browser console errors
 *   4. Take a full-page screenshot
 *   5. Write paired .log + .network.json artifacts keyed by the slug
 *
 * Three artifacts per slug:
 *   test-results/matrix/<slug>.png            — full-page screenshot
 *   test-results/matrix/<slug>.log            — console + page errors
 *   test-results/matrix/<slug>.network.json   — request timings
 */

const ARTIFACTS = path.resolve(process.cwd(), "test-results/matrix");
mkdirSync(ARTIFACTS, { recursive: true });

const ALLOWED_CONSOLE: RegExp[] = [
  /\[vite\]/i,
  /Download the React DevTools/i,
  /favicon/i,
  /act\(/,
];

interface NetworkTiming {
  url: string;
  method: string;
  status: number | null;
  start_offset_ms: number;
  duration_ms: number;
  resource_type: string;
}

interface TestCollector {
  writeArtifacts: (slug: string) => void;
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
    const text = msg.text();
    lines.push(`[${level}] ${text}`);
    if (msg.type() === "error" && !ALLOWED_CONSOLE.some((re) => re.test(text))) {
      errors.push(text);
    }
  });

  const network: NetworkTiming[] = [];
  const pending = new Map<PWRequest, number>();

  page.on("request", (req) => { pending.set(req, Date.now()); });
  page.on("requestfinished", async (req) => {
    const start = pending.get(req);
    if (start === undefined) return;
    pending.delete(req);
    const res = await req.response();
    const status = res ? res.status() : null;
    network.push({
      url: req.url(),
      method: req.method(),
      status,
      start_offset_ms: start - testStart,
      duration_ms: Date.now() - start,
      resource_type: req.resourceType(),
    });
    // 503s for optional data are tolerated.
    if (status !== null && status >= 500 && status !== 503) {
      errors.push(`HTTP ${status} ${req.url()}`);
    }
  });
  page.on("requestfailed", (req) => {
    const start = pending.get(req);
    if (start === undefined) return;
    pending.delete(req);
    network.push({
      url: req.url(),
      method: req.method(),
      status: null,
      start_offset_ms: start - testStart,
      duration_ms: Date.now() - start,
      resource_type: req.resourceType(),
    });
  });

  return {
    writeArtifacts(slug: string): void {
      writeFileSync(path.join(ARTIFACTS, `${slug}.log`), `${lines.join("\n")}\n`, "utf-8");
      const wallClockEnd = network.reduce(
        (m, n) => Math.max(m, n.start_offset_ms + n.duration_ms),
        0,
      );
      const summary = {
        test_start_ms: testStart,
        wall_clock_duration_ms: wallClockEnd,
        total_requests: network.length,
        total_duration_ms: network.reduce((s, n) => s + n.duration_ms, 0),
        all_requests: [...network].sort((a, b) => a.start_offset_ms - b.start_offset_ms),
      };
      writeFileSync(
        path.join(ARTIFACTS, `${slug}.network.json`),
        `${JSON.stringify(summary, null, 2)}\n`,
        "utf-8",
      );
    },
    assertNoErrors(): void {
      expect(errors, `Browser errors:\n${errors.join("\n")}`).toHaveLength(0);
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

for (const entry of MATRIX) {
  test.describe(`${entry.section.name} / ${entry.variant.name}`, () => {
    test(`${entry.slug}: ${entry.section.path}`, async ({ page }) => {
      const io = collectTestIO(page);
      await page.goto(entry.section.path);
      await waitForPageLoad(page);
      await page.screenshot({
        path: path.join(ARTIFACTS, `${entry.slug}.png`),
        fullPage: true,
      });
      io.writeArtifacts(entry.slug);
      io.assertNoErrors();
    });
  });
}
