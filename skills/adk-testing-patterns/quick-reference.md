# ADK Testing Quick Reference

## Common Test Commands

```bash
# Unit tests only
pytest tests/unit/ -v

# All evaluations
pytest eval/ -v

# Specific eval scenario
pytest eval/test_eval.py::test_scenario_name -v

# With detailed output
pytest -v -s

# Run with specific scenario loaded
SCENARIO=after_booking adk api_server your_package

# Start agent server for programmatic tests
adk api_server your_package

# Run programmatic integration test
python tests/programmatic_example.py
```

## Minimal Unit Test Template

```python
import unittest
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from your_package.agent import root_agent
from your_package.tools.your_tool import your_tool


session_service = InMemorySessionService()


class TestYourTools(unittest.TestCase):
    def setUp(self):
        self.session = session_service.create_session_sync(
            app_name="TestApp", user_id="test_user"
        )
        self.invoc_context = InvocationContext(
            session_service=session_service,
            invocation_id="TEST_ID",
            agent=root_agent,
            session=self.session,
        )
        self.tool_context = ToolContext(invocation_context=self.invoc_context)

    def test_your_tool(self):
        result = your_tool(param="value", tool_context=self.tool_context)
        self.assertIn("expected_key", result)
        self.assertEqual(self.tool_context.state["key"], "expected_value")
```

## Minimal Eval Test Template

```python
import pathlib
import dotenv
from google.adk.evaluation import AgentEvaluator
import pytest


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_scenario():
    await AgentEvaluator.evaluate(
        "your_package",
        str(pathlib.Path(__file__).parent / "data/scenario.test.json"),
        num_runs=4
    )
```

## Minimal before_agent_callback

```python
import json
from pathlib import Path
from google.adk.agents.callback_context import CallbackContext

STATE_FILE = Path(__file__).parent / "initial_state.json"


def load_initial_state(callback_context: CallbackContext) -> None:
    with open(STATE_FILE, "r") as f:
        data = json.load(f)
    callback_context.state.update(data.get("state", {}))
```

## Session State JSON Structure

```json
{
  "state": {
    "user_profile": {},
    "session_context": {},
    "custom_data": {}
  }
}
```

## Eval Data JSON Structure

```json
{
  "eval_set_id": "unique-id",
  "name": "Scenario Name",
  "eval_cases": [
    {
      "conversation": [
        {
          "user_content": {"parts": [{"text": "User message"}], "role": "user"},
          "final_response": {"parts": [{"text": "Expected response"}], "role": "model"},
          "intermediate_data": {
            "tool_uses": [{"name": "tool_name", "args": {}}]
          }
        }
      ],
      "session_input": {
        "state": {"initial": "state"}
      }
    }
  ]
}
```

## pyproject.toml Minimal Config

```toml
[tool.pytest.ini_options]
pythonpath = "."
asyncio_default_fixture_loop_scope = "function"

[dependency-groups]
dev = [
    "pytest>=8.3.5",
    "google-adk[eval]>=1.16.0",
    "pytest-asyncio>=0.26.0",
]
```
