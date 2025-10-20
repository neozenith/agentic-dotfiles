# Guideance Docs

## Overview

This folder represents an accumulation of learnings and refinements from having 1:1s with claude.

Taking projects and patterns that were successful and then getting claude to distill these patterns.

Subsequent projects then "prime" a claude code session by reading in the specific markdown file.

For example launch two claude code sessions in separate terminals:
- Session #1: `Read @.claude/misc/STATIC_SITES.md with a focus on Deck.GL for GIS purposes`
- Session #2: `Read @.claude/misc/PYTHON_HELPER_SCRIPTS.md and @.claude/misc/PRINCIPLES/md as we develop a data engineering pipeline to transform GIS data sources.`

Then each session works on their part of the code base with better context and focus.

After compactions these are helpful to re-prime the session context.

## TODO

Since starting on these Anthropic has released `Skills` which better maps to what is being aimed for here.

[Claude Code: Skills](https://docs.claude.com/en/docs/claude-code/skills)

I need to migrate and split these docs to be compliant with the new diorection of `.claude/skills/`