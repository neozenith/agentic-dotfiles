// Shell-runner with heartbeat + loud-on-failure semantics.
//
// `runQuiet(label, $`cmd`)` suppresses the underlying command's stdout/stderr
// on success (so the user sees one tidy success line per step), but emits a
// 5-second heartbeat showing the step is still working. On failure, the full
// captured output is dumped to stderr and the error re-thrown so the script
// exits non-zero.
//
// IMPORTANT: this helper is for non-interactive commands. Anything that may
// prompt for input on a TTY (e.g. `bun create vite@latest`, `shadcn init`)
// must close stdin via `< /dev/null` IN THE TEMPLATE LITERAL — `runQuiet`
// cannot do that for the caller because by the time it receives the
// ShellPromise, the redirect would have to already be inside the template.

import { log, elog } from "./logger.ts";

const HEARTBEAT_INTERVAL_MS = 5000;

// biome-ignore lint/suspicious/noExplicitAny: Bun's ShellPromise typing isn't loaded
export const runQuiet = async (label: string, p: any): Promise<void> => {
  const heartbeat = setInterval(() => {
    log(`  ... still running: ${label}`);
  }, HEARTBEAT_INTERVAL_MS);
  try {
    await p.quiet();
    clearInterval(heartbeat);
    log(`  ${label}`);
  } catch (err) {
    clearInterval(heartbeat);
    elog(`  ${label}: FAILED`);
    // biome-ignore lint/suspicious/noExplicitAny: ShellError is loosely typed
    const e = err as any;
    if (e?.stdout) elog(e.stdout.toString());
    if (e?.stderr) elog(e.stderr.toString());
    throw err;
  }
};
