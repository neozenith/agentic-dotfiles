---
paths:
  - ".claude/skills/**/scripts/*.py"
  - "scripts/**/*.py"
---

# ML HuggingFace Script Conventions

Rules specific to Python scripts that use HuggingFace `transformers` pipelines. Extends `claude_skills.md` and `RULES.md`.

## Deferred Import Exception

Heavy ML libraries (`transformers`, `torch`) are the **one exception** to the top-level import rule. Import inside the function that loads the pipeline to avoid 3+ second startup penalty on `--help` and non-ML code paths:

```python
def load_pipeline(task: str, model: str, device: str = "cpu") -> Any:
    from transformers import pipeline  # noqa: E402
    return pipeline(task, model=model, device=device)
```

## PEP-723 Dependency Pinning

Pin `transformers` to a major version range. The 4.x-to-5.x transition removed pipeline tasks (`summarization`, `text2text-generation`):

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "transformers>=4.40.0,<5.0.0",
#   "torch>=2.2.0",
#   "sentencepiece>=0.2.0",
# ]
# ///
```

## Model Token Limits

BERT-family models have ~512 token input limits. Truncate at word boundaries before feeding to pipelines:

```python
DEFAULT_MAX_CHARS = 2000  # ~512 tokens for BERT

def truncate_content(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space] + "..."
    return truncated + "..."
```

## Pipeline Configuration

- Always set `device="cpu"` explicitly (no silent GPU fallback)
- Use `batch_size` parameter for processing efficiency
- Store default models in a constant dict, overrideable via `--model`

```python
DEFAULT_MODELS: dict[str, str] = {
    "sentiment": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    "zero-shot": "facebook/bart-large-mnli",
    "summarize": "facebook/bart-large-cnn",
    "ner": "dslim/bert-base-NER",
}
```

## Output Format

Enrich input messages in-place with an `analysis` key rather than returning a separate structure. Preserves all original fields for downstream chaining:

```json
{
  "role": "user",
  "timestamp": "...",
  "content": "...",
  "analysis": {"task": "sentiment", "model": "...", "label": "POSITIVE", "score": 0.99}
}
```

## NumPy Type Conversion

Pipeline outputs often contain numpy scalars. Convert to native Python types before JSON serialization:

```python
{"score": round(float(e["score"]), 4), "start": int(e["start"])}
```

## Argparse: Shared Parent Parser Pattern

When a CLI has subcommands that all share options (`--session`, `--model`, `--role`), use `parents=` so flags work **after** the subcommand name:

```python
shared = argparse.ArgumentParser(add_help=False)
shared.add_argument("--session", help="...")
shared.add_argument("--model", help="...")

subparsers = parser.add_subparsers(dest="subcommand")
subparsers.add_parser("sentiment", parents=[shared])
subparsers.add_parser("ner", parents=[shared])
```

This allows both `script.sh --session X ner` and `script.sh ner --session X`.

## Makefile: ML Dependencies in Test Runner

The test runner needs `--with` flags to inject ML deps since they're PEP-723 deps of the script, not the test file. Mirror the script's dependency spec in a Makefile variable:

```makefile
ANALYZE_DEPS = --with "transformers>=4.40.0,<5.0.0" --with "torch>=2.2.0" --with "sentencepiece>=0.2.0"

test:
	uv run $(ANALYZE_DEPS) pytest test_analyze_text.py -v
```

## Testing ML Pipelines

Gate integration tests on import availability, but make them **mandatory** in the Makefile by providing deps via `uv run --with`:

```python
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

skip_without_torch = pytest.mark.skipif(
    not TORCH_AVAILABLE,
    reason="torch not installed",
)

@skip_without_torch
class TestSentimentIntegration:
    def test_positive(self) -> None:
        messages = [{"role": "user", "content": "I love this!"}]
        results = analyze_sentiment(messages, batch_size=1)
        assert results[0]["analysis"]["label"] == "POSITIVE"
```

Unit tests (truncation, batching, stdin parsing, error handling) must **always** pass without ML deps.
