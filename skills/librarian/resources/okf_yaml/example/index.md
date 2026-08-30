# Decision Records

* [REC-0001: Validate external payloads at the boundary, not at the point of use](0001-validate-at-the-boundary.md) - Data crossing a trust boundary is validated once, where it enters
* [REC-0002: One error taxonomy, owned by the boundary that raises it](0002-one-error-taxonomy.md) - Every failure names its boundary and its cause, in one vocabulary
# By group

## correctness

* [REC-0001](0001-validate-at-the-boundary.md) - Data crossing a trust boundary is validated once, where it enters
* [REC-0002](0002-one-error-taxonomy.md) - Every failure names its boundary and its cause, in one vocabulary
# Relationship graph

The typed edge set is rendered in [graph.md](graph.md), and generated as
[graph.json](graph.json) for any Cytoscape viewer.

* REC-0001 --depended_on_by--> REC-0002
* REC-0002 --depends_on--> REC-0001
