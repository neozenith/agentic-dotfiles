// `list-variations` subcommand — print every variation's name + description.
// Useful both for discovery and for shell pipelines that want to iterate the
// full set without hardcoding the list.

import { parseArgs } from "node:util";

import { VARIATIONS } from "../lib/variations.ts";

export const LIST_VARIATIONS_HELP = `\
setup-fullstack list-variations — print every known variation.

USAGE
  setup-fullstack list-variations [--names-only]

OPTIONS
  -h, --help          Show this help and exit.
  --names-only        Print one name per line, no descriptions. Pipeline-friendly.

EXAMPLES
  setup-fullstack list-variations
  setup-fullstack list-variations --names-only | xargs -n1 setup-fullstack variation
`;

export const listVariationsMain = (argv: string[]): number => {
  const { values } = parseArgs({
    args: argv,
    options: {
      help: { type: "boolean", short: "h", default: false },
      "names-only": { type: "boolean", default: false },
    },
    allowPositionals: false,
    strict: true,
  });

  if (values.help) {
    process.stdout.write(LIST_VARIATIONS_HELP);
    return 0;
  }

  if (values["names-only"]) {
    for (const v of VARIATIONS) process.stdout.write(`${v.name}\n`);
    return 0;
  }

  const longest = Math.max(...VARIATIONS.map((v) => v.name.length));
  for (const v of VARIATIONS) {
    process.stdout.write(`${v.name.padEnd(longest)}  ${v.description}\n`);
  }
  return 0;
};
