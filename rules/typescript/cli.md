# TypeScript CLI Conventions

Rules for building stdlib-based CLIs in this project.

## Library Choice

Use **`node:util.parseArgs`** (stdlib, available in Node ≥ 18.3 and Bun). Do not introduce `commander`, `yargs`, `oclif`, `citty`, or any other CLI framework.

The API covers 95% of CLI needs: typed options, short/long flags, positionals, strict unknown-flag rejection, and subcommand routing via `tokens`.

## Single-Command Scripts

For a script with a handful of flags and no subcommands, this is the full pattern:

```typescript
#!/usr/bin/env bun
import { parseArgs } from "node:util";

function printHelp(): void {
  console.log([
    "Usage: my-script <input-file> [--json] [--force]",
    "",
    "Do the thing.",
    "",
    "Options:",
    "  --json       Emit JSON output",
    "  -f, --force  Overwrite existing output",
    "  -h, --help   Show this help and exit",
  ].join("\n"));
}

async function main(): Promise<void> {
  const { values, positionals } = parseArgs({
    args: Bun.argv.slice(2),
    options: {
      json: { type: "boolean", default: false },
      force: { type: "boolean", short: "f", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) { printHelp(); return; }
  if (positionals.length === 0) { printHelp(); process.exit(2); }

  // ... actual work ...
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`error: ${msg}`);
  process.exit(1);
});
```

Key points:
- `strict: true` — reject unknown flags at parse time (equivalent to argparse's default behavior).
- Always catch at the top level and exit with a non-zero code on error (no uncaught-rejection noise).
- `process.exit(2)` for usage errors, `process.exit(1)` for runtime errors — matches Unix convention and argparse.

## Subcommand Structure

For CLIs with subcommands, emulate argparse's `set_defaults(func=...)` dispatch. The pattern is a two-pass parse: first peel off the subcommand positional, then re-parse the remainder against that subcommand's options.

```typescript
type Handler = (args: Record<string, unknown>) => Promise<void> | void;

interface Subcommand {
  name: string;
  help: string;
  options: Parameters<typeof parseArgs>[0]["options"];
  handler: Handler;
}

const COMMANDS: Subcommand[] = [
  {
    name: "status",
    help: "Show current state of X",
    options: { json: { type: "boolean", default: false } },
    handler: cmdStatus,
  },
  {
    name: "reset",
    help: "Reset X to defaults",
    options: { force: { type: "boolean", short: "f", default: false } },
    handler: cmdReset,
  },
];

async function main(): Promise<void> {
  const argv = Bun.argv.slice(2);
  const [cmdName, ...rest] = argv;

  if (!cmdName || cmdName === "-h" || cmdName === "--help") {
    printTopLevelHelp();
    return;
  }

  const cmd = COMMANDS.find((c) => c.name === cmdName);
  if (!cmd) {
    console.error(`error: unknown command '${cmdName}'`);
    printTopLevelHelp();
    process.exit(2);
  }

  const { values, positionals } = parseArgs({
    args: rest,
    options: { ...cmd.options, help: { type: "boolean", short: "h" } },
    allowPositionals: true,
    strict: true,
  });

  if (values.help) { printSubcommandHelp(cmd); return; }
  await cmd.handler({ ...values, _: positionals });
}
```

### Why This Pattern (vs. nested argparse)

`node:util.parseArgs` doesn't natively support subparsers — but it doesn't need to. Subcommands are just "the first positional picks which option schema to apply." The two-pass parse keeps the library stdlib and the logic transparent.

The `handler` field on each subcommand is the direct analog of Python's `set_defaults(func=real_handler)`. Top-level dispatch is:
- Leaf subcommand → `handler` is the real function.
- No subcommand / unknown subcommand → fall through to `printTopLevelHelp()`.

## Visibility Verb Convention

Read-only subcommands that display current state use **`status`** as their subcommand name (not `show`, `stats`, `info`, etc.):

```typescript
{ name: "status", help: "Show current state of X", ... }
```

Destructive or write subcommands use imperative verbs: `reset`, `init`, `set`, `seed`, `enable`, `disable`.

## Module Layout

For CLIs with more than ~3 subcommands:

```
src/cli/
├── app.ts              # build_parser equivalent + main() only — no business logic
├── commands/
│   ├── status.ts       # cmdStatus handler
│   ├── reset.ts        # cmdReset handler
│   └── ...
├── config.ts           # default values and CLI-level config helpers
├── formatting.ts       # date parsers, display helpers
└── logger.ts           # shared logger instance
```

`app.ts` imports handlers from `commands/` and wires them into the `COMMANDS` array. All business logic lives under `commands/`.

## Help Text

- Exit code 0 when `--help` is explicit.
- Exit code 2 when help is shown because arguments were missing or invalid.
- Write help to **stdout** when requested, **stderr** when the user made a mistake.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Runtime error (caught exception, file not found, parse error in input data) |
| 2    | Usage error (missing arg, unknown flag, bad value) |
