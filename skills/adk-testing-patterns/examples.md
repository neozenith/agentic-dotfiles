# ADK Testing Code Examples

Complete, copy-paste ready examples for ADK agent testing.

## Example 1: Complete Unit Test File

**File: `tests/unit/test_tools.py`**

```python
"""Unit tests for agent tools."""
import os
import unittest
from dotenv import load_dotenv
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
import pytest

from my_agent.agent import root_agent
from my_agent.tools.memory import memorize
from my_agent.tools.search import search_places


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables."""
    load_dotenv()


# Shared services
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()


class TestMemoryTool(unittest.TestCase):
    """Test memory storage tool."""

    def setUp(self):
        """Create fresh session for each test."""
        self.session = session_service.create_session_sync(
            app_name="TestApp",
            user_id="test_user_001",
        )
        self.invoc_context = InvocationContext(
            session_service=session_service,
            invocation_id="TEST_INVOCATION",
            agent=root_agent,
            session=self.session,
        )
        self.tool_context = ToolContext(invocation_context=self.invoc_context)

    def test_memorize_simple_value(self):
        """Test storing simple string value."""
        result = memorize(
            key="user_name",
            value="Alice",
            tool_context=self.tool_context,
        )

        # Verify tool returned success
        self.assertEqual(result["status"], "success")

        # Verify state was updated
        self.assertEqual(self.tool_context.state["user_name"], "Alice")

    def test_memorize_complex_object(self):
        """Test storing nested dictionary."""
        user_data = {
            "name": "Bob",
            "preferences": {
                "theme": "dark",
                "language": "en"
            }
        }

        result = memorize(
            key="user_profile",
            value=user_data,
            tool_context=self.tool_context,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            self.tool_context.state["user_profile"]["preferences"]["theme"],
            "dark"
        )

    def test_memorize_overwrites_existing(self):
        """Test that memorize overwrites previous values."""
        # Store initial value
        memorize(key="counter", value=1, tool_context=self.tool_context)
        self.assertEqual(self.tool_context.state["counter"], 1)

        # Overwrite with new value
        memorize(key="counter", value=2, tool_context=self.tool_context)
        self.assertEqual(self.tool_context.state["counter"], 2)


class TestSearchTool(unittest.TestCase):
    """Test external API search tool."""

    def setUp(self):
        """Create fresh session for each test."""
        self.session = session_service.create_session_sync(
            app_name="TestApp",
            user_id="test_user_002",
        )
        self.invoc_context = InvocationContext(
            session_service=session_service,
            invocation_id="TEST_SEARCH",
            agent=root_agent,
            session=self.session,
        )
        self.tool_context = ToolContext(invocation_context=self.invoc_context)

    @pytest.mark.skipif(
        not os.getenv("GOOGLE_PLACES_API_KEY"),
        reason="Google Places API key not available"
    )
    def test_search_places_enrichment(self):
        """Test that search tool enriches place data with API."""
        # Pre-populate state with basic place data
        self.tool_context.state["destinations"] = {
            "places": [
                {"place_name": "Eiffel Tower", "address": "Paris, France"}
            ]
        }

        # Call tool to enrich
        result = search_places(
            key="destinations",
            tool_context=self.tool_context
        )

        # Verify enrichment occurred
        self.assertIn("places", result)
        self.assertIn("place_id", result["places"][0])
        self.assertIn("coordinates", result["places"][0])

        # Verify state was updated
        enriched_place = self.tool_context.state["destinations"]["places"][0]
        self.assertIsNotNone(enriched_place["place_id"])

    def test_search_handles_empty_input(self):
        """Test graceful handling of empty/missing data."""
        result = search_places(
            key="nonexistent_key",
            tool_context=self.tool_context
        )

        # Should return error or empty result, not crash
        self.assertIn("error", result.lower() or "places" in result)
```

## Example 2: Programmatic API Test

**File: `tests/programmatic_example.py`**

```python
"""Programmatic interaction with ADK agent via API.

Prerequisites:
    1. Start agent server: adk api_server my_agent
    2. Run this script: python tests/programmatic_example.py
"""
import json
import requests


# Configuration
RUN_ENDPOINT = "http://127.0.0.1:8000/run_sse"
SESSION_ENDPOINT = "http://127.0.0.1:8000/apps/my_app/users/test_user/sessions/test_session"
HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "text/event-stream",
}


def create_session():
    """Create or retrieve existing session."""
    response = requests.post(SESSION_ENDPOINT)
    session_data = response.json()
    print(f"✓ Session ready: {session_data['id']}")
    return session_data


def send_message(user_input: str, session_id: str):
    """Send user message and stream agent response."""
    data = {
        "session_id": session_id,
        "app_name": "my_app",
        "user_id": "test_user",
        "new_message": {
            "role": "user",
            "parts": [{"text": user_input}],
        },
    }

    print(f'\n👤 User: "{user_input}"')

    with requests.post(
        RUN_ENDPOINT, data=json.dumps(data), headers=HEADERS, stream=True
    ) as r:
        for chunk in r.iter_lines():
            if not chunk:
                continue

            # Parse SSE event
            json_string = chunk.decode("utf-8").removeprefix("data: ").strip()
            try:
                event = json.loads(json_string)
            except json.JSONDecodeError:
                print(f"⚠️  Failed to parse: {json_string[:100]}")
                continue

            # Handle errors
            if "content" not in event:
                print(f"❌ Error: {event}")
                continue

            author = event["author"]

            # Extract text responses
            for part in event["content"]["parts"]:
                if "text" in part:
                    print(f"\n🤖 {author}: {part['text']}")

            # Extract function calls
            function_calls = [
                e["functionCall"]
                for e in event["content"]["parts"]
                if "functionCall" in e
            ]
            for fc in function_calls:
                print(f"\n🔧 Tool Call: {fc['name']}")
                print(f"   Args: {json.dumps(fc['args'], indent=2)}")

            # Extract function responses
            function_responses = [
                e["functionResponse"]
                for e in event["content"]["parts"]
                if "functionResponse" in e
            ]
            for fr in function_responses:
                print(f"\n📦 Tool Result: {fr['name']}")
                # Optionally print response data


def main():
    """Run multi-turn conversation test."""
    # Create session
    session = create_session()
    session_id = session["id"]

    # Test conversation
    test_inputs = [
        "Hello! What can you help me with?",
        "Tell me about your capabilities",
        "Can you search for restaurants in Paris?",
    ]

    for user_input in test_inputs:
        send_message(user_input, session_id)
        input("\nPress Enter to continue to next message...")

    print("\n✓ Test completed successfully")


if __name__ == "__main__":
    main()
```

## Example 3: Evaluation Test Suite

**File: `eval/test_eval.py`**

```python
"""Agent evaluation test suite."""
import pathlib
import dotenv
from google.adk.evaluation import AgentEvaluator
import pytest


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables for eval runs."""
    dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_greeting_flow():
    """Evaluate agent's greeting and introduction behavior."""
    await AgentEvaluator.evaluate(
        "my_agent",
        str(pathlib.Path(__file__).parent / "data/greeting.test.json"),
        num_runs=3
    )


@pytest.mark.asyncio
async def test_search_flow():
    """Evaluate agent's search and recommendation behavior."""
    await AgentEvaluator.evaluate(
        "my_agent",
        str(pathlib.Path(__file__).parent / "data/search.test.json"),
        num_runs=4
    )


@pytest.mark.asyncio
async def test_error_handling():
    """Evaluate agent's handling of invalid inputs."""
    await AgentEvaluator.evaluate(
        "my_agent",
        str(pathlib.Path(__file__).parent / "data/errors.test.json"),
        num_runs=2  # Deterministic error handling needs fewer runs
    )


@pytest.mark.asyncio
async def test_multi_turn_context():
    """Evaluate agent's ability to maintain context across turns."""
    await AgentEvaluator.evaluate(
        "my_agent",
        str(pathlib.Path(__file__).parent / "data/multi_turn.test.json"),
        num_runs=4
    )
```

## Example 4: Eval Data with Session State

**File: `eval/data/greeting.test.json`**

```json
{
  "eval_set_id": "greeting-flow-001",
  "name": "Agent Greeting Flow",
  "description": "Tests agent's initial greeting and capability explanation",
  "eval_cases": [
    {
      "eval_id": "greeting-001",
      "conversation": [
        {
          "invocation_id": "turn-1",
          "user_content": {
            "parts": [{"text": "Hello!"}],
            "role": "user"
          },
          "final_response": {
            "parts": [{"text": "Hello! I'm your assistant. I can help you search for places, make recommendations, and answer questions. What would you like to do today?"}],
            "role": "model"
          },
          "intermediate_data": {
            "tool_uses": [],
            "intermediate_responses": []
          },
          "creation_timestamp": 1234567890.0
        },
        {
          "invocation_id": "turn-2",
          "user_content": {
            "parts": [{"text": "What are my saved preferences?"}],
            "role": "user"
          },
          "final_response": {
            "parts": [{"text": "Based on your profile, you prefer vegetarian cuisine and have an interest in historical sites. Your home location is San Francisco."}],
            "role": "model"
          },
          "intermediate_data": {
            "tool_uses": [
              {
                "name": "get_user_preferences",
                "args": {"user_id": "test_user"}
              }
            ],
            "intermediate_responses": []
          },
          "creation_timestamp": 1234567891.0
        }
      ],
      "session_input": {
        "app_name": "",
        "user_id": "",
        "state": {
          "user_profile": {
            "name": "Test User",
            "home_location": "San Francisco, CA",
            "dietary_preferences": ["vegetarian"],
            "interests": ["history", "museums", "architecture"]
          }
        }
      },
      "creation_timestamp": 1234567890.0
    }
  ],
  "creation_timestamp": 1234567890.0
}
```

## Example 5: Session Loader with before_agent_callback

**File: `my_agent/tools/session_loader.py`**

```python
"""Session state loading utilities."""
import json
import os
from pathlib import Path
from google.adk.agents.callback_context import CallbackContext


# Default state file for development
DEFAULT_STATE_PATH = Path(__file__).parent.parent / "tests/default_state.json"


def load_initial_state(callback_context: CallbackContext) -> None:
    """
    Load initial session state from JSON file.

    Supports environment variable SCENARIO to load different states:
        SCENARIO=booking_complete adk api_server my_agent
        SCENARIO=first_visit adk api_server my_agent

    Args:
        callback_context: Callback context with session state
    """
    scenario = os.getenv("SCENARIO", "default")

    # Determine which state file to load
    if scenario == "default":
        state_path = DEFAULT_STATE_PATH
    else:
        state_path = Path(__file__).parent.parent / f"tests/scenarios/{scenario}.json"

    if not state_path.exists():
        print(f"[Session Loader] Warning: {state_path} not found, using empty state")
        return

    # Load and merge state
    with open(state_path, "r") as f:
        data = json.load(f)

    print(f"[Session Loader] Loading scenario: {scenario}")

    # Recursively merge state
    _merge_state(data.get("state", {}), callback_context.state)


def _merge_state(source: dict, target: dict) -> None:
    """
    Recursively merge source into target.

    Nested dicts are merged; other values are replaced.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            _merge_state(value, target[key])
        else:
            target[key] = value


def load_from_database(callback_context: CallbackContext) -> None:
    """
    Alternative: Load session from database.

    Useful for testing with production session snapshots.
    """
    from google.adk.sessions import DatabaseSessionService

    # Initialize database session service
    db_service = DatabaseSessionService(
        database_url=os.getenv("DATABASE_URL", "sqlite:///sessions.db")
    )

    session_id = callback_context.session.id
    user_id = callback_context.session.user_id
    app_name = callback_context.session.app_name

    # Try to load existing session
    existing = db_service.get_session_sync(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )

    if existing and existing.state:
        print(f"[Session Loader] Restored session {session_id} from database")
        callback_context.state.update(existing.state)
    else:
        print(f"[Session Loader] No existing session found, initializing")
        callback_context.state.update({
            "initialized_at": str(callback_context.session.create_time),
            "user_profile": {},
        })
```

**File: `tests/default_state.json`**

```json
{
  "state": {
    "user_profile": {
      "name": "Test User",
      "email": "test@example.com",
      "preferences": {
        "theme": "dark",
        "language": "en",
        "notifications": true
      }
    },
    "session_metadata": {
      "source": "test_suite",
      "environment": "development"
    }
  }
}
```

**File: `tests/scenarios/booking_complete.json`**

```json
{
  "scenario_id": "post-booking",
  "description": "User has completed a booking, testing follow-up interactions",
  "state": {
    "user_profile": {
      "name": "Test User",
      "email": "test@example.com"
    },
    "booking": {
      "status": "confirmed",
      "confirmation_code": "ABC123",
      "restaurant": {
        "name": "La Maison",
        "address": "123 Main St, Paris, France",
        "reservation_time": "2025-12-15T19:00:00Z",
        "party_size": 2
      }
    },
    "session_metadata": {
      "scenario": "post-booking",
      "test_mode": true
    }
  }
}
```

## Example 6: Agent with Session Loader

**File: `my_agent/agent.py`**

```python
"""Main agent configuration."""
from google.adk.agents import Agent
from my_agent.tools.session_loader import load_initial_state
from my_agent.tools.search import search_tool
from my_agent.tools.memory import memorize_tool


root_agent = Agent(
    model="gemini-2.5-flash",
    name="my_agent",
    description="Multi-purpose assistant with session state management",
    instruction="""You are a helpful assistant with access to user preferences
    and previous context. Use the session state to personalize responses and
    maintain context across conversations.""",
    tools=[
        search_tool,
        memorize_tool,
    ],
    before_agent_callback=load_initial_state,  # Load state before each conversation
)
```

## Example 7: pyproject.toml Configuration

**File: `pyproject.toml`**

```toml
[project]
name = "my-agent"
version = "0.1.0"
description = "ADK agent with comprehensive testing"
dependencies = [
    "google-adk>=1.0.0",
    "python-dotenv>=1.0.1",
]
requires-python = ">=3.10,<3.13"

[dependency-groups]
dev = [
    "pytest>=8.3.5",
    "google-adk[eval]>=1.16.0",
    "pytest-asyncio>=0.26.0",
]

[tool.pytest.ini_options]
pythonpath = "."
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests", "eval"]
python_files = ["test_*.py"]

markers = [
    "unit: Unit tests for tools",
    "eval: Agent evaluation tests",
    "slow: Tests that take significant time",
]

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = ["E501"]  # Line too long
```

## Running the Examples

```bash
# Install dependencies
pip install -e ".[dev]"

# Run unit tests
pytest tests/unit/ -v

# Start agent server for programmatic testing
adk api_server my_agent

# In another terminal: run programmatic test
python tests/programmatic_example.py

# Run evaluations
pytest eval/ -v

# Test with specific scenario
SCENARIO=booking_complete adk api_server my_agent

# Run all tests
pytest -v
```
