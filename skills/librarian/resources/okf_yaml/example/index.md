<!-- GENERATED from the bundle's *.yml by okf_render.py. Do not edit; regenerate. -->

# Decision Records

| Record | Decision | Status |
|---|---|---|
| [REC-0001](0001-validate-at-the-boundary.md) | Validate external payloads at the boundary, not at the point of use | accepted |
| [REC-0002](0002-one-error-taxonomy.md) | One error taxonomy, owned by the boundary that raises it | accepted |
# By group

## correctness

* [REC-0001](0001-validate-at-the-boundary.md) - Data crossing a trust boundary is validated once, where it enters
* [REC-0002](0002-one-error-taxonomy.md) - Every failure names its boundary and its cause, in one vocabulary
# Relationship graph

Open [graph.html](graph.html) to explore the records visually: click a node to read it, and links between records navigate the graph.
The same edge set is rendered as prose in [graph.md](graph.md), and as data in [graph.json](graph.json).

* REC-0001 --depended_on_by--> REC-0002
* REC-0002 --depends_on--> REC-0001
