# Goldens

A **golden** is a real, complete, correct output artifact — the thing a good run of this
skill should produce — committed so a case can compare against it (ADR 0046).

```
evals/
  fixtures/<name>/<path>    # the seed the agent starts from
  goldens/<name>/<path>     # a known-good answer for that seed
```

The two trees mirror each other, so the pairing is the layout rather than a convention
anyone has to remember. `GoldenCase.at(EVALS, "<name>", "<path>", facets)` resolves it.

## Why a golden is not a diff

Two valid answers differ in whitespace, in the order `classDef` lines appear, in whether a
group is called `service` or `svc`, in one hex being a legitimate neighbour on the same
palette ramp. Comparing files would be red on every run and would teach its reader to
ignore it. Comparing substrings (`"classDef" in doc`) is satisfied by styling one node of
four.

So a golden is compared **facet by facet**, and each facet declares how free that part of
the answer is: `Exact`, `Superset`, `Jaccard`, `Ratio`, `Count`, `Within`. Those
tolerances are the interesting content of the eval — they are the author's actual claim
about what the skill guarantees, so they belong where a reviewer reads them.

`eval_palette_mandate.py` is the worked example.

## What lives here

### `unstyled_diagram/ARCHITECTURE.md`

The four-node ingest flowchart of `fixtures/unstyled_diagram/`, with the mandatory colour
theming applied. It passes both of the skill's own gates — which is what makes it a
golden rather than a plausible file:

```sh
cd ../../scripts
bun run mermaid_contrast.ts   ../evals/goldens/unstyled_diagram/ARCHITECTURE.md   # 8 pass, 0 fail
bun run mermaid_complexity.ts ../evals/goldens/unstyled_diagram/ARCHITECTURE.md   # exit 0
```

Its palette is deliberately *not* copied from the examples in
`resources/color_theming.md`: those fail the skill's own border-contrast threshold
(stroke against fill, ≥3.0). The fills here are the darker end of each ramp with the
lighter tint as the stroke, which passes at 4.4–5.0.

## Changing a golden

Re-run the gates above, and commit the change on its own so a reviewer sees it. A golden
that moves because the skill's contract moved is a decision; one that moves to make a red
cell go green is the thing this mechanism exists to prevent.

`GoldenCase.record(output)` writes a run's output into the golden path for exactly this
purpose. It is never called from a grader — a run that could launder its own output into
the reference would make every later comparison vacuous.
