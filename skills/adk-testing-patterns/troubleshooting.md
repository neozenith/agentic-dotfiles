# ADK Testing Troubleshooting Guide

## Common Issues and Solutions

### Unit Test Issues

#### ❌ `AttributeError: 'ToolContext' object has no attribute 'state'`
**Cause:** InvocationContext not properly initialized with session
**Solution:**
```python
self.invoc_context = InvocationContext(
    session_service=session_service,
    invocation_id="TEST_ID",
    agent=root_agent,  # Must provide agent
    session=self.session,  # Must provide session
)
```

#### ❌ `ModuleNotFoundError: No module named 'your_package'`
**Cause:** Package not installed or not in PYTHONPATH
**Solution:**
```bash
# Option 1: Install in editable mode
pip install -e .

# Option 2: Add to pyproject.toml
[tool.pytest.ini_options]
pythonpath = "."
```

#### ❌ Tests pass individually but fail when run together
**Cause:** Shared state pollution between tests
**Solution:**
- Create fresh session in `setUp()` method
- Don't reuse `InvocationContext` across tests
- Use `session_service = InMemorySessionService()` at module level

### Evaluation Issues

#### ❌ `AgentEvaluator.evaluate` fails with "Package not found"
**Cause:** Package name doesn't match importable module
**Solution:**
```python
# Must match your package structure
await AgentEvaluator.evaluate(
    "your_package",  # Must be importable: `from your_package.agent import root_agent`
    "path/to/eval.json",
    num_runs=4
)
```

#### ❌ All eval scores are 0.0 or failing
**Cause:** Thresholds too strict or data format incorrect
**Solution:**
- Lower thresholds in `test_config.json` for development:
  ```json
  {"criteria": {"tool_trajectory_avg_score": 0.1, "response_match_score": 0.1}}
  ```
- Verify eval JSON has correct structure with `tool_uses` array
- Check that `intermediate_data.tool_uses` matches actual tool calls

#### ❌ `FileNotFoundError` when loading eval data
**Cause:** Incorrect path to eval JSON file
**Solution:**
```python
import pathlib

# Use pathlib for cross-platform compatibility
eval_path = str(pathlib.Path(__file__).parent / "data/scenario.test.json")
await AgentEvaluator.evaluate("package", eval_path, num_runs=4)
```

### Programmatic Testing Issues

#### ❌ `requests.exceptions.ConnectionError`
**Cause:** Agent server not running
**Solution:**
```bash
# Terminal 1: Start server
adk api_server your_package

# Terminal 2: Wait for "Uvicorn running on..." then run test
python tests/programmatic_example.py
```

#### ❌ Server returns 404 for `/run_sse`
**Cause:** Incorrect endpoint URL or server configuration
**Solution:**
```python
# Verify endpoint matches server output
RUN_ENDPOINT = "http://127.0.0.1:8000/run_sse"  # Default ADK endpoint

# Check server logs for actual endpoint
# Should see: INFO: Uvicorn running on http://127.0.0.1:8000
```

#### ❌ SSE stream hangs or never completes
**Cause:** Missing `stream=True` or incorrect event parsing
**Solution:**
```python
with requests.post(
    RUN_ENDPOINT,
    data=json.dumps(DATA),
    headers=HEADERS,
    stream=True  # REQUIRED for SSE
) as r:
    for chunk in r.iter_lines():
        if not chunk:
            continue  # Skip empty lines
        # Parse SSE format: "data: {json}"
        json_string = chunk.decode("utf-8").removeprefix("data: ").strip()
        event = json.loads(json_string)
```

### Session Loading Issues

#### ❌ `before_agent_callback` not loading state
**Cause:** Callback not registered or executed after agent start
**Solution:**
```python
# Callback MUST be set during agent initialization
root_agent = Agent(
    name="root_agent",
    before_agent_callback=load_initial_state,  # Set here
    # ...
)

# Verify callback is called by adding print statement
def load_initial_state(callback_context: CallbackContext) -> None:
    print("[DEBUG] Callback executed!")  # Should see this on first agent call
    # ...
```

#### ❌ State loaded but not persisting across turns
**Cause:** State updates not using `callback_context.state` reference
**Solution:**
```python
# WRONG: Creates new dict
def load_state(callback_context: CallbackContext) -> None:
    callback_context.state = {"new": "state"}  # ❌ Replaces reference

# CORRECT: Updates existing dict
def load_state(callback_context: CallbackContext) -> None:
    callback_context.state.update({"new": "state"})  # ✅ Preserves reference
```

#### ❌ `FileNotFoundError` when loading initial state JSON
**Cause:** Relative path resolved from wrong location
**Solution:**
```python
from pathlib import Path

# Resolve relative to this file, not CWD
STATE_FILE = Path(__file__).parent / "initial_state.json"
# Or use absolute path for clarity
STATE_FILE = Path("/absolute/path/to/initial_state.json")
```

### pytest Configuration Issues

#### ❌ `ImportError: cannot import name 'root_agent'`
**Cause:** Package not in Python path
**Solution:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
pythonpath = "."  # Ensures current directory is in path
```

#### ❌ Async tests not running or hanging
**Cause:** `pytest-asyncio` not configured
**Solution:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "function"

# Install pytest-asyncio
pip install pytest-asyncio>=0.26.0
```

#### ❌ Tests discovered in unexpected locations
**Cause:** Default test discovery too broad
**Solution:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests", "eval"]  # Only search these directories
python_files = ["test_*.py"]   # Only files matching this pattern
```

## Environment Variable Issues

#### ❌ API keys not loaded in tests
**Cause:** `.env` file not loaded or in wrong location
**Solution:**
```python
# Add to test file or conftest.py
import pytest
from dotenv import load_dotenv

@pytest.fixture(scope="session", autouse=True)
def load_env():
    load_dotenv()  # Loads .env from current directory
```

#### ❌ Tests pass locally but fail in CI
**Cause:** Environment variables not set in CI
**Solution:**
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest
  env:
    GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
    # Add other required env vars
```

## Performance Issues

#### ❌ Eval tests take too long
**Solution:**
- Reduce `num_runs` for development (use 1-2 instead of 4)
- Use smaller test cases for rapid iteration
- Run full eval suite only in CI

#### ❌ Unit tests are slow
**Solution:**
- Mock external API calls
- Use `@pytest.mark.skipif` for optional expensive tests
- Avoid creating real sessions if pure tool logic can be tested

## Debugging Tips

### Enable verbose logging
```bash
# For pytest
pytest -v -s  # -s shows print statements

# For ADK agent
export LOG_LEVEL=DEBUG
adk api_server your_package
```

### Inspect eval results
```python
# AgentEvaluator saves results to .adk/eval_history/
# Check JSON files for detailed scoring breakdown
```

### Print session state in tests
```python
def test_tool(self):
    result = your_tool(tool_context=self.tool_context)
    print(f"State after tool: {self.tool_context.state}")  # Debug output
    # Run with: pytest tests/unit/test_tools.py::test_tool -s
```

### Validate eval JSON format
```python
import json

# Load and validate structure
with open("eval/data/scenario.test.json") as f:
    data = json.load(f)
    assert "eval_cases" in data
    assert len(data["eval_cases"]) > 0
    assert "conversation" in data["eval_cases"][0]
```

## Getting Help

1. Check ADK documentation: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder
2. Review travel-concierge sample: `/Users/joshpeak/play/adk-samples/python/agents/travel-concierge`
3. Enable debug logging and inspect full event payloads
4. Simplify test case to minimal reproduction
