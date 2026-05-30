# Knowledge Graph Reference

A resolved-entity knowledge graph over chunked human-prompt content. Independent
SQL surface — query the tables directly. (Conceptual overview:
[README › Knowledge graph](../README.md#knowledge-graph).)

## Updating

The KG pipeline (chunk → NER → relations → entity embeddings → clustering →
canonical nodes/edges → Leiden communities → labels) runs during a cache update,
gated by the **same knob as embeddings** (KG depends on the embedding HNSW):

```bash
# Build / refresh the KG (embeddings enabled — first run downloads GLiNER2 ~205 MB
# + the embedding model ~150 MB, then is incremental)
.claude/skills/introspect/scripts/introspect_sessions.sh cache update
.claude/skills/introspect/scripts/introspect_sessions.sh cache rebuild   # full re-derive

# Skip the KG/embedding phase (faster; queries still work on existing KG rows)
CLAUDE_SESSIONS_DISABLE_EMBEDDINGS=1 \
  .claude/skills/introspect/scripts/introspect_sessions.sh cache update
```

Each phase is incremental (per-phase log tables), so warm updates are cheap. The KG
is also (re)built by the dashboard backend on start.

## Tables

| Table | Columns | Holds |
|-------|---------|-------|
| `entities` | name, entity_type, source, chunk_id, confidence | Per-mention entity rows |
| `relations` | src, dst, rel_type, weight, chunk_id, source | Per-mention relations |
| `entity_clusters` | name, canonical | name → canonical (synonym resolution) |
| `nodes` | name, entity_type, mention_count | Canonical entities |
| `edges` | src, dst, rel_type, weight | Coalesced canonical relations |
| `leiden_communities` | node, resolution, community_id, modularity | Multi-resolution community membership |
| `entity_cluster_labels` | canonical, label, member_count, model | LLM labels per canonical |
| `community_labels` | resolution, community_id, label, member_count | LLM labels per community |

The HNSW vector table `entities_vec` (+ `entity_vec_map`) is created at runtime by the
embedding phase; absent until the KG has run at least once.

## Query recipes

```bash
DB=~/.claude/cache/introspect_sessions.db

# Top canonical entities by mention count
sqlite3 "$DB" "SELECT name, entity_type, mention_count FROM nodes
               ORDER BY mention_count DESC LIMIT 20;"

# Relation types by frequency
sqlite3 "$DB" "SELECT rel_type, count(*) AS n FROM edges
               GROUP BY rel_type ORDER BY n DESC;"

# Community sizes at the default resolution
sqlite3 "$DB" "SELECT community_id, count(*) AS members
               FROM leiden_communities WHERE resolution = 0.25
               GROUP BY community_id ORDER BY members DESC LIMIT 10;"

# Synonyms resolved to a canonical name
sqlite3 "$DB" "SELECT name FROM entity_clusters WHERE canonical = 'YourEntity';"

# Neighbours of an entity (outgoing edges)
sqlite3 "$DB" "SELECT dst, rel_type, weight FROM edges
               WHERE src = 'YourEntity' ORDER BY weight DESC;"
```
