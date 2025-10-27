# AG-UI Protocol Reference

## Overview

**AG-UI** (Agent-to-UI) is an open protocol for real-time, structured communication between AI agent backends and frontend UIs.

**Transport**: HTTP Server-Sent Events (SSE) by default
**Endpoint**: `/run_sse` (created automatically by `add_adk_fastapi_endpoint`)

## Architecture

```
Frontend                Backend
--------                -------
User Input       POST
    ↓            --→    Agent receives request
CopilotKit UI          Agent processes with tools
    ↑            ←--
SSE Stream       SSE    Agent streams events:
    ↓                   - TEXT_MESSAGE_CONTENT
UI Updates             - TOOL_CALL_START
    ↓                   - TOOL_CALL_END
State Sync             - STATE_DELTA
```

## Event Types

### 1. TEXT_MESSAGE_CONTENT
**Purpose**: Stream message content to user
**Direction**: Backend → Frontend
**Usage**: Displayed in chat UI as agent responses

```python
# Backend automatically sends when agent generates text
# No manual implementation needed with ADK + ag_ui_adk
```

### 2. TOOL_CALL_START
**Purpose**: Notify UI that tool execution is beginning
**Direction**: Backend → Frontend
**Usage**: Display loading states, show "thinking" indicators

```typescript
// Frontend: Render function receives status
useCopilotAction({
    name: "my_tool",
    render: ({ args, status }) => {
        if (status === "executing") {
            return <Spinner>Calling {args.name}...</Spinner>;
        }
        return <Result />;
    },
});
```

### 3. TOOL_CALL_END
**Purpose**: Notify UI that tool execution completed
**Direction**: Backend → Frontend
**Usage**: Display results, update UI with tool outputs

```typescript
useCopilotAction({
    name: "my_tool",
    render: ({ args, status, result }) => {
        if (status === "complete") {
            return <SuccessCard result={result} />;
        }
        if (status === "error") {
            return <ErrorCard />;
        }
    },
});
```

### 4. STATE_DELTA
**Purpose**: Sync application state between backend and frontend
**Direction**: Backend → Frontend (bidirectional possible)
**Usage**: Keep UI in sync with agent's understanding of app state

**Backend (Python):**
```python
def update_items(context, items: list[str]):
    """Tool that updates application state."""
    # Send STATE_DELTA event to frontend
    context.state.set("items", items)
    context.state.set("status", "updated")
    return f"Updated {len(items)} items"
```

**Frontend (TypeScript):**
```typescript
const { state, setState } = useCoAgent<AppState>({
    name: "my_agent",
    initialState: { items: [], status: "idle" },
});

// state automatically updates when backend sends STATE_DELTA
// setState can also send updates to backend
```

## Connection Flow

### 1. Initial Connection
```
Frontend                    Backend
--------                    -------
POST /run_sse
  Body: {
    messages: [...],
    agent: "my_agent"
  }                        → Agent receives request
                           ← Opens SSE stream (200 OK)
```

### 2. Streaming Events
```
SSE Stream Events:
------------------
event: text_message_content
data: {"content": "Let me help you..."}

event: tool_call_start
data: {"tool": "search_web", "args": {...}}

event: tool_call_end
data: {"tool": "search_web", "result": {...}}

event: state_delta
data: {"key": "items", "value": [...]}

event: text_message_content
data: {"content": "I found 5 results"}
```

### 3. Connection Lifecycle
- **Timeout**: Configured via `session_timeout_seconds` in ADKAgent
- **Keep-Alive**: SSE maintains open connection
- **Reconnection**: Frontend automatically reconnects on disconnect
- **Cleanup**: Backend cleans up resources after timeout

## Implementation Notes

### Backend (Python/FastAPI)
```python
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

# ADKAgent wraps your ADK agent with AG-UI protocol
adk_agent = ADKAgent(
    adk_agent=my_llm_agent,
    app_name="my_app",
    user_id="user_123",
    session_timeout_seconds=3600,  # SSE timeout
    use_in_memory_services=True
)

# This creates /run_sse endpoint automatically
add_adk_fastapi_endpoint(
    app=fastapi_app,
    adk_agent=adk_agent,
    path="/"  # Endpoint at root: POST /run_sse
)
```

**Key Points:**
- No manual SSE implementation needed
- `add_adk_fastapi_endpoint` handles all protocol details
- Events sent automatically based on agent actions
- State updates via `context.state.set(key, value)`

### Frontend (React/Next.js)
```typescript
import { HttpAgent } from "@ag-ui/client";

const runtime = new CopilotRuntime({
    agents: {
        my_agent: new HttpAgent({
            url: "http://localhost:8000/",  // Your backend URL
        }),
    },
});
```

**Key Points:**
- `HttpAgent` handles SSE connection to `/run_sse`
- No manual SSE implementation needed
- Events automatically parsed and routed to hooks
- State updates automatically sync to `useCoAgent`

## Protocol Benefits

### 1. Real-Time Streaming
- Immediate feedback to users
- Progressive UI updates
- Reduced perceived latency

### 2. Structured Events
- Type-safe event handling
- Clear separation of concerns
- Easy to extend with custom events

### 3. Bidirectional Communication
- Frontend can send state updates
- Backend can push state changes
- Synchronized application state

### 4. Framework Agnostic
- Protocol works with any backend framework
- Not limited to Python/ADK
- Can implement in any language

## Debugging

### Monitor SSE Stream (Browser DevTools)
1. Open Network tab
2. Filter by "EventStream" or "SSE"
3. Click on `/run_sse` request
4. View "EventStream" tab for events

### Backend Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def my_tool(context, value: str):
    logger.debug(f"Tool called with value: {value}")
    context.state.set("result", value)
    logger.debug("State updated")
    return "Success"
```

### Frontend Debugging
```typescript
// Log all state updates
useEffect(() => {
    console.log("State updated:", state);
}, [state]);

// Log action renders
useCopilotAction({
    name: "my_tool",
    render: ({ args, status }) => {
        console.log("Action render:", { args, status });
        return <Component />;
    },
});
```

## Advanced: Custom Events

While AG-UI provides core events, you can extend with custom events:

```python
# Backend: Send custom event
context.emit_custom_event({
    "type": "custom_notification",
    "data": {"message": "Custom event"}
})
```

```typescript
// Frontend: Handle custom events
// (Requires custom event handler implementation)
```

## Security Considerations

- **Authentication**: Implement auth before `/run_sse` endpoint
- **Rate Limiting**: Prevent abuse of SSE connections
- **CORS**: Configure proper origins for production
- **Validation**: Validate all inputs before processing
- **Secrets**: Never expose API keys or secrets in state

## Performance

- **Connection Pooling**: Reuse connections when possible
- **Message Batching**: Batch state updates for efficiency
- **Compression**: Consider gzip for large payloads
- **Timeouts**: Set appropriate `session_timeout_seconds`
- **Resource Cleanup**: Properly close connections and clean resources

## Further Reading

- **AG-UI Spec**: https://www.copilotkit.ai/blog/introducing-ag-ui
- **SSE MDN**: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- **ADK Docs**: https://google.adk.dev/
