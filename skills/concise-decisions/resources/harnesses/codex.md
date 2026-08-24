# Harness adapter: Codex CLI

Part of `concise-decisions` ([../../SKILL.md](../../SKILL.md) step 4). Load
when `CODEX_SANDBOX`, `CODEX_PROXY_CERT`, or any `CODEX_ENV_*` variable is
set.

## Use the session-feed adapter

Codex's structured `request_user_input` surface is tied to **Plan mode**. The
skill is used while refining the user's own planning documents in Default
mode, so Plan mode is not an acceptable dependency. In every Codex mode,
render the question per [session-feed.md](session-feed.md): one markdown
message, reply footer last. Rehearsed and signed off in Default mode for all
five shapes.

## Codex-specific notes

- The five-iteration convergence in rehearsal came from, in order: complete
  real commands per option (not fragments); pros and cons on separate lines;
  recommendation moved into the option title; context split into the four
  labelled lines. All four are now base-template rules — do not relearn them.
- `TBD` is the visible label; `T` was misread as a fourth option.
- A decision sentence compressed to a fragment ("Decision: choose the
  ordered-rule syntax") failed check 1; write the complete sentence.
- Keep rehearsal/grading instructions outside the question message.

## Unverified

- Plan-mode `request_user_input`: option cap, preview support, whether free
  text can ride on a selected option. Until verified, the session-feed adapter
  applies in every mode. If it is verified to carry per-option reasoning,
  add a Codex-structured pattern here modelled on
  [claude-code.md](claude-code.md) and record the change as an ADR in
  [../../docs/adrs/](../../docs/adrs/README.md). If it cannot carry free
  text on the selected option, it is not an adapter for this skill at all
  (multichoice without reasoning is the failure the user named).
