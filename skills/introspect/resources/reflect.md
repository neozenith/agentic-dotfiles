# Meta-Prompt Reflection

The `reflect` command runs a meta-prompt against session events using `claude -p`, or a local ML engine.

## Basic Usage

```bash
# Rate each assistant message
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    -t assistant_text \
    --prompt "Rate the quality of this response 1-10 and explain: {{content}}"

# Self-evaluation of current session
.claude/skills/introspect/scripts/introspect_sessions.sh reflect ${CLAUDE_SESSION_ID} \
    -t assistant_text --limit 5 \
    --prompt "Evaluate this response:
1. Was it helpful? (yes/no)
2. Was it accurate? (yes/no)
3. Was it concise? (yes/no)
4. What could be improved?

Response: {{content}}"
```

## Placeholders

| Placeholder | Value |
|---|---|
| `{{content}}` | Message text content |
| `{{event_type}}` | Raw event type (user, assistant, etc.) |
| `{{uuid}}` | Event UUID |
| `{{timestamp}}` | Event timestamp |

## Options

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    --prompt "Analyze: {{content}}" \     # Meta-prompt
    --prompt-file prompt.txt \            # Or read from file
    -t human assistant_text \             # Filter by msg_kind
    --start UUID1 \                       # Start from UUID
    --end UUID2 \                         # End at UUID
    --limit 10 \                          # Max events to process
    --schema '{"rating": "number"}'       # Expected JSON output schema
```

## Structured Output

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh -f json reflect SESSION_ID \
    --prompt "Analyze for sentiment and key topics: {{content}}" \
    --schema '{"sentiment": "string", "topics": ["string"], "confidence": "number"}'
```

Results are persisted to the SQLite cache (`reflections` + `event_annotations` tables).

## ML Engines (Local HuggingFace Models)

A cheaper, faster alternative to `--prompt`. ML dependencies are injected at runtime only when `--engine` is used.

```bash
# Sentiment analysis on human-typed messages
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    --engine sentiment -t human

# Named Entity Recognition
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    --engine ner -t human -n 50

# Zero-shot classification with custom labels
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    --engine zero-shot --labels "frustrated,satisfied,confused,neutral"

# Summarize all messages into one
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    --engine summarize --concatenate

# Override default model
.claude/skills/introspect/scripts/introspect_sessions.sh reflect SESSION_ID \
    --engine sentiment --ml-model "cardiffnlp/twitter-roberta-base-sentiment"
```

### Available Engines

| Engine | HF Task | Default Model |
|--------|---------|---------------|
| `sentiment` | sentiment-analysis | distilbert-base-uncased-finetuned-sst-2-english |
| `zero-shot` | zero-shot-classification | facebook/bart-large-mnli |
| `ner` | ner | dslim/bert-base-NER |
| `summarize` | summarization | facebook/bart-large-cnn |

### ML Engine Options

- `--engine {sentiment,zero-shot,ner,summarize}` — Use local ML model
- `--ml-model MODEL` — Override default HuggingFace model
- `--batch-size N` — Batch size (default: 8)
- `--max-chars N` — Max chars per message for BERT models (default: 2000, ~512 tokens)
- `--labels "a,b,c"` — Comma-separated labels for zero-shot engine
- `--concatenate` — Concatenate all messages (for summarize engine)
