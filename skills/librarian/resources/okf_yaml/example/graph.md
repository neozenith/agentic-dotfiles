# Decision relationship graph

2 decision records, 2 typed edges, grouped into
1 groups. Every edge comes from a record's `relates_to`
block, so this view cannot drift from the records.

```cytoscape
{ "data": "graph.json", "height": 620 }
```

## Edge vocabulary

| Relation | Inverse | Meaning |
|---|---|---|
| `extends` | `extended_by` | Adds a clause to an existing decision without replacing it |
| `split_from` | `split_to` | The record was carved out of another when one grew two decisions |
| `supersedes` | `superseded_by` | Replaces the earlier decision; the earlier record stays, marked superseded |
| `depends_on` | `depended_on_by` | The decision is only implementable because the other one holds |
| `tests` | `tested_by` | Names how the other decision is verified |
| `see_also` | `see_also` | Related reasoning, no dependency |

## Asymmetries

An edge whose inverse is missing on the far record. These are gaps in the
record set, not rendering artifacts.

None: every edge has its inverse.
