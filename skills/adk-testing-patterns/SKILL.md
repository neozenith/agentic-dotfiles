---
name: "adk-testing-patterns"
description: "Expert guidance on testing Google ADK agents using pytest. Covers evals/, unit tests for deterministic tools, programmatic agent interaction via API, session loading patterns with before_agent_callback, and loading sessions from JSON or DatabaseSessionService for curated testing scenarios."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# ADK Testing Patterns Skill

You are now operating as a Google ADK testing specialist. Your expertise covers comprehensive testing strategies for ADK agents including evaluations, unit tests, programmatic testing, and session state management.

## Core Testing Architecture

**Testing Layers:**
1. **Unit Tests** (`tests/unit/`) - Test deterministic tools in isolation
2. **Integration Tests** (`tests/`) - Test agent interactions programmatically
3. **Evaluations** (`evals/` or `eval/`) - End-to-end agent behavior validation
4. **Session Management** - Load/restore sessions for curated test scenarios

## 1. Directory Structure

### Standard ADK Testing Layout
```
project-root/
├── pyproject.toml              # pytest configuration
├── agent_package/
│   ├── agent.py               # Root agent with before_agent_callback
│   └── tools/
│       └── your_tools.py      # Deterministic tools to test
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   └── test_tools.py      # Unit tests for deterministic tools
│   ├── programmatic_example.py # API interaction example
│   ├── pre_booking_sample.md  # Sample session states (optional)
│   └── post_booking_sample.md
└── eval/  # or evals/
    ├── data/
    │   ├── test_config.json   # Evaluation criteria/thresholds
    │   ├── scenario1.test.json # Eval case with conversation & session_input
    │   ├── scenario2.test.json
    │   └── scenario3.test.json
    └── test_eval.py           # Pytest evaluation runner
```

**Key Points:**
- `tests/unit/` for fast, isolated tool tests
- `tests/` root for integration/API tests
- `eval/` for comprehensive agent behavior validation
- `eval/data/` contains JSON test cases with expected trajectories

## 2. Unit Testing Deterministic Tools

### Setup Pattern (`tests/unit/test_tools.py`)

```python
"""Basic tests for individual tools."""
import os
import unittest
from dotenv import load_dotenv
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
import pytest

from your_package.agent import root_agent
from your_package.tools.memory import memorize_tool
from your_package.tools.search import search_tool


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables for all tests."""
    load_dotenv()


# Shared services for all tests
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()


class TestTools(unittest.TestCase):
    """Test cases for deterministic tools."""

    def setUp(self):
        """Set up for test methods - creates fresh session and context."""
        super().setUp()
        self.session = session_service.create_session_sync(
            app_name="YourApp",
            user_id="test_user_001",
        )
        self.user_id = "test_user_001"
        self.session_id = self.session.id

        # Create invocation context for tool execution
        self.invoc_context = InvocationContext(
            session_service=session_service,
            invocation_id="TEST_INVOCATION_ID",
            agent=root_agent,
            session=self.session,
        )

        # Tool context is passed to all tools
        self.tool_context = ToolContext(invocation_context=self.invoc_context)

    def test_memory_tool(self):
        """Test that memory tool correctly stores values in session state."""
        result = memorize_tool(
            key="test_key",
            value="test_value",
            tool_context=self.tool_context,
        )

        # Verify tool returns success
        self.assertIn("status", result)

        # Verify state was updated
        self.assertEqual(
            self.tool_context.state["test_key"],
            "test_value"
        )

    @pytest.mark.skipif(
        not os.getenv("GOOGLE_PLACES_API_KEY"),
        reason="Google Places API key not available"
    )
    def test_places_lookup(self):
        """Test external API tool - skip if credentials unavailable."""
        # Pre-populate state with test data
        self.tool_context.state["poi"] = {
            "places": [{"place_name": "Machu Picchu", "address": "Peru"}]
        }

        result = search_tool(key="poi", tool_context=self.tool_context)

        # Verify API enrichment occurred
        self.assertIn("place_id", result["places"][0])
        self.assertEqual(
            self.tool_context.state["poi"]["places"][0]["place_id"],
            "ChIJVVVViV-abZERJxqgpA43EDo",  # Known place_id
        )
```

**Testing Principles:**
- **Isolation**: Each test gets fresh session and invocation context
- **State Verification**: Check both tool return values AND session state changes
- **Skip Unavailable Resources**: Use `@pytest.mark.skipif` for optional external dependencies
- **Deterministic Tools First**: Focus unit tests on tools with predictable outputs

## 3. Programmatic Agent Interaction (`tests/programmatic_example.py`)

### API-Based Testing Pattern

```python
"""Example of programmatic interaction with ADK agent via API."""
import json
import requests

# Connect to running agent server: `adk api_server your_package`
RUN_ENDPOINT = "http://127.0.0.1:8000/run_sse"
HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "text/event-stream",
}

# Create or load existing session
SESSION_ENDPOINT = "http://127.0.0.1:8000/apps/your_app/users/test_user/sessions/test_session_001"
response = requests.post(SESSION_ENDPOINT)
print("Session created:", response.json())

# Multi-turn conversation test
user_inputs = [
    "First user query to test initial response",
    "Follow-up query to test context retention",
]

for user_input in user_inputs:
    DATA = {
        "session_id": "test_session_001",
        "app_name": "your_app",
        "user_id": "test_user",
        "new_message": {
            "role": "user",
            "parts": [{"text": user_input}],
        },
    }

    print(f'\n[user]: "{user_input}"')

    with requests.post(
        RUN_ENDPOINT, data=json.dumps(DATA), headers=HEADERS, stream=True
    ) as r:
        for chunk in r.iter_lines():
            if not chunk:
                continue

            json_string = chunk.decode("utf-8").removeprefix("data: ").strip()
            event = json.loads(json_string)

            # Error handling
            if "content" not in event:
                print("ERROR:", event)
                continue

            author = event["author"]

            # Extract function calls (tool usage)
            function_calls = [
                e["functionCall"]
                for e in event["content"]["parts"]
                if "functionCall" in e
            ]

            # Extract function responses (tool results)
            function_responses = [
                e["functionResponse"]
                for e in event["content"]["parts"]
                if "functionResponse" in e
            ]

            # Extract text responses
            if "text" in event["content"]["parts"][0]:
                text_response = event["content"]["parts"][0]["text"]
                print(f"\n{author}: {text_response}")

            # Log tool calls
            if function_calls:
                for function_call in function_calls:
                    name = function_call["name"]
                    args = function_call["args"]
                    print(f'\n{author} TOOL CALL: "{name}"')
                    print(f'Args: {json.dumps(args, indent=2)}')

            # Log tool responses and trigger UI updates
            elif function_responses:
                for function_response in function_responses:
                    function_name = function_response["name"]
                    payload = json.dumps(function_response["response"], indent=2)
                    print(f'\n{author} TOOL RESPONSE: "{function_name}"')
                    print(f'Result: {payload}')

                    # Application-specific UI triggers
                    match function_name:
                        case "search_agent":
                            print("[app] → Render search results carousel")
                        case "map_tool":
                            print("[app] → Display map with markers")
                        case "booking_agent":
                            print("[app] → Show booking confirmation UI")
```

**Integration Testing Benefits:**
- **Real Agent Execution**: Tests actual agent logic, not mocks
- **Event Stream Validation**: Verify SSE event format and sequencing
- **Multi-Turn Context**: Test conversation state persistence
- **UI Integration Points**: Identify when/how to update frontend based on tool responses
- **Debugging Aid**: Full event payload inspection for troubleshooting

**Running the Test:**
```bash
# Terminal 1: Start agent server
adk api_server your_package

# Terminal 2: Run programmatic test
python tests/programmatic_example.py
```

## 4. Agent Evaluations (`eval/test_eval.py`)

### Evaluation Structure

```python
"""Comprehensive agent behavior evaluation using ADK's AgentEvaluator."""
import pathlib
import dotenv
from google.adk.evaluation import AgentEvaluator
import pytest


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables for eval runs."""
    dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_inspire_scenario():
    """Evaluate agent performance on inspiration/discovery use case."""
    await AgentEvaluator.evaluate(
        "your_package",  # Package name (must be importable)
        str(pathlib.Path(__file__).parent / "data/inspire.test.json"),
        num_runs=4  # Run multiple times to assess consistency
    )


@pytest.mark.asyncio
async def test_planning_scenario():
    """Evaluate agent performance on planning workflow."""
    await AgentEvaluator.evaluate(
        "your_package",
        str(pathlib.Path(__file__).parent / "data/planning.test.json"),
        num_runs=4
    )


@pytest.mark.asyncio
async def test_edge_cases():
    """Evaluate agent handling of error conditions and edge cases."""
    await AgentEvaluator.evaluate(
        "your_package",
        str(pathlib.Path(__file__).parent / "data/edge_cases.test.json"),
        num_runs=2  # Fewer runs for deterministic error handling
    )
```

### Evaluation Data Format (`eval/data/scenario.test.json`)

```json
{
  "eval_set_id": "uuid-for-this-eval-set",
  "name": "Scenario Name",
  "description": "Optional description of what this eval tests",
  "eval_cases": [
    {
      "eval_id": "unique-eval-case-id",
      "conversation": [
        {
          "invocation_id": "turn-1-uuid",
          "user_content": {
            "parts": [{"text": "User's first message"}],
            "role": "user"
          },
          "final_response": {
            "parts": [{"text": "Expected agent response (or actual golden response)"}],
            "role": "model"
          },
          "intermediate_data": {
            "tool_uses": [
              {
                "name": "transfer_to_agent",
                "args": {"agent_name": "expected_sub_agent"}
              },
              {
                "name": "expected_tool",
                "args": {"param": "expected_value"}
              }
            ],
            "intermediate_responses": []
          },
          "creation_timestamp": 1234567890.123
        },
        {
          "invocation_id": "turn-2-uuid",
          "user_content": {
            "parts": [{"text": "Follow-up message"}],
            "role": "user"
          },
          "final_response": {
            "parts": [{"text": "Expected follow-up response"}],
            "role": "model"
          },
          "intermediate_data": {
            "tool_uses": [
              {"name": "another_expected_tool", "args": {}}
            ],
            "intermediate_responses": []
          },
          "creation_timestamp": 1234567891.456
        }
      ],
      "session_input": {
        "app_name": "",
        "user_id": "",
        "state": {
          "user_profile": {
            "preference_1": "value_1",
            "preference_2": "value_2"
          },
          "initial_context": "Any initial state to load into session"
        }
      },
      "creation_timestamp": 1234567890.0
    }
  ],
  "creation_timestamp": 1234567890.0
}
```

**Key Eval Fields:**
- **conversation**: Multi-turn dialogue with expected tool trajectories
- **session_input.state**: Initial session state (user profile, context, etc.)
- **intermediate_data.tool_uses**: Expected sequence of tool/agent calls
- **final_response**: Expected or actual golden response for comparison
- **num_runs**: Evaluate consistency across multiple runs

### Evaluation Criteria (`eval/data/test_config.json`)

```json
{
  "criteria": {
    "tool_trajectory_avg_score": 0.1,
    "response_match_score": 0.1
  }
}
```

**Scoring Metrics:**
- **tool_trajectory_avg_score**: Minimum acceptable score for tool call sequence accuracy
- **response_match_score**: Minimum acceptable score for response content similarity
- Lower thresholds (0.1) allow more variation; higher (0.8+) enforce strict matching

**Running Evaluations:**
```bash
# Run all eval tests
pytest eval/

# Run specific eval scenario
pytest eval/test_eval.py::test_inspire_scenario -v

# Run with detailed output
pytest eval/ -v -s
```

## 5. Session Loading Patterns with `before_agent_callback`

### Pattern: Load Initial State from JSON File

**Agent Configuration (`agent.py`):**
```python
from google.adk.agents import Agent
from your_package.tools.session_loader import load_initial_state


root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="Agent with pre-loaded session state",
    instruction="Your agent instructions...",
    tools=[...],
    sub_agents=[...],
    before_agent_callback=load_initial_state,  # Called before system instruction
)
```

**Session Loader (`tools/session_loader.py`):**
```python
import json
from pathlib import Path
from google.adk.agents.callback_context import CallbackContext


# Path to initial state JSON file
INITIAL_STATE_PATH = Path(__file__).parent.parent / "tests/initial_state.json"


def load_initial_state(callback_context: CallbackContext) -> None:
    """
    Load initial session state from JSON file.

    Called by ADK before constructing system instruction, allowing
    state initialization without manual setup in UI/API calls.

    Args:
        callback_context: Contains session state and agent context
    """
    data = {}
    with open(INITIAL_STATE_PATH, "r") as file:
        data = json.load(file)
        print(f"[Session Loader] Loading initial state: {data}")

    # Merge loaded state into session
    _merge_state(data.get("state", {}), callback_context.state)


def _merge_state(source: dict, target: dict) -> None:
    """Recursively merge source state into target session state."""
    for key, value in source.items():
        if isinstance(value, dict) and key in target:
            _merge_state(value, target[key])
        else:
            target[key] = value
```

**Initial State JSON (`tests/initial_state.json`):**
```json
{
  "state": {
    "user_profile": {
      "name": "Test User",
      "preferences": {
        "theme": "dark",
        "language": "en"
      }
    },
    "session_context": {
      "source": "test_suite",
      "environment": "staging"
    }
  }
}
```

**Benefits:**
- **Reduced Setup**: No manual state initialization in tests/UI
- **Reproducible Tests**: Consistent starting state across test runs
- **Quick Prototyping**: Fast iteration with pre-configured scenarios

### Pattern: Load Session from DatabaseSessionService

**Production Pattern:**
```python
from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions import DatabaseSessionService


# Initialize persistent session service
session_service = DatabaseSessionService(
    database_url="postgresql://user:pass@localhost/sessions"
)


def load_previous_session(callback_context: CallbackContext) -> None:
    """
    Load existing session state from database.

    Useful for:
    - Resuming interrupted conversations
    - Testing with production session snapshots
    - A/B testing different agent versions on same history
    """
    session_id = callback_context.session.id
    user_id = callback_context.session.user_id
    app_name = callback_context.session.app_name

    # Retrieve session from database
    existing_session = session_service.get_session_sync(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )

    if existing_session and existing_session.state:
        print(f"[Session Loader] Restoring session {session_id} state")
        callback_context.state.update(existing_session.state)
    else:
        print(f"[Session Loader] No existing state found, using defaults")
        # Initialize with defaults
        callback_context.state.update({
            "initialized_at": "timestamp",
            "default_config": {}
        })
```

**Testing with Session Snapshots:**
```python
import json
from google.adk.sessions import InMemorySessionService


def load_test_session_snapshot(callback_context: CallbackContext) -> None:
    """
    Load session from snapshot file for testing.

    Allows testing agent behavior at specific conversation states.
    """
    # Snapshot files can be exported from production or created manually
    snapshot_path = f"tests/snapshots/{callback_context.session.id}.json"

    try:
        with open(snapshot_path, "r") as f:
            snapshot = json.load(f)

        # Restore state
        callback_context.state.update(snapshot["state"])

        # Optionally restore conversation history
        if "messages" in snapshot:
            # Add previous messages to context (implementation depends on ADK version)
            pass

        print(f"[Test] Loaded session snapshot from {snapshot_path}")
    except FileNotFoundError:
        print(f"[Test] No snapshot found at {snapshot_path}, starting fresh")
```

**Curated Test Scenarios:**
```python
# tests/scenarios/after_booking.json
{
  "scenario_id": "post_booking_confirmation",
  "description": "User has completed flight booking, testing follow-up questions",
  "state": {
    "booking_status": "confirmed",
    "booking_reference": "ABC123",
    "flight_details": {
      "departure": "2025-12-01T10:00:00Z",
      "arrival": "2025-12-01T14:00:00Z",
      "from": "SFO",
      "to": "LAX"
    },
    "user_profile": {
      "name": "Test User",
      "frequent_flyer": "AA1234567"
    }
  }
}
```

**Loading Curated Scenarios:**
```python
import os
from pathlib import Path


def load_curated_scenario(callback_context: CallbackContext) -> None:
    """
    Load curated test scenario based on environment variable.

    Usage:
        SCENARIO=after_booking adk api_server your_package
    """
    scenario_name = os.getenv("SCENARIO", "default")
    scenario_path = Path(__file__).parent.parent / f"tests/scenarios/{scenario_name}.json"

    if scenario_path.exists():
        with open(scenario_path, "r") as f:
            scenario = json.load(f)

        callback_context.state.update(scenario["state"])
        print(f"[Scenario] Loaded '{scenario['description']}'")
    else:
        print(f"[Scenario] '{scenario_name}' not found, using default state")
```

## 6. pyproject.toml Configuration

### Pytest Configuration
```toml
[tool.pytest.ini_options]
pythonpath = "."  # Ensure package is importable
asyncio_default_fixture_loop_scope = "function"  # For async tests

# Optional: Custom test markers
markers = [
    "unit: Unit tests for individual tools",
    "integration: Integration tests via API",
    "eval: Agent evaluation tests",
    "slow: Tests that take significant time",
]

# Optional: Test discovery patterns
testpaths = ["tests", "eval"]
python_files = ["test_*.py", "*_test.py"]
```

### Development Dependencies
```toml
[dependency-groups]
dev = [
    "pytest>=8.3.5",
    "google-adk[eval]>=1.16.0",  # Includes AgentEvaluator
    "pytest-asyncio>=0.26.0",     # For async eval tests
    "python-dotenv>=1.0.1",       # Load .env in tests
]
```

## 7. Complete Testing Workflow

### Test Development Cycle
```bash
# 1. Unit test individual tools
pytest tests/unit/ -v

# 2. Start agent server for integration testing
adk api_server your_package &

# 3. Run programmatic integration tests
python tests/programmatic_example.py

# 4. Run comprehensive evaluations
pytest eval/ -v

# 5. Test with curated scenarios
SCENARIO=after_booking adk api_server your_package
```

### CI/CD Pipeline Example
```yaml
# .github/workflows/test.yml
name: ADK Agent Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --group dev

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run evaluations
        run: pytest eval/ -v
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
```

## 8. Best Practices Summary

**Unit Testing:**
- ✅ Test deterministic tools in isolation
- ✅ Use fresh InvocationContext per test
- ✅ Verify both return values and state changes
- ✅ Skip tests requiring unavailable credentials with `@pytest.mark.skipif`

**Integration Testing:**
- ✅ Test via `/run_sse` endpoint for realistic execution
- ✅ Validate SSE event sequences and payloads
- ✅ Test multi-turn conversations for context retention
- ✅ Use programmatic tests to identify UI integration points

**Evaluation Testing:**
- ✅ Define golden conversation trajectories in JSON
- ✅ Include `session_input.state` for reproducible starting conditions
- ✅ Run multiple times (`num_runs`) to assess consistency
- ✅ Set appropriate scoring thresholds in `test_config.json`

**Session Management:**
- ✅ Use `before_agent_callback` for initial state loading
- ✅ Load from JSON files for development/testing
- ✅ Load from DatabaseSessionService for production scenarios
- ✅ Create curated scenario snapshots for specific test cases
- ✅ Use environment variables to switch between scenarios

**Project Organization:**
- ✅ Separate `tests/unit/`, `tests/`, and `eval/` concerns
- ✅ Store eval data in `eval/data/` with descriptive names
- ✅ Keep session snapshots in `tests/snapshots/` or `tests/scenarios/`
- ✅ Configure pytest in `pyproject.toml` for consistency

## 9. Troubleshooting

**Issue: Eval tests fail with "Package not found"**
- Solution: Ensure package is importable: `pip install -e .` or verify `pyproject.toml` build config

**Issue: Unit tests can't find session_service**
- Solution: Initialize `InMemorySessionService()` at module level, not inside test methods

**Issue: before_agent_callback not loading state**
- Solution: Verify callback is registered before agent initialization AND that state merge is recursive

**Issue: Programmatic tests timeout**
- Solution: Ensure agent server is running (`adk api_server`) and endpoint URL is correct

**Issue: Eval scores always fail**
- Solution: Check `test_config.json` thresholds (lower for development, higher for production gates)

## 10. References

**ADK Documentation:**
- AgentEvaluator: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/evaluation
- Session Services: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/sessions
- Callbacks: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/callbacks

**Sample Implementation:**
- Travel Concierge (Google ADK Samples): Comprehensive reference implementation
- Path: `/Users/joshpeak/play/adk-samples/python/agents/travel-concierge`

---

**When to use this skill:**
- Setting up pytest infrastructure for ADK agents
- Writing unit tests for agent tools
- Creating agent evaluations with golden trajectories
- Implementing session state management for testing
- Debugging test failures or flaky evaluations
- Designing curated test scenarios for specific agent states
