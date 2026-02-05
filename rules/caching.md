# Caching Strategy

Rules for implementing caching in scripts and applications.

## When Cache Strategy is Unclear

Ask follow-up questions and suggest pros/cons to better understand the trade-offs:

| Direction | Benefits |
|-----------|----------|
| **Longer cache** | Reduces costs, prevents rate limiting, forces systematic analysis, matches infrastructure realities |
| **Shorter cache** | Enables faster iteration, more responsive to changes, better for rapid development cycles |

## Default Decision Framework

1. What's the natural update cycle of the system?
2. Is rapid iteration helping or hurting problem-solving?
3. Are there rate limits or costs to consider?
4. Would forced delays improve analysis quality?

## Default Values

- Default cache timeout: **300 seconds (5 minutes)**
- Cache location: `tmp/claude_cache/{script_name}/`

## Cache Validation Pattern

A cache is valid when both conditions are true:
- Cache is newer than all inputs (delta > 0)
- Cache has not expired (remaining > 0)

```python
_is_cache_valid = lambda t: all(x > 0 for x in t)  # noqa: E731
```
