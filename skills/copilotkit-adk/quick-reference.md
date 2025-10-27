# CopilotKit + ADK Quick Reference

## Installation

### Backend (Python)
```bash
pip install ag_ui_adk uvicorn fastapi google-adk
```

### Frontend (React/Next.js)
```bash
npm install @copilotkit/react-ui @copilotkit/react-core @copilotkit/runtime
```

## Minimal Backend Setup

```python
from google.adk.agents import LlmAgent
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
import uvicorn

# 1. Define agent
agent = LlmAgent(
    name="MyAgent",
    model="gemini-2.5-flash",
    instruction="Your instructions",
    tools=[my_tool]
)

# 2. Wrap with AG-UI
adk_agent = ADKAgent(
    adk_agent=agent,
    app_name="my_app",
    user_id="user_123",
    session_timeout_seconds=3600,
    use_in_memory_services=True
)

# 3. Expose endpoint
app = FastAPI()
add_adk_fastapi_endpoint(app, adk_agent, path="/")

# 4. Run
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Minimal Frontend Setup

### 1. Runtime (`app/api/copilotkit/route.ts`)
```typescript
import { CopilotRuntime, ExperimentalEmptyAdapter } from "@copilotkit/runtime";
import { copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

const runtime = new CopilotRuntime({
    agents: {
        my_agent: new HttpAgent({ url: "http://localhost:8000/" }),
    },
});

export const POST = async (req: NextRequest) => {
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
        runtime,
        serviceAdapter: new ExperimentalEmptyAdapter(),
        endpoint: "/api/copilotkit",
    });
    return handleRequest(req);
};
```

### 2. Provider (`app/layout.tsx`)
```typescript
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";

export default function RootLayout({ children }) {
    return (
        <html>
            <body>
                <CopilotKit runtimeUrl="/api/copilotkit" agent="my_agent">
                    {children}
                </CopilotKit>
            </body>
        </html>
    );
}
```

### 3. UI Component (`app/page.tsx`)
```typescript
"use client";
import { CopilotSidebar } from "@copilotkit/react-ui";

export default function Page() {
    return (
        <main>
            <YourContent />
            <CopilotSidebar defaultOpen={true} />
        </main>
    );
}
```

## Essential Hooks

### State Sync
```typescript
import { useCoAgent } from "@copilotkit/react-core";

const { state, setState } = useCoAgent<MyState>({
    name: "my_agent",
    initialState: { items: [] },
});
```

### Generative UI
```typescript
import { useCopilotAction } from "@copilotkit/react-core";

useCopilotAction({
    name: "tool_name",  // Must match ADK tool
    available: "disabled",  // Backend-only
    parameters: [{ name: "param", type: "string", required: true }],
    render: ({ args, status }) => <YourComponent {...args} />,
});
```

## AG-UI Protocol Events

| Event | Description | Direction |
|-------|-------------|-----------|
| `TEXT_MESSAGE_CONTENT` | Message content | Backend → Frontend |
| `TOOL_CALL_START` | Tool execution begins | Backend → Frontend |
| `TOOL_CALL_END` | Tool execution completes | Backend → Frontend |
| `STATE_DELTA` | State update patch | Backend → Frontend |

## State Updates (Backend)

```python
def my_tool(context, value: str):
    """Update application state from backend."""
    context.state.set("key", value)
    return "Success"
```

## Common Patterns

### Multi-Agent Setup
```typescript
const runtime = new CopilotRuntime({
    agents: {
        agent1: new HttpAgent({ url: "http://localhost:8001/" }),
        agent2: new HttpAgent({ url: "http://localhost:8002/" }),
    },
});
```

### Custom Styling
```css
:root {
    --copilot-kit-primary-color: #3b82f6;
    --copilot-kit-background-color: #ffffff;
}
```

### Environment Variables
```env
ADK_AGENT_URL=http://localhost:8000/
GEMINI_API_KEY=your_key_here
```

## Component Comparison

| Component | Use Case | Position |
|-----------|----------|----------|
| `CopilotSidebar` | Always-available assistant | Side panel |
| `CopilotPopup` | Optional AI feature | Modal/overlay |
| `CopilotChat` | AI-first experience | Full page |

## Running the Stack

```bash
# Terminal 1: Backend
cd backend && python agent.py  # :8000

# Terminal 2: Frontend
cd frontend && npm run dev     # :3000
```

## Quick Bootstrap

```bash
npx copilotkit@latest create -f adk
```
