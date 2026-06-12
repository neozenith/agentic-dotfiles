# State: refinement — settle open decisions, one question at a time

The composed context below includes the index and every gap file that still carries an open marker
(`<!-- UNRESOLVED -->`, `<!-- CHANGE-REQUEST -->`, or `<!-- ASSUMPTION`). Your job this turn:

1. **Assemble the open set.** Every `<!-- UNRESOLVED -->` ADR, plus any ambiguity with no ADR yet
   (unspecified format/threshold/library, implicit assumptions in Outputs/Key logic, unfalsifiable
   measures). Create an `<!-- UNRESOLVED -->` placeholder for each newly found ambiguity so it is
   rankable. Convert each `<!-- ASSUMPTION: ... -->` into either a settled fact (the evidence is in
   the repo) or an `<!-- UNRESOLVED -->` ADR.
2. **Rank by cross-gap impact.** Pick the SINGLE question whose answer resolves the most ADRs
   across the most gaps and unblocks the most downstream work.
3. **Ask exactly one question.** State why it is the highest-leverage question now, which
   `G<n>`/`ADR<n>.<m>` it settles, the cascade it knocks out, and your researched recommendation
   ranked first so the user can confirm a default in one word. Never dump a question list.
4. **Incorporate the answer** (when one is available this turn): rewrite each affected ADR into
   settled bulleted form (**Decision / Why / Rejected**), delete the marker and Pros/Cons table,
   update the index Decisions roll-up, and cascade into Outputs, Key logic, Measures, and affected
   `DISCOVERY.md` diagrams. Use precise edits, never whole-file rewrites; never flip a
   `[ ]`↔`[x]` checkbox.

A `<!-- CHANGE-REQUEST -->` marker in a gap file is a recorded plan defect from execution: rescope
that gap (restate Outputs/tickets so real evidence is producible), then delete the marker.

If no human is available to answer and the top question cannot be self-answered from repo evidence,
STOP after posting the question — the machine pauses in this state by design (the exit gate is
"zero open markers", and only an answered question removes one). Reducing the open-marker count is
the only progress metric for this state; an answer that quietly downgrades a requirement to
optional/fallback is the failure this state exists to catch — reject it and re-ask.
