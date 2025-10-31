#!/usr/bin/env python
"""Claude Code Meta Learning Memory Script - aka CLEM

Query and analyze Claude Code conversation history across projects and sessions.
"""
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.1.3",
#   "rich>=13.9.4",
#   "sentence-transformers>=3.0.0",
#   "numpy>=1.24.0",
#   "transformers>=4.30.0",
#   "torch>=2.0.0",
# ]
# ///

import argparse
import json as json_module
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from shlex import split
from textwrap import dedent

import duckdb
import numpy as np
from rich.console import Console
from rich.table import Table

log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

# Claude logs location
CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_PROJECTS_DIR = CLAUDE_DIR / "projects"

# Git helpers
_run = lambda cmd: subprocess.check_output(split(cmd), text=True).strip()  # noqa: E731

try:
    GIT_ROOT = Path(_run("git rev-parse --show-toplevel"))
    CURRENT_PROJECT = str(GIT_ROOT)
except subprocess.CalledProcessError:
    CURRENT_PROJECT = str(Path.cwd())
    log.warning("Not in a git repository, using current directory as project")

# Rich console for pretty output
console = Console()

# Embedding model (lazy loaded)
_embedding_model = None

# ============================================================================
# Vector Search & Database Management
# ============================================================================


def get_database_path(project_path: str | None = None) -> Path:
    """Get the DuckDB database path based on scope.

    Args:
        project_path: If provided, returns project-specific DB path.
                     If None, returns global DB path.

    Returns:
        Path to the DuckDB database file
    """
    if project_path:
        # Project-specific database: PROJECT_DIR/.claude/clem.duckdb
        project_root = Path(project_path)
        db_path = project_root / ".claude" / "clem.duckdb"
        db_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Global database: ~/.claude/clem.duckdb
        db_path = CLAUDE_DIR / "clem.duckdb"
        db_path.parent.mkdir(parents=True, exist_ok=True)

    return db_path


def get_embedding_model():
    """Get or initialize the embedding model (lazy loading)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Use a lightweight but effective model
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            log.info("Loaded embedding model: all-MiniLM-L6-v2")
        except Exception as e:
            log.error(f"Failed to load embedding model: {e}")
            return None
    return _embedding_model


def init_vector_db(db_path: Path):
    """Initialize the vector database with required schema.

    Creates a table with message content and vector embeddings.
    """
    conn = duckdb.connect(str(db_path))

    try:
        # Install and load the VSS extension for vector similarity search
        conn.execute("INSTALL vss")
        conn.execute("LOAD vss")
    except Exception as e:
        log.warning(f"Could not load VSS extension: {e}")

    # Create messages table with vector embeddings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR PRIMARY KEY,
            project VARCHAR,
            session_id VARCHAR,
            timestamp BIGINT,
            role VARCHAR,
            content VARCHAR,
            embedding FLOAT[384],  -- all-MiniLM-L6-v2 produces 384-dim embeddings
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index on project and session for faster filtering
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project ON messages(project)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session ON messages(project, session_id)
    """)

    conn.close()
    log.info(f"Initialized vector database at {db_path}")


def generate_embedding(text: str) -> list[float] | None:
    """Generate vector embedding for text content.

    Args:
        text: Text content to embed

    Returns:
        384-dimensional embedding vector, or None if model unavailable
    """
    model = get_embedding_model()
    if model is None:
        return None

    try:
        # Handle different content types (string or list of dicts)
        if isinstance(text, list):
            # Extract text from content array
            text_parts = []
            for item in text:
                if isinstance(item, dict) and 'text' in item:
                    text_parts.append(item['text'])
                elif isinstance(item, dict) and 'type' in item:
                    # Skip non-text content types
                    continue
            text = " ".join(text_parts)

        # Generate embedding
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        log.debug(f"Failed to generate embedding: {e}")
        return None


def index_messages(project_path: str | None = None, session_id: str | None = None):
    """Index messages with vector embeddings for similarity search.

    Args:
        project_path: If provided, only index messages from this project
        session_id: If provided (with project_path), only index this session
    """
    db_path = get_database_path(project_path)
    init_vector_db(db_path)

    conn = duckdb.connect(str(db_path))

    # Determine which sessions to index
    if session_id and project_path:
        # Single session
        project_dir_name = project_path.replace("/", "-")
        if not project_dir_name.startswith("-"):
            project_dir_name = "-" + project_dir_name
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
        session_file = project_dir / f"{session_id}.jsonl"
        session_files = [session_file] if session_file.exists() else []
    elif project_path:
        # All sessions in project
        project_dir_name = project_path.replace("/", "-")
        if not project_dir_name.startswith("-"):
            project_dir_name = "-" + project_dir_name
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
        if project_dir.exists():
            session_files = [f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")]
        else:
            session_files = []
    else:
        # All sessions across all projects
        session_files = []
        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                session_files.extend([f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")])

    console.print(f"[cyan]Indexing {len(session_files)} session files...[/cyan]")
    indexed_count = 0

    for session_file in session_files:
        # Derive metadata from file path
        project_dir_name = session_file.parent.name
        file_project_path = "/" + project_dir_name.lstrip("-").replace("-", "/")
        file_session_id = session_file.stem

        try:
            # Read messages from JSONL file
            with open(session_file, 'r') as f:
                for line_num, line in enumerate(f):
                    try:
                        data = json_module.loads(line)
                        if 'message' not in data:
                            continue

                        message = data['message']
                        content = message.get('content', '')
                        role = message.get('role', 'unknown')
                        timestamp_str = data.get('timestamp', '')

                        # Parse timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            timestamp_ms = int(dt.timestamp() * 1000)
                        except:
                            timestamp_ms = 0

                        # Generate message ID
                        msg_id = f"{file_project_path}:{file_session_id}:{line_num}"

                        # Check if already indexed
                        existing = conn.execute(
                            "SELECT id FROM messages WHERE id = ?", [msg_id]
                        ).fetchone()

                        if existing:
                            continue

                        # Generate embedding
                        embedding = generate_embedding(content)
                        if embedding is None:
                            continue

                        # Insert into database
                        conn.execute("""
                            INSERT INTO messages (id, project, session_id, timestamp, role, content, embedding)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, [msg_id, file_project_path, file_session_id, timestamp_ms, role, str(content)[:1000], embedding])

                        indexed_count += 1

                    except Exception as e:
                        log.debug(f"Failed to index line {line_num} in {session_file}: {e}")
                        continue

        except Exception as e:
            log.debug(f"Failed to process {session_file}: {e}")
            continue

    conn.close()
    console.print(f"[green]✓ Indexed {indexed_count} messages in {db_path}[/green]")


def semantic_search(query: str, project_path: str | None = None,
                   session_id: str | None = None, limit: int = 10) -> list[dict]:
    """Search messages using semantic similarity.

    Args:
        query: Search query text
        project_path: Optional project to filter by
        session_id: Optional session to filter by (requires project_path)
        limit: Maximum number of results

    Returns:
        List of matching messages with similarity scores
    """
    db_path = get_database_path(project_path)

    if not db_path.exists():
        console.print(f"[yellow]Database not found at {db_path}. Run 'index' command first.[/yellow]")
        return []

    # Generate query embedding
    query_embedding = generate_embedding(query)
    if query_embedding is None:
        console.print("[yellow]Could not generate query embedding[/yellow]")
        return []

    conn = duckdb.connect(str(db_path))

    # Build WHERE clause for filtering
    where_clauses = []
    params = []

    if session_id and project_path:
        where_clauses.append("project = ? AND session_id = ?")
        params.extend([project_path, session_id])
    elif project_path:
        where_clauses.append("project = ?")
        params.append(project_path)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Query using array distance function
    # Lower distance = more similar
    query_sql = f"""
        SELECT
            project,
            session_id,
            timestamp,
            role,
            content,
            array_distance(embedding, ?::FLOAT[384]) as distance
        FROM messages
        {where_sql}
        ORDER BY distance ASC
        LIMIT ?
    """

    try:
        results = conn.execute(query_sql, [query_embedding] + params + [limit]).fetchall()
    except Exception as e:
        log.error(f"Semantic search failed: {e}")
        conn.close()
        return []

    conn.close()

    # Format results
    matches = []
    for row in results:
        matches.append({
            "project": row[0],
            "session_id": row[1],
            "timestamp": row[2],
            "role": row[3],
            "preview": row[4][:200] if row[4] else "",
            "similarity": 1.0 - (row[5] / 2.0)  # Convert distance to similarity score (0-1)
        })

    return matches


# ============================================================================
# Memory Extraction & Consolidation
# ============================================================================

# Lazy-loaded models for memory extraction
_extraction_model = None
_extraction_tokenizer = None

MEMORY_TOPICS = {
    "personal_info": "Personal information about the user (names, relationships, profession, dates)",
    "preferences": "User preferences, likes, dislikes, styles, patterns",
    "key_decisions": "Important decisions, conclusions, or outcomes",
    "explicit_instructions": "Things user explicitly asked to remember or forget"
}


def get_extraction_model():
    """Get or initialize the extraction model (lazy loading)."""
    global _extraction_model, _extraction_tokenizer
    if _extraction_model is None:
        try:
            from transformers import T5ForConditionalGeneration, T5Tokenizer
            console.print("[cyan]Loading memory extraction model (Flan-T5)...[/cyan]")
            _extraction_model = T5ForConditionalGeneration.from_pretrained(
                "google/flan-t5-base"  # Using base for speed, can upgrade to large/xl
            )
            _extraction_tokenizer = T5Tokenizer.from_pretrained("google/flan-t5-base")
            console.print("[green]✓ Extraction model loaded[/green]")
        except Exception as e:
            log.error(f"Failed to load extraction model: {e}")
            return None, None
    return _extraction_model, _extraction_tokenizer


def init_memory_db(db_path: Path):
    """Initialize memory database schema."""
    conn = duckdb.connect(str(db_path))

    # Main memories table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL DEFAULT 'default',
            topic VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding FLOAT[384],
            confidence FLOAT DEFAULT 1.0,
            source_session_id VARCHAR,
            source_timestamp BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            supersedes VARCHAR,
            is_active BOOLEAN DEFAULT TRUE,
            version INTEGER DEFAULT 1
        )
    """)

    # Memory relationships table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_relationships (
            id VARCHAR PRIMARY KEY,
            memory_id VARCHAR NOT NULL,
            related_memory_id VARCHAR NOT NULL,
            relationship_type VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Memory changes audit trail
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_changes (
            id VARCHAR PRIMARY KEY,
            memory_id VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            old_content TEXT,
            new_content TEXT,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_topic ON memories(user_id, topic, is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_session ON memories(source_session_id)")

    conn.close()
    log.info(f"Initialized memory database at {db_path}")


def extract_memories_from_session(session_messages: list[dict], session_id: str) -> list[dict]:
    """Extract structured memories from conversation messages.

    Args:
        session_messages: List of message dicts with 'role' and 'content'
        session_id: Session identifier

    Returns:
        List of extracted memory dicts with topic, content, embedding
    """
    model, tokenizer = get_extraction_model()
    if model is None or tokenizer is None:
        console.print("[yellow]Extraction model not available[/yellow]")
        return []

    # Format messages for extraction
    conversation_text = "\n".join([
        f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:500]}"
        for msg in session_messages[-20:]  # Last 20 messages
    ])

    # Extraction prompt
    prompt = f"""Extract key information from this conversation and categorize each fact:

Topics:
1. personal_info: Names, relationships, profession, important dates, location
2. preferences: Likes, dislikes, preferred styles, patterns, behaviors
3. key_decisions: Important conclusions, decisions, outcomes, milestones
4. explicit_instructions: Things user explicitly asked to remember or forget

Conversation:
{conversation_text}

List each fact in format: [topic] fact content
Extract facts:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", max_length=1024, truncation=True)
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.3,
            num_beams=4
        )
        extracted_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Parse extraction output
        memories = []
        for line in extracted_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('[') is False:
                continue

            # Parse format: [topic] content
            try:
                if ']' in line:
                    topic_end = line.index(']')
                    topic = line[1:topic_end].strip()
                    content = line[topic_end+1:].strip()

                    if topic in MEMORY_TOPICS and content:
                        # Generate embedding
                        embedding = generate_embedding(content)
                        if embedding:
                            memories.append({
                                'topic': topic,
                                'content': content,
                                'embedding': embedding,
                                'confidence': 1.0,
                                'session_id': session_id
                            })
            except Exception as e:
                log.debug(f"Failed to parse memory line: {line}, error: {e}")
                continue

        return memories

    except Exception as e:
        log.error(f"Memory extraction failed: {e}")
        return []


def find_related_memories(new_memory: dict, user_id: str, db_path: Path,
                         threshold: float = 0.75) -> list[dict]:
    """Find existing memories semantically similar to new memory."""
    if not db_path.exists():
        return []

    conn = duckdb.connect(str(db_path))

    try:
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

        related = []
        for row in results:
            similarity = 1.0 - (row[4] / 2.0)
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

    except Exception as e:
        log.error(f"Failed to find related memories: {e}")
        return []
    finally:
        conn.close()


def consolidate_memory(new_memory: dict, related_memories: list[dict]) -> dict:
    """Determine action (ADD/UPDATE/IGNORE) for new memory.

    Uses simple heuristics for now. Can be enhanced with LLM consolidation.
    """
    if not related_memories:
        return {'action': 'ADD', 'memory': new_memory}

    # Check for very high similarity (likely duplicate)
    for related in related_memories:
        if related['similarity'] > 0.90:
            return {
                'action': 'IGNORE',
                'reason': f"Very similar to existing memory (similarity: {related['similarity']:.2f})"
            }

    # Check for high similarity but different content (potential update)
    for related in related_memories:
        if related['similarity'] > 0.75:
            # Simple check: if content differs significantly, suggest update
            if len(new_memory['content']) > len(related['content']) * 1.2:
                return {
                    'action': 'UPDATE',
                    'memory_id': related['id'],
                    'memory': new_memory,
                    'reason': f"More detailed version of existing memory"
                }

    # Default: add as new memory
    return {'action': 'ADD', 'memory': new_memory}


def apply_memory_action(action: dict, user_id: str, db_path: Path):
    """Apply the consolidation action to memory store."""
    import uuid

    conn = duckdb.connect(str(db_path))

    try:
        if action['action'] == 'ADD':
            memory = action['memory']
            memory_id = str(uuid.uuid4())

            conn.execute("""
                INSERT INTO memories
                (id, user_id, topic, content, embedding, confidence, source_session_id, source_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                memory_id,
                user_id,
                memory['topic'],
                memory['content'],
                memory['embedding'],
                memory.get('confidence', 1.0),
                memory.get('session_id'),
                memory.get('timestamp', 0)
            ])

            # Log change
            change_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO memory_changes (id, memory_id, action, new_content, reason)
                VALUES (?, ?, 'ADD', ?, ?)
            """, [change_id, memory_id, memory['content'], 'New memory extracted'])

            console.print(f"[green]✓ Added memory: {memory['content'][:60]}...[/green]")

        elif action['action'] == 'UPDATE':
            old_memory_id = action['memory_id']
            memory = action['memory']

            # Get old content
            old_content = conn.execute(
                "SELECT content FROM memories WHERE id = ?", [old_memory_id]
            ).fetchone()[0]

            # Deactivate old
            conn.execute("UPDATE memories SET is_active = FALSE WHERE id = ?", [old_memory_id])

            # Create new version
            new_memory_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO memories
                (id, user_id, topic, content, embedding, supersedes, version, source_session_id)
                SELECT ?, ?, ?, ?, ?, ?, version + 1, ?
                FROM memories WHERE id = ?
            """, [
                new_memory_id,
                user_id,
                memory['topic'],
                memory['content'],
                memory['embedding'],
                old_memory_id,
                memory.get('session_id'),
                old_memory_id
            ])

            # Record relationship
            rel_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO memory_relationships (id, memory_id, related_memory_id, relationship_type)
                VALUES (?, ?, ?, 'supersedes')
            """, [rel_id, new_memory_id, old_memory_id])

            # Log change
            change_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO memory_changes (id, memory_id, action, old_content, new_content, reason)
                VALUES (?, ?, 'UPDATE', ?, ?, ?)
            """, [change_id, new_memory_id, old_content, memory['content'], action.get('reason', 'Updated')])

            console.print(f"[yellow]⟳ Updated memory: {memory['content'][:60]}...[/yellow]")

        elif action['action'] == 'IGNORE':
            console.print(f"[dim]- Ignored (duplicate): {action.get('reason', 'N/A')}[/dim]")

        conn.commit()

    except Exception as e:
        log.error(f"Failed to apply memory action: {e}")
    finally:
        conn.close()


def process_session_memories(session_id: str, project_path: str | None = None, user_id: str = "default"):
    """Extract and consolidate memories from a session."""
    # Get database path
    db_path = get_database_path(project_path)
    init_memory_db(db_path)

    # Load session messages
    if project_path:
        project_dir_name = project_path.replace("/", "-")
        if not project_dir_name.startswith("-"):
            project_dir_name = "-" + project_dir_name
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
    else:
        # Find session across all projects
        project_dir = None
        for pdir in CLAUDE_PROJECTS_DIR.iterdir():
            if pdir.is_dir() and (pdir / f"{session_id}.jsonl").exists():
                project_dir = pdir
                break
        if not project_dir:
            console.print(f"[red]Session {session_id} not found[/red]")
            return

    session_file = project_dir / f"{session_id}.jsonl"
    if not session_file.exists():
        console.print(f"[red]Session file not found: {session_file}[/red]")
        return

    # Load messages
    messages = []
    with open(session_file, 'r') as f:
        for line in f:
            try:
                data = json_module.loads(line)
                if 'message' in data:
                    messages.append(data['message'])
            except:
                continue

    console.print(f"[cyan]Extracting memories from {len(messages)} messages...[/cyan]")

    # Extract memories
    new_memories = extract_memories_from_session(messages, session_id)
    console.print(f"[cyan]Extracted {len(new_memories)} potential memories[/cyan]")

    # Consolidate each memory
    added_count = 0
    updated_count = 0
    ignored_count = 0

    for memory in new_memories:
        related = find_related_memories(memory, user_id, db_path)
        action = consolidate_memory(memory, related)
        apply_memory_action(action, user_id, db_path)

        if action['action'] == 'ADD':
            added_count += 1
        elif action['action'] == 'UPDATE':
            updated_count += 1
        else:
            ignored_count += 1

    console.print(f"\n[bold]Memory Extraction Complete:[/bold]")
    console.print(f"  Added: {added_count}")
    console.print(f"  Updated: {updated_count}")
    console.print(f"  Ignored: {ignored_count}")


def query_memories(user_id: str, query: str = "", topic: str | None = None,
                  project_path: str | None = None, limit: int = 20) -> list[dict]:
    """Query memories using semantic search."""
    db_path = get_database_path(project_path)

    if not db_path.exists():
        console.print(f"[yellow]Memory database not found. Run 'memory extract' first.[/yellow]")
        return []

    conn = duckdb.connect(str(db_path))

    try:
        if query:
            # Semantic search
            query_embedding = generate_embedding(query)
            if query_embedding is None:
                return []

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
                    created_at, updated_at, confidence
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
                    'relevance': 1.0 - (row[3] / 2.0),
                    'created_at': row[4],
                    'updated_at': row[5],
                    'confidence': row[6]
                })

            return memories

        else:
            # List all memories
            where_clauses = ["user_id = ?", "is_active = TRUE"]
            params = [user_id]

            if topic:
                where_clauses.append("topic = ?")
                params.append(topic)

            where_sql = " AND ".join(where_clauses)

            query_sql = f"""
                SELECT id, topic, content, created_at, updated_at, confidence
                FROM memories
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
            """

            results = conn.execute(query_sql, params + [limit]).fetchall()

            memories = []
            for row in results:
                memories.append({
                    'id': row[0],
                    'topic': row[1],
                    'content': row[2],
                    'created_at': row[3],
                    'updated_at': row[4],
                    'confidence': row[5]
                })

            return memories

    except Exception as e:
        log.error(f"Memory query failed: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# Core Query Functions
# ============================================================================


def get_current_session_id() -> str | None:
    """Get the current session ID from the most recent JSONL file in the current project."""
    project_dir = CLAUDE_PROJECTS_DIR / CURRENT_PROJECT.replace("/", "-")

    if not project_dir.exists():
        log.warning(f"Project directory not found: {project_dir}")
        return None

    # Find most recently modified session file (exclude agent-*.jsonl files)
    session_files = [f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")]

    if not session_files:
        log.warning(f"No session files found in {project_dir}")
        return None

    most_recent = max(session_files, key=lambda f: f.stat().st_mtime)
    return most_recent.stem


def execute_query(query: str) -> list[tuple]:
    """Execute a DuckDB query and return results."""
    conn = duckdb.connect()
    try:
        result = conn.execute(query).fetchall()
        return result
    finally:
        conn.close()


def get_all_projects() -> list[dict]:
    """List all projects with their session counts and activity."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    projects = []

    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir() or project_dir.name.startswith('.'):
            continue

        # Count session files (exclude agent-*.jsonl files)
        session_files = [f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")]

        if not session_files:
            continue

        # Get project path from directory name (reverse the encoding)
        # Remove leading dash and replace remaining dashes with slashes
        project_path = "/" + project_dir.name.lstrip("-").replace("-", "/")

        # Get timestamps from file metadata
        file_mtimes = [f.stat().st_mtime for f in session_files]
        last_activity = int(max(file_mtimes) * 1000) if file_mtimes else None
        first_activity = int(min([f.stat().st_ctime for f in session_files]) * 1000) if session_files else None

        # Count total messages across all session files
        total_messages = 0
        for session_file in session_files:
            try:
                query = f"SELECT COUNT(*) FROM read_ndjson_auto('{session_file}')"
                result = execute_query(query)
                if result and result[0]:
                    total_messages += result[0][0]
            except Exception as e:
                log.debug(f"Skipping {session_file}: {e}")
                continue

        projects.append({
            "project": project_path,
            "sessions": len(session_files),
            "messages": total_messages,
            "last_activity": last_activity,
            "first_activity": first_activity,
        })

    # Sort by last activity
    projects.sort(key=lambda p: p["last_activity"] or 0, reverse=True)

    return projects


def get_sessions_by_project(project_path: str) -> list[dict]:
    """List all sessions for a specific project."""
    # Convert project path to directory name (add leading dash, replace slashes with dashes)
    project_dir_name = project_path.replace("/", "-")
    if not project_dir_name.startswith("-"):
        project_dir_name = "-" + project_dir_name
    project_dir = CLAUDE_PROJECTS_DIR / project_dir_name

    if not project_dir.exists():
        log.warning(f"Project directory not found: {project_dir}")
        return []

    # Get all session files (exclude agent-*.jsonl)
    session_files = [f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")]

    sessions = []
    for session_file in session_files:
        session_id = session_file.stem

        try:
            # Query this specific session file
            query = f"""
            SELECT
                COUNT(*) as messages,
                SUM(CASE WHEN message.usage.input_tokens IS NOT NULL
                    THEN message.usage.input_tokens ELSE 0 END) as input_tokens,
                SUM(CASE WHEN message.usage.output_tokens IS NOT NULL
                    THEN message.usage.output_tokens ELSE 0 END) as output_tokens
            FROM read_ndjson_auto('{session_file}')
            """

            result = execute_query(query)

            if result and result[0]:
                messages = result[0][0] if result[0][0] else 0
                input_tokens = result[0][1] if result[0][1] else 0
                output_tokens = result[0][2] if result[0][2] else 0
            else:
                messages = 0
                input_tokens = 0
                output_tokens = 0
        except Exception as e:
            log.debug(f"Skipping {session_file}: {e}")
            continue

        # Get timestamps from file metadata
        file_stat = session_file.stat()
        started = int(file_stat.st_ctime * 1000)
        last_activity = int(file_stat.st_mtime * 1000)

        sessions.append({
            "session_id": session_id,
            "messages": messages,
            "started": started,
            "last_activity": last_activity,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })

    # Sort by last activity
    sessions.sort(key=lambda s: s["last_activity"], reverse=True)

    return sessions


def get_summary_stats(scope: str, project_path: str | None = None, session_id: str | None = None) -> dict:
    """Get summary statistics for different scopes."""
    # Determine which files to query based on scope
    session_files = []

    if session_id and project_path:
        # Single session
        project_dir_name = project_path.replace("/", "-")
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
        session_file = project_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session_files = [session_file]
    elif project_path:
        # All sessions in a project
        project_dir_name = project_path.replace("/", "-")
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
        if project_dir.exists():
            session_files = [f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")]
    else:
        # All sessions across all projects
        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                session_files.extend([f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")])

    if not session_files:
        return {
            "scope": scope,
            "projects": 0,
            "sessions": 0,
            "total_messages": 0,
            "user_messages": 0,
            "assistant_messages": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "first_activity": None,
            "last_activity": None,
        }

    # Aggregate stats across all relevant files
    total_messages = 0
    user_messages = 0
    assistant_messages = 0
    total_input_tokens = 0
    total_output_tokens = 0
    first_activity = None
    last_activity = None

    # Track unique projects
    unique_projects = set()

    for session_file in session_files:
        # Track project
        unique_projects.add(session_file.parent.name)

        try:
            # Query this session file
            query = f"""
            SELECT
                COUNT(*) as messages,
                SUM(CASE WHEN message.role = 'user' THEN 1 ELSE 0 END) as user_msgs,
                SUM(CASE WHEN message.role = 'assistant' THEN 1 ELSE 0 END) as assistant_msgs,
                SUM(CASE WHEN message.usage.input_tokens IS NOT NULL
                    THEN message.usage.input_tokens ELSE 0 END) as input_tokens,
                SUM(CASE WHEN message.usage.output_tokens IS NOT NULL
                    THEN message.usage.output_tokens ELSE 0 END) as output_tokens
            FROM read_ndjson_auto('{session_file}')
            """

            result = execute_query(query)

            if result and result[0]:
                total_messages += result[0][0] if result[0][0] else 0
                user_messages += result[0][1] if result[0][1] else 0
                assistant_messages += result[0][2] if result[0][2] else 0
                total_input_tokens += result[0][3] if result[0][3] else 0
                total_output_tokens += result[0][4] if result[0][4] else 0
        except Exception as e:
            # Skip files that don't match expected schema
            log.debug(f"Skipping {session_file}: {e}")
            continue

        # Update timestamps from file metadata
        file_stat = session_file.stat()
        file_ctime = int(file_stat.st_ctime * 1000)
        file_mtime = int(file_stat.st_mtime * 1000)

        if first_activity is None or file_ctime < first_activity:
            first_activity = file_ctime
        if last_activity is None or file_mtime > last_activity:
            last_activity = file_mtime

    return {
        "scope": scope,
        "projects": len(unique_projects),
        "sessions": len(session_files),
        "total_messages": total_messages,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "first_activity": first_activity,
        "last_activity": last_activity,
    }


def search_conversations(search_term: str, project_path: str | None = None,
                        session_id: str | None = None, limit: int = 20) -> list[dict]:
    """Search for a term across conversations."""
    # Determine which files to search based on scope
    session_files = []

    if session_id and project_path:
        # Single session
        project_dir_name = project_path.replace("/", "-")
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
        session_file = project_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session_files = [session_file]
    elif project_path:
        # All sessions in a project
        project_dir_name = project_path.replace("/", "-")
        project_dir = CLAUDE_PROJECTS_DIR / project_dir_name
        if project_dir.exists():
            session_files = [f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")]
    else:
        # All sessions across all projects
        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                session_files.extend([f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")])

    matches = []

    for session_file in session_files:
        # Derive project path from directory name
        project_dir_name = session_file.parent.name
        file_project_path = "/" + project_dir_name.lstrip("-").replace("-", "/")
        file_session_id = session_file.stem

        # Query this session file for matches
        query = f"""
        SELECT
            timestamp,
            message.role,
            substring(CAST(message.content AS VARCHAR), 1, 200) as preview
        FROM read_ndjson_auto('{session_file}')
        WHERE CAST(message.content AS VARCHAR) LIKE '%{search_term}%'
        ORDER BY timestamp DESC
        LIMIT {limit}
        """

        try:
            results = execute_query(query)
        except Exception as e:
            # Skip files that don't have the expected structure or are empty
            log.debug(f"Skipping {session_file}: {e}")
            continue

        for row in results:
            # Convert ISO timestamp to milliseconds
            timestamp = row[0]
            if timestamp and isinstance(timestamp, str):
                try:
                    # Parse ISO format and convert to milliseconds
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp_ms = int(dt.timestamp() * 1000)
                except (ValueError, AttributeError):
                    timestamp_ms = None
            else:
                timestamp_ms = timestamp

            matches.append({
                "project": file_project_path,
                "session_id": file_session_id,
                "timestamp": timestamp_ms,
                "role": row[1],
                "preview": row[2],
            })

            # Stop if we've reached the limit
            if len(matches) >= limit:
                break

        if len(matches) >= limit:
            break

    # Sort all matches by timestamp (already should be sorted, but ensure it)
    # Note: timestamps might be strings, need to handle that
    matches.sort(key=lambda m: m["timestamp"] if m["timestamp"] else "", reverse=True)

    return matches[:limit]


# ============================================================================
# Display Functions
# ============================================================================


def format_timestamp(ts: int | str | None) -> str:
    """Convert unix timestamp (ms) to readable format."""
    if ts is None:
        return "N/A"
    # Handle string timestamps from DuckDB
    if isinstance(ts, str):
        try:
            ts = int(ts)
        except (ValueError, TypeError):
            return "N/A"
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def format_number(num: int | float) -> str:
    """Format large numbers with commas."""
    if num is None:
        return "0"
    return f"{num:,}"


def display_projects(projects: list[dict]):
    """Display projects in a rich table."""
    table = Table(title="Claude Code Projects", show_header=True, header_style="bold magenta")

    table.add_column("Project", style="cyan", no_wrap=False)
    table.add_column("Sessions", justify="right", style="green")
    table.add_column("Messages", justify="right", style="yellow")
    table.add_column("Last Activity", style="blue")

    for proj in projects:
        project_name = Path(proj["project"]).name if proj["project"] else "Unknown"
        table.add_row(
            project_name,
            str(proj["sessions"]),
            format_number(proj["messages"]),
            format_timestamp(proj["last_activity"]),
        )

    console.print(table)


def display_sessions(sessions: list[dict], project_name: str):
    """Display sessions in a rich table."""
    table = Table(title=f"Sessions for {project_name}", show_header=True, header_style="bold magenta")

    table.add_column("Session ID", style="cyan", no_wrap=True)
    table.add_column("Messages", justify="right", style="green")
    table.add_column("Input Tokens", justify="right", style="yellow")
    table.add_column("Output Tokens", justify="right", style="yellow")
    table.add_column("Started", style="blue")
    table.add_column("Last Activity", style="blue")

    for sess in sessions:
        session_id = str(sess["session_id"]) if sess["session_id"] else "N/A"
        session_short = session_id[:8] if session_id != "N/A" else "N/A"
        table.add_row(
            session_short,
            str(sess["messages"]),
            format_number(sess["input_tokens"]),
            format_number(sess["output_tokens"]),
            format_timestamp(sess["started"]),
            format_timestamp(sess["last_activity"]),
        )

    console.print(table)


def display_stats(stats: dict):
    """Display summary statistics."""
    table = Table(title=f"Summary Statistics: {stats.get('scope', 'Unknown')}",
                  show_header=True, header_style="bold magenta")

    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Projects", format_number(stats.get("projects", 0)))
    table.add_row("Sessions", format_number(stats.get("sessions", 0)))
    table.add_row("Total Messages", format_number(stats.get("total_messages", 0)))
    table.add_row("User Messages", format_number(stats.get("user_messages", 0)))
    table.add_row("Assistant Messages", format_number(stats.get("assistant_messages", 0)))
    table.add_row("Total Input Tokens", format_number(stats.get("total_input_tokens", 0)))
    table.add_row("Total Output Tokens", format_number(stats.get("total_output_tokens", 0)))
    table.add_row("First Activity", format_timestamp(stats.get("first_activity")))
    table.add_row("Last Activity", format_timestamp(stats.get("last_activity")))

    console.print(table)


def display_search_results(matches: list[dict], search_term: str):
    """Display search results in a rich table."""
    table = Table(title=f"Search Results for '{search_term}'", show_header=True, header_style="bold magenta")

    table.add_column("Project", style="cyan", no_wrap=False, max_width=30)
    table.add_column("Session", style="yellow", no_wrap=True, max_width=10)
    table.add_column("Role", style="green", max_width=10)
    table.add_column("Timestamp", style="blue", max_width=20)
    table.add_column("Preview", style="white", no_wrap=False)

    for match in matches:
        project_name = Path(match["project"]).name if match["project"] else "Unknown"
        session_id = str(match["session_id"]) if match["session_id"] else "N/A"
        session_short = session_id[:8] if session_id != "N/A" else "N/A"

        table.add_row(
            project_name,
            session_short,
            match["role"],
            format_timestamp(match["timestamp"]),
            match["preview"],
        )

    console.print(table)


# ============================================================================
# Main Commands
# ============================================================================


def cmd_list_projects():
    """List all projects."""
    projects = get_all_projects()
    display_projects(projects)
    console.print(f"\n[bold]Total: {len(projects)} projects[/bold]")


def cmd_list_sessions(project_path: str | None = None):
    """List sessions for a project."""
    if not project_path:
        project_path = CURRENT_PROJECT

    sessions = get_sessions_by_project(project_path)
    project_name = Path(project_path).name
    display_sessions(sessions, project_name)
    console.print(f"\n[bold]Total: {len(sessions)} sessions[/bold]")


def cmd_stats_all():
    """Show statistics for all projects and sessions."""
    stats = get_summary_stats("All Projects / All Sessions")
    display_stats(stats)


def cmd_stats_current_project():
    """Show statistics for current project, all sessions."""
    stats = get_summary_stats("Current Project / All Sessions", project_path=CURRENT_PROJECT)
    display_stats(stats)
    console.print(f"\n[dim]Project: {CURRENT_PROJECT}[/dim]")


def cmd_stats_current_session():
    """Show statistics for current project, current session."""
    session_id = get_current_session_id()

    if not session_id:
        console.print("[red]Could not determine current session ID[/red]")
        return

    stats = get_summary_stats("Current Project / Current Session",
                             project_path=CURRENT_PROJECT,
                             session_id=session_id)
    display_stats(stats)
    console.print(f"\n[dim]Project: {CURRENT_PROJECT}[/dim]")
    console.print(f"[dim]Session: {session_id}[/dim]")


def cmd_search(search_term: str, scope: str = "all", limit: int = 20):
    """Search conversations."""
    project_path = None
    session_id = None

    if scope == "project":
        project_path = CURRENT_PROJECT
    elif scope == "session":
        project_path = CURRENT_PROJECT
        session_id = get_current_session_id()
        if not session_id:
            console.print("[red]Could not determine current session ID[/red]")
            return

    matches = search_conversations(search_term, project_path, session_id, limit)
    display_search_results(matches, search_term)
    console.print(f"\n[bold]Found: {len(matches)} matches[/bold]")


def cmd_index(scope: str = "project"):
    """Index messages for semantic search."""
    project_path = None
    session_id = None

    if scope == "project":
        project_path = CURRENT_PROJECT
        console.print(f"[cyan]Indexing project: {project_path}[/cyan]")
    elif scope == "session":
        project_path = CURRENT_PROJECT
        session_id = get_current_session_id()
        if not session_id:
            console.print("[red]Could not determine current session ID[/red]")
            return
        console.print(f"[cyan]Indexing session: {session_id}[/cyan]")
    else:
        console.print("[cyan]Indexing all projects...[/cyan]")

    index_messages(project_path, session_id)


def cmd_semantic_search(query: str, scope: str = "all", limit: int = 10):
    """Semantic similarity search."""
    project_path = None
    session_id = None

    if scope == "project":
        project_path = CURRENT_PROJECT
    elif scope == "session":
        project_path = CURRENT_PROJECT
        session_id = get_current_session_id()
        if not session_id:
            console.print("[red]Could not determine current session ID[/red]")
            return

    matches = semantic_search(query, project_path, session_id, limit)

    # Display results in a table
    table = Table(title=f"Semantic Search Results for '{query}'")
    table.add_column("Project", style="cyan")
    table.add_column("Session", style="magenta")
    table.add_column("Role", style="green")
    table.add_column("Timestamp", style="yellow")
    table.add_column("Similarity", style="blue")
    table.add_column("Preview", style="white")

    for match in matches:
        project_short = match["project"].split("/")[-1] if match["project"] else "unknown"
        session_short = match["session_id"][:8] if match["session_id"] else "unknown"
        timestamp_formatted = format_timestamp(match["timestamp"])
        similarity_pct = f"{match['similarity']*100:.1f}%"

        table.add_row(
            project_short,
            session_short,
            match["role"],
            timestamp_formatted,
            similarity_pct,
            match["preview"][:100] + "..." if len(match["preview"]) > 100 else match["preview"]
        )

    console.print(table)
    console.print(f"\n[bold]Found: {len(matches)} semantically similar messages[/bold]")


def cmd_memory_extract(scope: str = "session", session_id: str | None = None):
    """Extract memories from sessions."""
    project_path = None

    if scope == "project":
        project_path = CURRENT_PROJECT
    elif scope == "session":
        project_path = CURRENT_PROJECT
        if not session_id:
            session_id = get_current_session_id()
        if not session_id:
            console.print("[red]Could not determine current session ID[/red]")
            return

    if session_id:
        # Extract from specific session
        process_session_memories(session_id, project_path)
    else:
        # Extract from all sessions in project
        console.print("[yellow]Extracting from all sessions not yet implemented[/yellow]")
        console.print("[yellow]Please specify --session [id] or use --scope session[/yellow]")


def cmd_memory_query(query: str = "", scope: str = "project", topic: str | None = None, limit: int = 20):
    """Query extracted memories."""
    project_path = None

    if scope == "project":
        project_path = CURRENT_PROJECT

    memories = query_memories("default", query, topic, project_path, limit)

    if not memories:
        console.print("[yellow]No memories found[/yellow]")
        return

    # Display results in a table
    table = Table(title=f"Extracted Memories{' for: ' + query if query else ''}")
    table.add_column("Topic", style="cyan")
    table.add_column("Content", style="white")
    table.add_column("Created", style="yellow")

    if query:
        table.add_column("Relevance", style="green")

    for mem in memories:
        topic_display = mem['topic'].replace('_', ' ').title()
        created_display = mem['created_at'].strftime('%Y-%m-%d') if hasattr(mem['created_at'], 'strftime') else str(mem['created_at'])[:10]

        row = [
            topic_display,
            mem['content'][:100] + "..." if len(mem['content']) > 100 else mem['content'],
            created_display
        ]

        if query:
            row.append(f"{mem['relevance']*100:.1f}%")

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[bold]Found: {len(memories)} memories[/bold]")


def cmd_memory_stats(scope: str = "project"):
    """Show memory statistics."""
    project_path = None

    if scope == "project":
        project_path = CURRENT_PROJECT

    db_path = get_database_path(project_path)

    if not db_path.exists():
        console.print(f"[yellow]Memory database not found at {db_path}[/yellow]")
        return

    conn = duckdb.connect(str(db_path))

    try:
        # Count by topic
        topic_counts = conn.execute("""
            SELECT topic, COUNT(*) as count
            FROM memories
            WHERE is_active = TRUE
            GROUP BY topic
            ORDER BY count DESC
        """).fetchall()

        # Total memories
        total = conn.execute("SELECT COUNT(*) FROM memories WHERE is_active = TRUE").fetchone()[0]

        # Recent additions
        recent = conn.execute("""
            SELECT COUNT(*) FROM memories
            WHERE is_active = TRUE AND created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
        """).fetchone()[0]

        console.print(f"\n[bold cyan]Memory Statistics[/bold cyan]")
        console.print(f"Database: {db_path}")
        console.print(f"Total memories: {total}")
        console.print(f"Recent (7 days): {recent}")
        console.print("\n[bold]By Topic:[/bold]")

        for topic, count in topic_counts:
            topic_display = topic.replace('_', ' ').title()
            console.print(f"  {topic_display}: {count}")

    except Exception as e:
        log.error(f"Failed to get memory stats: {e}")
    finally:
        conn.close()


# ============================================================================
# Main Entry Point
# ============================================================================


def main(args):
    """Main entry point."""
    if args.command == "projects":
        cmd_list_projects()

    elif args.command == "sessions":
        project = args.project if args.project else CURRENT_PROJECT
        cmd_list_sessions(project)

    elif args.command == "stats":
        if args.scope == "all":
            cmd_stats_all()
        elif args.scope == "project":
            cmd_stats_current_project()
        elif args.scope == "session":
            cmd_stats_current_session()

    elif args.command == "search":
        if not args.term:
            console.print("[red]Search term required[/red]")
            return
        cmd_search(args.term, args.scope, args.limit)

    elif args.command == "index":
        cmd_index(args.scope)

    elif args.command == "semantic":
        if not args.query:
            console.print("[red]Search query required[/red]")
            return
        cmd_semantic_search(args.query, args.scope, args.limit)

    elif args.command == "memory-extract":
        cmd_memory_extract(args.scope, getattr(args, 'session', None))

    elif args.command == "memory-query":
        cmd_memory_query(
            getattr(args, 'query', ""),
            args.scope,
            getattr(args, 'topic', None),
            args.limit
        )

    elif args.command == "memory-stats":
        cmd_memory_stats(args.scope)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Claude Code Meta Learning Memory

        Query and analyze Claude Code conversation history across projects and sessions.

        SCOPES:
          all      - All projects, all sessions
          project  - Current project, all sessions
          session  - Current project, current session

        COMMANDS:
          projects                    List all projects
          sessions [--project PATH]   List sessions (default: current project)
          stats [--scope SCOPE]       Show statistics (default: all)
          search TERM [--scope SCOPE] Search conversations
          index [--scope SCOPE]       Index messages for semantic search
          semantic QUERY              Semantic similarity search
          memory-extract              Extract memories from sessions
          memory-query [QUERY]        Query extracted memories
          memory-stats                Show memory statistics

        EXAMPLES:
          # List all projects
          uv run {SCRIPT_NAME}.py projects

          # List sessions for current project
          uv run {SCRIPT_NAME}.py sessions

          # Show stats for all conversations
          uv run {SCRIPT_NAME}.py stats --scope all

          # Show stats for current project
          uv run {SCRIPT_NAME}.py stats --scope project

          # Show stats for current session
          uv run {SCRIPT_NAME}.py stats --scope session

          # Search across all conversations
          uv run {SCRIPT_NAME}.py search "duckdb" --scope all

          # Search in current project
          uv run {SCRIPT_NAME}.py search "query" --scope project

          # Index messages for semantic search
          uv run {SCRIPT_NAME}.py index --scope project

          # Semantic similarity search
          uv run {SCRIPT_NAME}.py semantic "vector databases"

          # Extract memories from current session
          uv run {SCRIPT_NAME}.py memory-extract --scope session

          # Query memories
          uv run {SCRIPT_NAME}.py memory-query "my preferences"

          # List all memories
          uv run {SCRIPT_NAME}.py memory-query

          # Show memory statistics
          uv run {SCRIPT_NAME}.py memory-stats
        """)
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress all but error messages")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Projects command
    subparsers.add_parser("projects", help="List all projects")

    # Sessions command
    sessions_parser = subparsers.add_parser("sessions", help="List sessions for a project")
    sessions_parser.add_argument("--project", help="Project path (default: current)")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show summary statistics")
    stats_parser.add_argument("--scope", choices=["all", "project", "session"],
                             default="all", help="Statistics scope")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search conversations")
    search_parser.add_argument("term", help="Search term")
    search_parser.add_argument("--scope", choices=["all", "project", "session"],
                               default="all", help="Search scope")
    search_parser.add_argument("--limit", type=int, default=20, help="Max results to show")

    # Index command for vector search
    index_parser = subparsers.add_parser("index", help="Index messages for semantic search")
    index_parser.add_argument("--scope", choices=["all", "project", "session"],
                             default="project", help="Index scope")

    # Semantic search command
    semantic_parser = subparsers.add_parser("semantic", help="Semantic similarity search")
    semantic_parser.add_argument("query", help="Search query")
    semantic_parser.add_argument("--scope", choices=["all", "project", "session"],
                                default="all", help="Search scope")
    semantic_parser.add_argument("--limit", type=int, default=10, help="Max results to show")

    # Memory extraction command
    memory_extract_parser = subparsers.add_parser("memory-extract",
                                                   help="Extract memories from sessions")
    memory_extract_parser.add_argument("--scope", choices=["project", "session"],
                                       default="session", help="Extraction scope")
    memory_extract_parser.add_argument("--session", help="Specific session ID to extract from")

    # Memory query command
    memory_query_parser = subparsers.add_parser("memory-query",
                                                help="Query extracted memories")
    memory_query_parser.add_argument("query", nargs="?", default="", help="Search query (optional)")
    memory_query_parser.add_argument("--scope", choices=["all", "project"],
                                     default="project", help="Query scope")
    memory_query_parser.add_argument("--topic", choices=list(MEMORY_TOPICS.keys()),
                                     help="Filter by memory topic")
    memory_query_parser.add_argument("--limit", type=int, default=20, help="Max results to show")

    # Memory stats command
    memory_stats_parser = subparsers.add_parser("memory-stats",
                                                help="Show memory statistics")
    memory_stats_parser.add_argument("--scope", choices=["all", "project"],
                                     default="project", help="Stats scope")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if not args.command:
        parser.print_help()
    else:
        main(args)
