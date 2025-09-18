# Principles

<!--TOC-->
- [Principles](#principles)
  - [High Quality](#high-quality)
  - [Lens of Pragmatism](#lens-of-pragmatism)
    - [1. The Time-Poor Developer Perspective:](#1-the-time-poor-developer-perspective)
    - [2. The Frugal Startup Founder Perspective:](#2-the-frugal-startup-founder-perspective)
    - [3. The Experienced Engineer Perspective:](#3-the-experienced-engineer-perspective)
  - [Less is More](#less-is-more)
  - [Pragmatic Filtering Criteria](#pragmatic-filtering-criteria)
    - [Examples of What NOT to refactor:](#examples-of-what-not-to-refactor)
    - [Examples of What TO refactor / fix:](#examples-of-what-to-refactor--fix)
  - [Testing Strategy](#testing-strategy)
<!--TOC-->

## High Quality

Where possible abide by the following popular SDLC Principles:

- [Twelve Factor App](https://www.12factor.net/)
- [SOLID](https://en.wikipedia.org/wiki/SOLID)

## Lens of Pragmatism

Also consider these pragmatic perspectives:

### 1. The Time-Poor Developer Perspective:

  - Every refactoring has opportunity cost
  - If it works, don't fix it
  - Scripts that run once a month don't need to be perfect
  - Copy-paste is often faster than abstraction
  - Understanding 5 simple scripts is easier than understanding 1 complex framework

### 2. The Frugal Startup Founder Perspective:

  - Time is the most scarce resource
  - Working code > perfect code
  - Technical debt is only debt if you have to pay it back
  - Many startups die with perfect code that never shipped
  - Hardcoded values are fine if they rarely change
  - Duplication is fine if the scripts work independently
  - "Best practices" often optimize for problems you don't have

### 3. The Experienced Engineer Perspective:

  - Not all technical debt is created equal
  - Some "debt" is actually just different trade-offs
  - Context matters more than principles
  - YAGNI (You Aren't Gonna Need It) is often right
  - Premature abstraction can be worse than duplication
  - Working code that ships has infinite more value than perfect code that doesn't


## Less is More

IMPORTANT: None of the above principles are more important than:

- Each script needs to stand-alone.
- There is such thing as too much refactoring.

## Pragmatic Filtering Criteria

Before refactoring code, ask:

1. **Does this cause actual failures or data issues?** If no, skip it.
2. **Has this caused a problem in the last 6 months?** If no, skip it.
3. **Would fixing this take more than 1 hour?** If yes, it better be critical.
4. **Is the "fix" more complex than the "problem"?** If yes, skip it.
5. **Will anyone notice if we don't fix this?** If no, skip it.

### Examples of What NOT to refactor:

- Hardcoded URLs that haven't changed in years
- Duplicate retry logic that works fine in each script
- Magic numbers that are commented inline
- Scripts doing "too much" if they work reliably
- Missing abstractions if the concrete implementations work
- Inconsistent patterns if each pattern works for its context
- Configuration that could be extracted but doesn't need to be

### Examples of What TO refactor / fix:

- Code that crashes: `async def` without implementation
- Data corruption risks: Writing to wrong directory
- Security issues: API keys in code (not just hardcoded endpoints)
- Performance issues that matter: 30-second operation that could be 1 second
- Frequent pain points: Something you fix manually every week

## Testing Strategy

**Default Approach: No Tests**
- If a script works on first run, it was simple enough that execution IS the end-to-end test.
- Don't write tests preemptively for straightforward scripts.

**Tests Warrant Creation When:**

- Script still fails after your first "fix" attempt.
- This signals complexity high enough to need tooling to isolate the problem space.
- Tests help identify which parts DO work vs. DO NOT work.
- Reduces problem complexity back to solvable size.

**When Explicitly Requested:**

- Target >75% code coverage (ideal).
- Target >50% code coverage is also pragmatically acceptable.
- Never lower the `--cov-fail-under=` threshold. Once we achieve a certain level, it should never regress.
- Use parametrised tests where possible to maximise least test code vs maxium scenarios covered.

**Philosophy:**

- Tests are a complexity signal, not always a requirement. Use them as tools to break down problems that prove too complex for direct fixing.
- Sometimes we need tests as a baseline before refactoring code, to then be our success criteria it still works.

**Systematic and Scientific Thinking:**

- Reason through the **symptoms**, 
- to then form **hypothesis** 
- and then synthesize **experiments**
- in the form of new **tests** or new **triage** scripts.