# Memory Extraction Research: VertexAI Memory Bank & Open-Source Implementation

## Overview

This document details how Google's VertexAI Memory Bank extracts and manages conversational memories, and proposes an implementation using HuggingFace models and DuckDB.

## VertexAI Memory Bank Architecture

### Core Components

1. **Memory Extraction**: LLM analyzes user-agent conversations to identify relevant information
2. **Memory Consolidation**: Evaluates new information against existing memories
3. **Coherence Checking**: Identifies contradictions and determines whether to add, update, or delete memories
4. **Semantic Storage**: Stores memories with vector embeddings for semantic search

### The 4 Managed Memory Topics

Google's Memory Bank defines 4 default managed topics that guide extraction:

#### 1. USER_PERSONAL_INFO
**Description**: Significant personal information about the user
**Examples**:
- Names, relationships, family members
- Hobbies and interests
- Important dates (birthdays, anniversaries)
- Professional information (job, company)
- Location information

**Sample Extraction**:
```
Input: "I work at Google as a software engineer and my wedding anniversary is on December 31"
Extracted Memories:
  - User works at Google
  - User role: software engineer
  - Wedding anniversary: December 31
```

#### 2. USER_PREFERENCES
**Description**: Stated or implied likes, dislikes, preferred styles, or patterns
**Examples**:
- Likes and dislikes
- Preferred styles (music, art, design)
- Behavioral patterns
- Communication preferences

**Sample Extraction**:
```
Input: "I prefer the middle seat when flying and I hate spicy food"
Extracted Memories:
  - Prefers middle seat on flights
  - Dislikes spicy food
```

#### 3. KEY_CONVERSATION_DETAILS
**Description**: Important milestones, outcomes, or conclusions within dialogue
**Examples**:
- Task completion status
- Decisions made
- Important conclusions reached
- Follow-up actions agreed upon

**Sample Extraction**:
```
Input: "We decided to go with the blue design for the website header"
Extracted Memories:
  - Decision: Use blue design for website header
```

#### 4. EXPLICIT_INSTRUCTIONS
**Description**: Information user explicitly asks the agent to remember or forget
**Examples**:
- "Remember that..."
- "Don't forget..."
- "Please forget about..."
- "Never mention..."

**Sample Extraction**:
```
Input: "Remember that I never want to be contacted on weekends"
Extracted Memories:
  - User non-negotiable: No weekend contact
```

### Memory Extraction Process

The extraction happens in two phases:

#### Phase 1: Extraction
```
Session Events → Extraction LLM → Structured Facts

Prompt Template (conceptual):
"""
Extract key information from the following conversation that falls into these categories:
1. Personal information (names, dates, relationships, profession)
2. Preferences (likes, dislikes, styles, patterns)
3. Key decisions or conclusions
4. Explicit instructions to remember or forget

Conversation:
{session_messages}

Extract facts in structured format.
"""
```

#### Phase 2: Consolidation
```
New Facts + Existing Memories → Consolidation LLM → Actions (ADD/UPDATE/DELETE)

Prompt Template (conceptual):
"""
Given these existing memories:
{existing_memories}

And these new facts:
{new_facts}

For each new fact, determine:
- ADD: If it's genuinely new information
- UPDATE: If it contradicts or refines existing memory (include memory_id)
- DELETE: If it explicitly requests forgetting (include memory_id)
- IGNORE: If it's redundant

Check for:
- Temporal coherence (newer information supersedes older)
- Logical coherence (contradictions)
- Semantic similarity (deduplication)
"""
```

### Coherence Checking Mechanisms

1. **Semantic Similarity**: Use vector embeddings to find related memories
2. **Temporal Ordering**: Newer memories can supersede older ones
3. **Contradiction Detection**: LLM identifies logical conflicts
4. **Merge Logic**: Similar facts are consolidated into single memory

**Example Flow**:
```
Existing Memory: "User prefers coffee"
New Fact: "User now prefers tea instead of coffee"

Coherence Check:
  - Semantic similarity: 0.85 (high similarity detected)
  - Temporal: New fact is more recent
  - Contradiction: Yes (coffee → tea)

Action: UPDATE memory_id=123
Result: "User prefers tea (changed from coffee on 2025-10-31)"
```

## Open-Source Implementation with HuggingFace + DuckDB

### Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│                     Memory Extraction System                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Session   │───▶│  Extraction  │───▶│ Consolidation │  │
│  │   Events    │    │  LLM         │    │ LLM           │  │
│  └─────────────┘    │ (Flan-T5)    │    │ (Flan-T5)     │  │
│                     └──────────────┘    └───────────────┘  │
│                            │                     │           │
│                            ▼                     ▼           │
│                     ┌──────────────────────────────┐        │
│                     │    Structured Facts          │        │
│                     │    {topic, content, meta}    │        │
│                     └──────────────────────────────┘        │
│                                  │                           │
│                                  ▼                           │
│                     ┌──────────────────────────────┐        │
│                     │   Semantic Search Engine     │        │
│                     │   (Sentence-Transformers)    │        │
│                     └──────────────────────────────┘        │
│                                  │                           │
│                                  ▼                           │
│                     ┌──────────────────────────────┐        │
│                     │    DuckDB Vector Store       │        │
│                     │  - memories table            │        │
│                     │  - embeddings (384-dim)      │        │
│                     │  - temporal metadata         │        │
│                     └──────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Models

#### 1. Extraction LLM: Flan-T5-Large
- **Model**: `google/flan-t5-large` (780M parameters)
- **Purpose**: Extract structured facts from conversations
- **Why**: Fine-tuned on 1000+ tasks, excellent instruction following
- **Alternative**: `google/flan-t5-xl` (3B) for better quality

```python
from transformers import T5ForConditionalGeneration, T5Tokenizer

extraction_model = T5ForConditionalGeneration.from_pretrained("google/flan-t5-large")
extraction_tokenizer = T5Tokenizer.from_pretrained("google/flan-t5-large")
```

#### 2. Consolidation LLM: Flan-T5-Large or Mistral-7B-Instruct
- **Model**: `google/flan-t5-large` or `mistralai/Mistral-7B-Instruct-v0.2`
- **Purpose**: Decide ADD/UPDATE/DELETE actions
- **Why**: Needs reasoning capability for contradiction detection

```python
# For better reasoning, use Mistral
from transformers import AutoModelForCausalLM, AutoTokenizer

consolidation_model = AutoModelForCausalLM.from_pretrained(
    "mistralai/Mistral-7B-Instruct-v0.2",
    load_in_8bit=True  # Quantization for memory efficiency
)
consolidation_tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.2")
```

#### 3. Embeddings: Sentence-Transformers
- **Model**: `all-MiniLM-L6-v2` (already used in CLEM)
- **Purpose**: Generate embeddings for semantic similarity
- **Dimension**: 384
- **Why**: Fast, small, good quality

```python
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
```

### DuckDB Schema Design

```sql
-- Main memories table with vector embeddings
CREATE TABLE memories (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    topic VARCHAR NOT NULL,  -- personal_info, preferences, decisions, instructions
    content TEXT NOT NULL,
    embedding FLOAT[384],

    -- Metadata
    confidence FLOAT DEFAULT 1.0,
    source_session_id VARCHAR,
    source_timestamp BIGINT,

    -- Temporal tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    supersedes VARCHAR,  -- ID of memory this replaces

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1
);

-- Index for fast user lookups
CREATE INDEX idx_user_topic ON memories(user_id, topic, is_active);

-- Memory relationships (for tracking updates/contradictions)
CREATE TABLE memory_relationships (
    id VARCHAR PRIMARY KEY,
    memory_id VARCHAR NOT NULL,
    related_memory_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL,  -- supersedes, contradicts, refines, related_to
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (memory_id) REFERENCES memories(id),
    FOREIGN KEY (related_memory_id) REFERENCES memories(id)
);

-- Memory changelog for audit trail
CREATE TABLE memory_changes (
    id VARCHAR PRIMARY KEY,
    memory_id VARCHAR NOT NULL,
    action VARCHAR NOT NULL,  -- ADD, UPDATE, DELETE
    old_content TEXT,
    new_content TEXT,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (memory_id) REFERENCES memories(id)
);
```

### Implementation Pseudocode

#### Step 1: Extraction

```python
def extract_memories_from_session(session_messages: list[dict]) -> list[dict]:
    """Extract structured memories from conversation."""

    # Prepare extraction prompt
    prompt = f"""Extract key information from this conversation.

Categorize each fact into one of these topics:
1. PERSONAL_INFO: Names, dates, relationships, profession, location
2. PREFERENCES: Likes, dislikes, styles, patterns, behaviors
3. KEY_DECISIONS: Important conclusions, decisions, outcomes
4. EXPLICIT_INSTRUCTIONS: Things user explicitly asked to remember/forget

Conversation:
{format_messages(session_messages)}

For each fact, output:
- topic: [category]
- content: [the fact]
- confidence: [0.0-1.0]

Extract facts:"""

    inputs = extraction_tokenizer(prompt, return_tensors="pt", max_length=1024, truncation=True)
    outputs = extraction_model.generate(
        **inputs,
        max_new_tokens=512,
        temperature=0.3,  # Lower for more deterministic extraction
        num_beams=4
    )

    extracted_text = extraction_tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Parse structured output
    memories = parse_extraction_output(extracted_text)

    # Generate embeddings for each memory
    for memory in memories:
        memory['embedding'] = embedding_model.encode(memory['content']).tolist()

    return memories
```

#### Step 2: Semantic Search for Related Memories

```python
def find_related_memories(new_memory: dict, user_id: str,
                         threshold: float = 0.75) -> list[dict]:
    """Find existing memories semantically similar to new memory."""

    conn = duckdb.connect('memory.duckdb')

    # Search using vector similarity
    query = """
        SELECT
            id, topic, content, embedding,
            array_distance(embedding, ?::FLOAT[384]) as distance,
            created_at, updated_at
        FROM memories
        WHERE user_id = ?
          AND topic = ?
          AND is_active = TRUE
        ORDER BY distance ASC
        LIMIT 10
    """

    results = conn.execute(query, [
        new_memory['embedding'],
        user_id,
        new_memory['topic']
    ]).fetchall()

    # Filter by distance threshold (convert to similarity)
    related = []
    for row in results:
        similarity = 1.0 - (row[4] / 2.0)  # distance → similarity
        if similarity >= threshold:
            related.append({
                'id': row[0],
                'topic': row[1],
                'content': row[2],
                'similarity': similarity,
                'created_at': row[5],
                'updated_at': row[6]
            })

    return related
```

#### Step 3: Consolidation

```python
def consolidate_memory(new_memory: dict, related_memories: list[dict],
                      user_id: str) -> dict:
    """Determine action (ADD/UPDATE/DELETE) for new memory."""

    if not related_memories:
        return {'action': 'ADD', 'memory': new_memory}

    # Prepare consolidation prompt
    related_text = "\n".join([
        f"[ID: {m['id']}] {m['content']} (created: {m['created_at']}, similarity: {m['similarity']:.2f})"
        for m in related_memories
    ])

    prompt = f"""Given existing memories and a new fact, decide the appropriate action.

Existing memories:
{related_text}

New fact: {new_memory['content']}
Topic: {new_memory['topic']}

Rules:
1. If new fact is genuinely novel: output "ADD"
2. If new fact updates/contradicts existing memory: output "UPDATE: [memory_id]" with reason
3. If new fact is redundant: output "IGNORE" with reason
4. If new fact asks to forget: output "DELETE: [memory_id]"

Consider:
- Temporal order (newer information may supersede older)
- Semantic similarity (>0.90 = likely duplicate)
- Logical contradictions
- User intent (explicit vs implicit)

Decision:"""

    inputs = consolidation_tokenizer(prompt, return_tensors="pt", max_length=1536, truncation=True)
    outputs = consolidation_model.generate(
        **inputs,
        max_new_tokens=256,
        temperature=0.2,
        num_beams=3
    )

    decision_text = consolidation_tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Parse decision
    action = parse_consolidation_decision(decision_text)

    return action
```

#### Step 4: Apply Actions

```python
def apply_memory_action(action: dict, new_memory: dict, user_id: str):
    """Apply the decided action to the memory store."""

    conn = duckdb.connect('memory.duckdb')

    if action['action'] == 'ADD':
        memory_id = generate_id()
        conn.execute("""
            INSERT INTO memories
            (id, user_id, topic, content, embedding, source_session_id, source_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            memory_id,
            user_id,
            new_memory['topic'],
            new_memory['content'],
            new_memory['embedding'],
            new_memory.get('session_id'),
            new_memory.get('timestamp')
        ])

        # Log change
        conn.execute("""
            INSERT INTO memory_changes (id, memory_id, action, new_content, reason)
            VALUES (?, ?, 'ADD', ?, ?)
        """, [generate_id(), memory_id, new_memory['content'], 'New information'])

    elif action['action'] == 'UPDATE':
        old_memory_id = action['memory_id']

        # Get old content
        old_content = conn.execute(
            "SELECT content FROM memories WHERE id = ?", [old_memory_id]
        ).fetchone()[0]

        # Deactivate old memory
        conn.execute("""
            UPDATE memories
            SET is_active = FALSE
            WHERE id = ?
        """, [old_memory_id])

        # Create new version
        new_memory_id = generate_id()
        conn.execute("""
            INSERT INTO memories
            (id, user_id, topic, content, embedding, supersedes, version)
            VALUES (?, ?, ?, ?, ?, ?, (
                SELECT version + 1 FROM memories WHERE id = ?
            ))
        """, [
            new_memory_id,
            user_id,
            new_memory['topic'],
            new_memory['content'],
            new_memory['embedding'],
            old_memory_id,
            old_memory_id
        ])

        # Record relationship
        conn.execute("""
            INSERT INTO memory_relationships (id, memory_id, related_memory_id, relationship_type)
            VALUES (?, ?, ?, 'supersedes')
        """, [generate_id(), new_memory_id, old_memory_id])

        # Log change
        conn.execute("""
            INSERT INTO memory_changes (id, memory_id, action, old_content, new_content, reason)
            VALUES (?, ?, 'UPDATE', ?, ?, ?)
        """, [generate_id(), new_memory_id, old_content, new_memory['content'], action.get('reason', 'Updated')])

    elif action['action'] == 'DELETE':
        memory_id = action['memory_id']

        # Soft delete
        conn.execute("""
            UPDATE memories
            SET is_active = FALSE
            WHERE id = ?
        """, [memory_id])

        # Log change
        conn.execute("""
            INSERT INTO memory_changes (id, memory_id, action, reason)
            VALUES (?, ?, 'DELETE', ?)
        """, [generate_id(), memory_id, action.get('reason', 'User requested deletion')])

    conn.commit()
    conn.close()
```

### Complete Workflow

```python
def process_session_into_memories(session_id: str, user_id: str,
                                 messages: list[dict]):
    """Complete workflow: extract → search → consolidate → apply."""

    # 1. Extract memories from session
    print(f"Extracting memories from session {session_id}...")
    new_memories = extract_memories_from_session(messages)
    print(f"Extracted {len(new_memories)} potential memories")

    # 2. For each extracted memory, consolidate with existing
    for new_memory in new_memories:
        new_memory['session_id'] = session_id
        new_memory['timestamp'] = get_session_timestamp(messages)

        # Find related memories
        related = find_related_memories(new_memory, user_id)
        print(f"Found {len(related)} related memories for: {new_memory['content'][:50]}...")

        # Decide action
        action = consolidate_memory(new_memory, related, user_id)
        print(f"Decision: {action['action']}")

        # Apply action
        apply_memory_action(action, new_memory, user_id)

    print(f"Memory processing complete for session {session_id}")
```

### Query Interface

```python
def query_memories(user_id: str, query: str, topic: str = None,
                  limit: int = 10) -> list[dict]:
    """Query memories using semantic search."""

    # Generate query embedding
    query_embedding = embedding_model.encode(query).tolist()

    conn = duckdb.connect('memory.duckdb')

    # Build query
    where_clauses = ["user_id = ?", "is_active = TRUE"]
    params = [user_id]

    if topic:
        where_clauses.append("topic = ?")
        params.append(topic)

    where_sql = " AND ".join(where_clauses)

    query_sql = f"""
        SELECT
            id, topic, content,
            array_distance(embedding, ?::FLOAT[384]) as distance,
            created_at, updated_at
        FROM memories
        WHERE {where_sql}
        ORDER BY distance ASC
        LIMIT ?
    """

    results = conn.execute(query_sql, [query_embedding] + params + [limit]).fetchall()

    memories = []
    for row in results:
        memories.append({
            'id': row[0],
            'topic': row[1],
            'content': row[2],
            'relevance': 1.0 - (row[3] / 2.0),  # Convert distance to relevance score
            'created_at': row[4],
            'updated_at': row[5]
        })

    return memories
```

## Performance Optimization

### 1. Model Quantization
Use 8-bit or 4-bit quantization for LLMs:
```python
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_8bit=True,
    llm_int8_threshold=6.0
)

model = AutoModelForCausalLM.from_pretrained(
    "mistralai/Mistral-7B-Instruct-v0.2",
    quantization_config=quantization_config
)
```

### 2. Batch Processing
Process multiple memories in parallel:
```python
# Batch embedding generation
contents = [m['content'] for m in new_memories]
embeddings = embedding_model.encode(contents, batch_size=32, show_progress_bar=True)
for memory, embedding in zip(new_memories, embeddings):
    memory['embedding'] = embedding.tolist()
```

### 3. Caching
Cache recent memory lookups:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_user_memories_cached(user_id: str, topic: str):
    return query_memories(user_id, "", topic=topic, limit=50)
```

## Advanced Features

### 1. Confidence Scoring
Track confidence in each memory:
```python
# During extraction
if any(word in content.lower() for word in ['think', 'maybe', 'probably', 'might']):
    confidence = 0.7
else:
    confidence = 1.0
```

### 2. Memory Decay
Implement time-based relevance decay:
```python
import math
from datetime import datetime, timedelta

def calculate_relevance_with_decay(base_relevance: float, created_at: datetime,
                                   decay_halflife_days: float = 90) -> float:
    """Apply exponential decay to memory relevance."""
    days_old = (datetime.now() - created_at).days
    decay_factor = math.exp(-days_old * math.log(2) / decay_halflife_days)
    return base_relevance * decay_factor
```

### 3. Memory Importance
Classify memory importance:
```python
IMPORTANCE_KEYWORDS = {
    'high': ['critical', 'important', 'never', 'always', 'must', 'emergency'],
    'medium': ['prefer', 'like', 'usually', 'typically'],
    'low': ['sometimes', 'occasionally', 'might']
}

def classify_importance(content: str) -> str:
    content_lower = content.lower()
    for level, keywords in IMPORTANCE_KEYWORDS.items():
        if any(kw in content_lower for kw in keywords):
            return level
    return 'medium'
```

## Comparison: VertexAI vs Open-Source

| Feature | VertexAI Memory Bank | Open-Source Implementation |
|---------|---------------------|----------------------------|
| **Extraction Model** | Gemini 2.5 Flash | Flan-T5-Large / Mistral-7B |
| **Embedding Model** | Proprietary | Sentence-Transformers |
| **Vector Store** | Vertex AI Vector Search | DuckDB with VSS extension |
| **Consolidation** | Gemini-based | Flan-T5 / Mistral |
| **Cost** | Pay per API call | Free (self-hosted) |
| **Latency** | API latency (~500ms) | Local inference (~100-500ms) |
| **Scalability** | Cloud-scale | Limited by hardware |
| **Customization** | Limited to topics | Full control |
| **Privacy** | Data sent to Google | Fully local |

## References

- [Vertex AI Memory Bank Overview](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview)
- [Generate Memories - Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/generate-memories)
- [Mem0 - Memory for AI Agents](https://mem0.ai/)
- [LangMem - Memory System for LLMs](https://langchain-ai.github.io/langmem/)
- [Flan-T5 on HuggingFace](https://huggingface.co/docs/transformers/model_doc/flan-t5)
- [MiniCheck-Flan-T5 for Fact Checking](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large)

## Next Steps for CLEM Integration

To integrate this memory extraction system into CLEM:

1. **Add Memory Extraction Module**
   - Create `memory_extraction.py` in `.claude/scripts/clem/`
   - Implement extraction using Flan-T5-large
   - Add CLI command: `clem memory extract --session [id]`

2. **Extend DuckDB Schema**
   - Add `memories` table with the schema above
   - Implement consolidation logic
   - Add memory query interface

3. **Create Memory Dashboard**
   - View all extracted memories by topic
   - Track memory evolution over time
   - Visualize memory relationships

4. **Integrate with Session Processing**
   - Auto-extract memories after each session
   - Provide memory context to new sessions
   - Enable agents to query user preferences

This would make CLEM a complete conversational memory system with both semantic search and structured memory extraction capabilities.
