# State: complete — terminal

Every ticket is `[x]`, no open markers remain, and the machine recorded evidence for every
transition along the way. There is no work in this state.

If asked to summarise: report the Progress table totals, the Success Measures and how each was
demonstrated (the committed proof-of-execution artifacts), and the transition history from
`.pgsm/state.json` (every state, its entry time, and the gate evidence that fired it).

Re-opening a completed spec is a deliberate act: a new requirement means a new `<!-- UNRESOLVED -->`
ADR in the affected gap file followed by `pgsm next` — never silent edits to a closed plan.
