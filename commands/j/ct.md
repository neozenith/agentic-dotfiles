---
description: "Apply critical thinking with structured analysis and evidence validation"
---

# Critical Thinking Protocol

Analyze the following problem using systematic, evidence-based reasoning with structured multi-step thinking.

## Problem Statement

$ARGUMENTS

---

## Analysis Methodology

### Step 1: Structured Thinking (Sequential MCP)

Use the `mcp__sequential-thinking__sequentialthinking` tool to decompose this problem:

- **Initial thoughts estimate**: 20-30 steps for thorough analysis
- **Question assumptions**: Challenge each hypothesis before accepting it
- **Revise when needed**: Set `isRevision: true` when reconsidering previous thoughts
- **Branch if necessary**: Explore alternative explanations using `branchFromThought`
- **Adjust total**: Update `totalThoughts` up or down as understanding deepens

**Key principles**:
- Treat initial thoughts as hypotheses, not conclusions
- Don't proceed linearly if new evidence contradicts earlier reasoning
- Continue thinking until you reach a satisfactory answer, not a predetermined endpoint

### Step 2: Evidence Gathering

Before drawing conclusions, gather concrete evidence:

**Code Analysis**:
- Use `Read` tool to examine actual implementations
- Use `Grep` to search for patterns across the codebase
- Use `Glob` to identify relevant files

**Documentation Research**:
- Use `mcp__context7__resolve-library-id` + `mcp__context7__get-library-docs` for official framework documentation
- Use `WebFetch` for technical articles and authoritative sources
- Use `WebSearch` for broader research when needed

**Cross-Validation**:
- Verify claims across multiple sources
- Look for contradictions or edge cases
- Test assumptions against actual code behavior

### Step 3: Hypothesis Testing

For each hypothesis generated in Step 1:

1. **State the hypothesis clearly** - What are you claiming?
2. **Identify required evidence** - What would prove/disprove it?
3. **Gather that evidence** - Use appropriate tools
4. **Evaluate results** - Does evidence support the hypothesis?
5. **Document confidence level** - High (90%+), Medium (60-89%), Low (<60%)

If evidence contradicts a hypothesis, use Sequential MCP's revision capability to backtrack and reconsider.

### Step 4: Synthesis & Action Plan

Use `TodoWrite` to create a structured action plan:

**Each TODO should include**:
- Clear, actionable description
- Evidence supporting this action
- Success criteria (how to validate it worked)
- Priority level (high/medium/low)

**TODO format**:
```
content: "Implement X based on evidence Y"
activeForm: "Implementing X"
status: "pending"
```

---

## Quality Checklist

Before considering analysis complete, verify:

- [ ] All major claims are backed by specific evidence (file paths, line numbers, docs)
- [ ] Alternative explanations were considered and evaluated
- [ ] Confidence levels are explicitly stated for key conclusions
- [ ] Action plan includes validation criteria for each recommendation
- [ ] Assumptions and risks are documented
- [ ] The specific outcomes requested in the problem statement are addressed

---

## Expected Deliverables

1. **Thinking Chain**: Complete Sequential MCP thought process with revisions visible
2. **Evidence Summary**: Key findings with source attribution (files, docs, research)
3. **Analysis Report**: Conclusions with confidence levels
4. **Action Plan**: TodoWrite list with priorities and validation criteria
5. **Risk Assessment**: Known unknowns and potential issues

---

**Begin Analysis Now**: Apply the methodology above to the problem statement. Start with Sequential MCP thinking to structure your analysis, gather evidence systematically, and end with a concrete action plan.
