---
paths:
  - "**/triage_*.py"
---

# Triage Script Conventions

Rules for `triage_*.py` scripts that analyze logs/tests and suggest next steps.

## Purpose

Triage scripts collate log and test information, then critically analyze the output to systematically suggest a next step. They enable autonomous decision-making by producing structured, self-documenting output.

## Required Output Sections

Every triage script must produce these sections:

### STATUS SUMMARY
Current system state with key metrics.

### FINDINGS
Categorized issues with evidence:
- **Critical**: Immediate action required
- **High**: Should be addressed soon
- **Medium**: Important but not urgent
- **Low**: Nice to fix when time permits

### RECOMMENDATIONS
Prioritized next steps with:
- Reasoning for each recommendation
- Confidence levels (e.g., "90% confident this is network latency")
- Success criteria for recommended actions

### EVIDENCE LINKS
Specific references supporting conclusions:
- Log entries with file paths and line numbers
- Data points with timestamps
- Files that led to conclusions

### ASSUMPTIONS
What the analysis assumes to be true. Document these explicitly so they can be validated.

### ALTERNATIVES
Other hypotheses considered and why they were ruled out. This helps avoid re-investigating dead ends.

## Output Format Standards

- Use structured text (YAML/JSON) for machine parsing when beneficial
- Include confidence percentages on recommendations
- Reference specific files/lines that led to conclusions
- Document any manual verification steps needed

## Example Output Structure

```yaml
# STATUS SUMMARY
status: degraded
uptime: 99.2%
error_rate: 0.8%
last_incident: 2024-01-15T14:30:00Z

# FINDINGS
critical: []
high:
  - issue: "Connection timeouts to database"
    evidence: "logs/app.log:1234-1256"
    frequency: "15 occurrences in last hour"
medium:
  - issue: "Slow response times on /api/users"
    evidence: "metrics/latency.json"
    p99: "2.3s (threshold: 1s)"

# RECOMMENDATIONS
1:
  action: "Increase database connection pool size"
  confidence: 85%
  reasoning: "Connection exhaustion pattern in logs"
  success_criteria: "Error rate drops below 0.1%"
2:
  action: "Add index on users.email column"
  confidence: 70%
  reasoning: "Query plan shows full table scan"

# ASSUMPTIONS
- Database server has available connections
- No network partitions between app and db

# ALTERNATIVES CONSIDERED
- Memory leak: Ruled out - heap usage stable at 60%
- CPU throttling: Ruled out - CPU at 40%
```

## --help Documentation

The `--help` output should include guidance on:
- What data sources the script analyzes
- How to interpret confidence levels
- What manual verification might be needed
- How to provide feedback to improve the script
