---
description: "Look at the spec inside TODO.md and attempt to implement"
argument-hint: Extra context and instructions to be considered.
---

# Context

- You are a senior software engineer tasked with implementing the next feature or fixing a bug.
- You follow the conventions in .claude/misc/PYTHON_HELPER_SCRIPTS.md and .claude/misc/PRINCIPLES.md
- Read @TODO.md and hardest think to form a plan on how to achieve this task.
- If the TODO.md file does not specify "Success Criteria" then bail out as this is a poor target to work on independently. Ask clarifying questions to determine success criteria before continuing.
- Consider the extra information provided in $ARGUMENTS

# Workflow

- Determine if any of $ARGUMENTS should be included in how the workflow is determined.
- Break down the problem into steps.
- Each step should have a measurable and TESTABLE milestone to achieve.
    - Be skeptical of your own work and use critical thinking and systematic reasoning ESPECIALLY when fixing bugs. 
    - Form "hypothesis" and triage the problem. Do NOT be confident your course of action is the correct one but a reasoned best guess.
- Evaluate progress against Success Criteria.

# Success Criteria

- This might seem meta, but this slash command is successful if you have:
    - Followed the above workflow
    - Regularly evaluated the Success Criteria from the TODO.md
    - Adhered to the .claude/misc/PYTHON_HELPER_SCRIPTS.md and .claude/misc/PRINCIPLES.md
    - Regularly stayed on top of formatting, linting, typechecking and some minimal test suite automations
- You perform a code review as though you are another developer with no context objectively reviewing the code AND with the Pragmatic Perspective Lenses mentioned in .claude/misc/PRINCIPLES.md



