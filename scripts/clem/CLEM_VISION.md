# CLEM Vision: Solving LLM Anterograde Amnesia

## The Karpathy Insight

> "Agents/LLMs do not sleep. They do not have knowledge consolidation which results in them having anterograde amnesia." — Andrej Karpathy

**Two fundamental problems with LLMs**:

1. **💤 No Sleep** - No consolidation phase where experiences → long-term knowledge
2. **📚 No Books** - No consolidated knowledge artifacts for accelerated learning

**Result**: "50 First Dates" syndrome - every conversation starts fresh

## CLEM's Solution: Sleep Cycles

### Hierarchical Consolidation

```
Session Memories → Project Knowledge → Global Patterns → Skill Synthesis
     (minutes)         (hours/days)        (weeks)          (evolution)
```

### The Four Levels

**Level 1: Session Memory** (Minutes)
- Extract structured facts from conversations
- Topics: personal_info, preferences, key_decisions, explicit_instructions
- Technology: Flan-T5 + vector embeddings (384-dim)
- Output: `~/.claude/memories.duckdb`

**Level 2: Project Knowledge** (Hours/Days)
- Synthesize implicit requirements from project sessions
- Extract business + technical constraints
- Document architectural decisions
- Output: `BDD.md` in project root

**Level 3: Global Learning** (Weeks/Months)
- Recognize patterns across ALL projects
- Identify successful solutions and anti-patterns
- Synthesize generalized knowledge
- Output: `.claude/misc/PATTERNS.md`, `LESSONS.md`, `ANTI_PATTERNS.md`

**Level 4: Skill Evolution** (Continuous)
- Meta-analysis of how you use Claude Code
- Generate new personas or command patterns
- Suggest framework improvements
- Output: Updates to SuperClaude configuration

## The Workflow

```bash
# After project work, run sleep cycle
cd /path/to/project
make -C .claude/scripts/clem sleepytime

# This consolidates:
# 1. Recent conversation memories
# 2. Project requirements (BDD.md)
# 3. Cross-project patterns
# 4. Framework skill updates
```

## The Impact

### Before CLEM
- ❌ Stateless, amnesiac interactions
- ❌ Repeat explanations in every project
- ❌ No memory of preferences or style
- ❌ Implicit requirements never captured
- ❌ Patterns recognized but never consolidated
- ❌ Manual, incomplete learning from past work

### After CLEM
- ✅ Continuous learning loop with memory consolidation
- ✅ Persistent understanding of coding style and preferences
- ✅ Automatic extraction of implicit requirements
- ✅ Pattern recognition and consolidation across projects
- ✅ Knowledge artifacts as "books" for accelerated onboarding
- ✅ Framework evolves based on actual usage patterns

## The Continuous Learning Loop

```
Experience → Consolidation → Knowledge → Distribution → Enhanced Experience
    ↑                                                            ↓
    └────────────────────── Feedback Loop ──────────────────────┘
```

**Each cycle**:
1. Experience: Work on projects with Claude Code
2. Consolidation: Run `make sleepytime` to extract knowledge
3. Knowledge: Generate structured artifacts (BDD.md, PATTERNS.md)
4. Distribution: Load relevant context in future sessions
5. Enhanced Experience: Claude Code knows your history and patterns

**Result**: Incremental intelligence - Claude Code becomes more valuable with every interaction

## Technical Architecture

### Two-Phase Processing

**Phase 1: Extraction (Flan-T5)**
```
Conversations → Flan-T5-base → Candidate Memories
              (instruction-tuned) (topic classification)
```

**Phase 2: Consolidation (Vector Similarity)**
```
Candidate Memory → Embedding → Similarity Search → ADD/UPDATE/IGNORE
                  (384-dim)    (existing memories)  (smart deduplication)
```

### Consolidation Thresholds
- `similarity > 0.90` → **IGNORE** (duplicate)
- `similarity > 0.75` → **UPDATE** (more detailed, version increment)
- `similarity < 0.75` → **ADD** (new memory)

### Performance
- **Session Memory**: 10-20s for 20-50 messages
- **Project Knowledge**: 1-3 min for 200-500 messages
- **Global Learning**: 5-15 min for 1K-5K messages
- **Full Sleep Cycle**: 10-25 min for complete consolidation

## Knowledge Artifacts

### Project-Level: BDD.md
```markdown
# Business & Technical Requirements

## Business Requirements
- User needs OAuth authentication for social login
- System must handle 10K concurrent users

## Technical Constraints
- Must use PostgreSQL (existing infrastructure)
- Deploy to AWS Lambda (cost optimization)

## Architectural Decisions
- Event-driven architecture for scalability
- CQRS pattern for read/write separation
```

### Global-Level: PATTERNS.md
```markdown
# Architectural Patterns

## Authentication Patterns
Across 12 projects, consistent pattern emerged:
- JWT tokens with refresh mechanism
- Redis for session storage
- Rate limiting at API gateway level
```

### Global-Level: LESSONS.md
```markdown
# Lessons Learned

## Database Migrations
❌ Avoid: Running migrations without rollback scripts
✅ Prefer: Versioned migrations with automated rollback
```

## The Vision

**Current State**: Phase 1 complete (session memory extraction)

**Near Future** (Phase 2-3):
- Automated BDD.md generation from conversations
- Cross-project pattern recognition
- Lessons learned synthesis

**Long-term Vision** (Phase 4):
- Context injection: Load relevant memories before sessions
- Proactive suggestions: "You've solved this before in project X"
- Knowledge graphs: Link related concepts across projects
- Temporal analysis: Track how practices evolve
- Collaborative learning: Share anonymized patterns

## Why This Matters

**CLEM transforms LLM assistance from ephemeral to persistent**:

- Not just memory storage → **Incremental intelligence**
- Not just search → **Knowledge consolidation**
- Not just retrieval → **Continuous learning**
- Not just tools → **Cognitive architecture**

**The ultimate goal**: Every developer gets an AI assistant that:
- Knows their style and preferences
- Remembers their decisions and patterns
- Continuously improves based on collective work
- Distributes learning through knowledge artifacts

**The reality**: CLEM makes this possible today, locally, on your machine.

## References

- **Inspiration**: Andrej Karpathy's insights on LLM intelligence gaps
- **Technology**: Flan-T5 (Google), sentence-transformers, DuckDB VSS
- **Framework**: SuperClaude for Claude Code
- **Philosophy**: Incremental intelligence through sleep cycles

---

*CLEM: Claude Learning & Embedded Memory - Solving anterograde amnesia through hierarchical knowledge consolidation*
