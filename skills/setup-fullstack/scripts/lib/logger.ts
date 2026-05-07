// Timestamped logger.
//
// Every line written through `log` / `elog` is prefixed with [HH:MM:SS +Ns],
// where the +Ns is wall-clock seconds since the script started. This makes a
// hang visible as a long elapsed-time gap between adjacent lines and lets the
// user attribute slowness to a specific step at a glance.

const SCRIPT_START_MS = Date.now();

export const tsPrefix = (): string => {
  const now = new Date();
  const hms = now.toTimeString().slice(0, 8); // "HH:MM:SS"
  const elapsed = ((Date.now() - SCRIPT_START_MS) / 1000).toFixed(1);
  return `[${hms} +${elapsed}s]`;
};

// biome-ignore lint/suspicious/noExplicitAny: process.stdout/stderr loose typing
const writeStamped = (stream: any, args: unknown[]): void => {
  const text = args
    .map((a) => (typeof a === "string" ? a : String(a)))
    .join(" ");
  const prefix = tsPrefix();
  for (const line of text.split("\n")) {
    if (line === "") {
      stream.write("\n");
    } else {
      stream.write(`${prefix} ${line}\n`);
    }
  }
};

/** Stamped stdout. Replacement for `console.log`. */
export const log = (...args: unknown[]): void =>
  writeStamped(process.stdout, args);

/** Stamped stderr. Replacement for `console.error`. */
export const elog = (...args: unknown[]): void =>
  writeStamped(process.stderr, args);

/** Wall-clock seconds since the script started. */
export const elapsedSeconds = (): number =>
  (Date.now() - SCRIPT_START_MS) / 1000;
