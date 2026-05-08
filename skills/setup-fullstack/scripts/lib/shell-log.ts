// Append-to-file logging helpers used by the variation + matrix subcommands.
//
// The bash predecessors wrote a per-variation log (tmp/variation-<name>.log)
// and a matrix-summary log (tmp/matrix-summary.log) that captured stdout +
// stderr from every shell-out plus framing headers. The TypeScript port keeps
// the same files in the same paths so existing tooling (less, grep, log
// pickers) keeps working.

import { mkdir, appendFile } from "node:fs/promises";
import { dirname } from "node:path";

/** Ensure the log file's parent directory exists, then append `text`. */
export const appendLog = async (path: string, text: string): Promise<void> => {
  await mkdir(dirname(path), { recursive: true });
  await appendFile(path, text);
};

/** Append a single line (newline-terminated) to the log file. */
export const appendLogLine = async (
  path: string,
  line: string,
): Promise<void> => {
  await appendLog(path, `${line}\n`);
};

/**
 * Append a Bun ShellOutput (or any { stdout, stderr } pair of Buffer/string)
 * to the log. Used after running a non-interactive shell-out where we want the
 * full captured output preserved on disk regardless of pass/fail.
 */
export const appendShellOutput = async (
  path: string,
  out: { stdout: Buffer | string; stderr: Buffer | string },
): Promise<void> => {
  const stdout = typeof out.stdout === "string" ? out.stdout : out.stdout.toString();
  const stderr = typeof out.stderr === "string" ? out.stderr : out.stderr.toString();
  if (stdout) await appendLog(path, stdout);
  if (stderr) await appendLog(path, stderr);
};
