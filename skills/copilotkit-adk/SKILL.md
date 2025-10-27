---
name: "copilotkit-adk"
description: "Expert assistance with CopilotKit React UI components integrated with Google ADK agents via AG-UI protocol. Use when building frontend interfaces for ADK agents, implementing chat UIs, setting up AG-UI streaming endpoints, managing agent state synchronization, or creating generative UI components. Specializes in the AG-UI /run_sse protocol bridge between React and Python ADK backends."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - WebFetch
  - mcp__context7__resolve-library-id
  - mcp__context7__get-library-docs
---

# CopilotKit React UI + Google ADK Integration Skill

You are now operating as a CopilotKit + Google ADK specialist. Your expertise covers building React frontends for ADK agents using CopilotKit's UI components and the AG-UI protocol for real-time streaming communication.

## Core Architecture

**Stack Overview:**
- **Backend**: Google ADK (Python) - Agent logic, tools, multi-step reasoning
- **Bridge**: AG-UI Protocol - Event-based streaming over SSE (/run_sse endpoint)
- **Frontend**: CopilotKit React UI - Chat components, state sync, generative UI
- **Transport**: HTTP Server-Sent Events (SSE) for real-time bidirectional communication

**Communication Flow:**
```
User → CopilotKit UI → /api/copilotkit → HttpAgent → ADK /run_sse → Agent
                                                            ↓
User ← CopilotKit UI ← AG-UI Events ← SSE Stream ← ADK Agent
```

## 1. Backend Setup (Python/FastAPI)

### Required Dependencies
```bash
pip install ag_ui_adk uvicorn fastapi google-adk
```

### ADK Agent Configuration
```python
from google.adk.agents import LlmAgent

# Define your ADK agent
my_agent = LlmAgent(
    name="MyAgent",
    model="gemini-2.5-flash",
    instruction="""Your agent instructions here.
    Explain how to use tools and interact with users.""",
    tools=[tool1, tool2],  # Your ADK tools
    before_agent_callback=on_before_agent,
    after_model_callback=on_after_model
)
```

### Wrap with AG-UI Middleware
```python
from ag_ui_adk import ADKAgent

adk_agent = ADKAgent(
    adk_agent=my_agent,
    app_name="my_app",
    user_id="user_123",  # Can be dynamic
    session_timeout_seconds=3600,
    use_in_memory_services=True  # Or use persistent storage
)
```

### Expose via FastAPI (/run_sse endpoint)
```python
from fastapi import FastAPI
from ag_ui_adk import add_adk_fastapi_endpoint
import uvicorn

app = FastAPI(title="ADK Agent API")

# This creates the /run_sse endpoint automatically
add_adk_fastapi_endpoint(
    app=app,
    adk_agent=adk_agent,
    path="/"  # Creates endpoint at root or specify custom path
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Key Points:**
- `add_adk_fastapi_endpoint` automatically creates the `/run_sse` streaming endpoint
- The endpoint handles AG-UI protocol events (TEXT_MESSAGE_CONTENT, TOOL_CALL_START, TOOL_CALL_END, STATE_DELTA)
- SSE transport enables real-time streaming of agent responses

## 2. Frontend Setup (React/Next.js)

### Required Dependencies
```bash
npm install @copilotkit/react-ui @copilotkit/react-core @copilotkit/runtime
```

### Project Structure (Next.js App Router)
```
app/
├── api/
│   └── copilotkit/
│       └── route.ts          # CopilotKit runtime endpoint
├── layout.tsx                 # CopilotKit provider wrapper
└── page.tsx                   # Main UI with chat components
```

### 2.1 CopilotKit Runtime Setup (`app/api/copilotkit/route.ts`)

```typescript
import { CopilotRuntime, ExperimentalEmptyAdapter } from "@copilotkit/runtime";
import { copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

// Configure the runtime with your ADK agent
const runtime = new CopilotRuntime({
    agents: {
        my_agent: new HttpAgent({
            url: process.env.ADK_AGENT_URL || "http://localhost:8000/",
        }),
    },
});

// Create Next.js API route handler
export const POST = async (req: NextRequest) => {
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
        runtime,
        serviceAdapter: new ExperimentalEmptyAdapter(),
        endpoint: "/api/copilotkit",
    });
    return handleRequest(req);
};
```

**Key Configuration:**
- `HttpAgent` connects to your ADK backend's `/run_sse` endpoint
- `ExperimentalEmptyAdapter` used when backend handles all logic
- Multiple agents can be configured in the `agents` object

### 2.2 Provider Setup (`app/layout.tsx`)

```typescript
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";

export default function RootLayout({
    children
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body>
                <CopilotKit
                    runtimeUrl="/api/copilotkit"
                    agent="my_agent"  // Must match runtime config
                >
                    {children}
                </CopilotKit>
            </body>
        </html>
    );
}
```

**Provider Props:**
- `runtimeUrl`: Your CopilotKit API endpoint
- `agent`: Agent name from runtime configuration
- All children can now use CopilotKit hooks

## 3. React UI Components

### 3.1 CopilotSidebar (Recommended for ADK)

```typescript
"use client";
import { CopilotSidebar } from "@copilotkit/react-ui";

export default function Page() {
    return (
        <main className="flex h-screen">
            <div className="flex-1">
                {/* Your main application content */}
                <YourMainContent />
            </div>

            <CopilotSidebar
                defaultOpen={true}
                instructions="You are an AI assistant. Help users accomplish their goals."
                labels={{
                    title: "AI Assistant",
                    initial: "Hi! How can I help you today?",
                    placeholder: "Ask me anything...",
                }}
                onSubmitMessage={(message) => {
                    console.log("User sent:", message);
                }}
            />
        </main>
    );
}
```

### 3.2 CopilotPopup (Non-intrusive)

```typescript
"use client";
import { CopilotPopup } from "@copilotkit/react-ui";

export default function Page() {
    return (
        <main>
            <YourMainContent />

            <CopilotPopup
                instructions="You are an AI assistant."
                labels={{
                    title: "AI Assistant",
                    initial: "Hi! How can I help?",
                }}
                defaultOpen={false}  // Opens on icon click
            />
        </main>
    );
}
```

### 3.3 CopilotChat (Full-featured)

```typescript
"use client";
import { CopilotChat } from "@copilotkit/react-ui";

export default function Page() {
    return (
        <div className="flex flex-col h-screen">
            <header>{/* Your header */}</header>

            <div className="flex-1 overflow-hidden">
                <CopilotChat
                    instructions="You are an AI assistant specialized in..."
                    labels={{
                        title: "Chat Assistant",
                        initial: "Welcome! What would you like to know?",
                        placeholder: "Type your message...",
                    }}
                />
            </div>
        </div>
    );
}
```

**Component Comparison:**
- **CopilotSidebar**: Persistent side panel, best for always-available assistance
- **CopilotPopup**: Modal dialog, best for optional/supplementary AI features
- **CopilotChat**: Full-page chat, best for AI-first experiences

## 4. State Synchronization with useCoAgent

### Frontend State Hook

```typescript
"use client";
import { useCoAgent } from "@copilotkit/react-core";

type AgentState = {
    items: string[];
    status: string;
    metadata?: Record<string, any>;
};

export default function YourMainContent() {
    const { state, setState } = useCoAgent<AgentState>({
        name: "my_agent",  // Must match agent name
        initialState: {
            items: [],
            status: "idle",
        },
    });

    // State updates automatically when agent sends STATE_DELTA events
    return (
        <div>
            <h2>Status: {state.status}</h2>
            <ul>
                {state.items?.map((item, i) => (
                    <li key={i}>{item}</li>
                ))}
            </ul>

            <button onClick={() => setState({ status: "processing" })}>
                Update State
            </button>
        </div>
    );
}
```

### Backend State Updates (Python/ADK)

```python
from google.adk.agents import LlmAgent

def my_tool(context, items: list[str]):
    """Tool that updates application state."""

    # Update state via context
    context.state.set("items", items)
    context.state.set("status", "completed")

    return f"Updated {len(items)} items"

my_agent = LlmAgent(
    name="MyAgent",
    model="gemini-2.5-flash",
    tools=[my_tool],
)
```

**AG-UI Protocol Events:**
- `STATE_DELTA`: Sent when backend updates state
- `TEXT_MESSAGE_CONTENT`: Sent for message content
- `TOOL_CALL_START`/`TOOL_CALL_END`: Tool execution lifecycle

## 5. Generative UI with useCopilotAction

### Render Tool Calls in UI

```typescript
"use client";
import { useCopilotAction } from "@copilotkit/react-core";

export function WeatherWidget() {
    useCopilotAction({
        name: "get_weather",  // Must match ADK tool name
        description: "Get weather information for a location",
        available: "disabled",  // Don't let frontend trigger, only render
        parameters: [
            {
                name: "location",
                type: "string",
                required: true,
                description: "City name or zip code"
            },
        ],
        render: ({ args, status }) => {
            if (status === "executing") {
                return <div>Loading weather for {args.location}...</div>;
            }

            return (
                <div className="weather-card">
                    <h3>Weather: {args.location}</h3>
                    {/* Render weather data */}
                </div>
            );
        },
    });

    return null;  // Component just registers the action
}
```

### Handling Multiple Actions

```typescript
export function ActionRegistry() {
    // Weather action
    useCopilotAction({
        name: "get_weather",
        description: "Get weather for a location",
        available: "disabled",
        parameters: [{ name: "location", type: "string", required: true }],
        render: ({ args }) => <WeatherCard location={args.location} />,
    });

    // Search action
    useCopilotAction({
        name: "search_web",
        description: "Search the web",
        available: "disabled",
        parameters: [{ name: "query", type: "string", required: true }],
        render: ({ args, result }) => (
            <SearchResults query={args.query} results={result} />
        ),
    });

    // Calendar action
    useCopilotAction({
        name: "create_event",
        description: "Create calendar event",
        available: "disabled",
        parameters: [
            { name: "title", type: "string", required: true },
            { name: "date", type: "string", required: true },
        ],
        render: ({ args }) => (
            <EventPreview title={args.title} date={args.date} />
        ),
    });

    return null;
}
```

**Action Props:**
- `name`: Must match ADK tool name exactly
- `available: "disabled"`: Prevents frontend triggering (backend-only)
- `render`: React component to display when tool is called
- `status`: "executing" | "complete" | "error"

## 6. Advanced Patterns

### 6.1 Custom Message Components

```typescript
import { CopilotSidebar } from "@copilotkit/react-ui";

function CustomAssistantMessage({ message }: { message: string }) {
    return (
        <div className="bg-blue-100 p-4 rounded-lg">
            <div className="font-semibold">AI Assistant</div>
            <div>{message}</div>
        </div>
    );
}

export default function Page() {
    return (
        <CopilotSidebar
            AssistantMessage={CustomAssistantMessage}
            instructions="..."
        />
    );
}
```

### 6.2 Auto-open Chat with Query Param

```typescript
"use client";
import { useSearchParams } from "next/navigation";
import { CopilotSidebar } from "@copilotkit/react-ui";

export default function Page() {
    const searchParams = useSearchParams();
    const shouldOpen = searchParams.get("openCopilot") === "true";

    return (
        <CopilotSidebar
            defaultOpen={shouldOpen}
            instructions="..."
        />
    );
}
```

Usage: `https://yourapp.com/?openCopilot=true`

### 6.3 CSS Custom Properties

```css
/* styles/copilot-theme.css */
:root {
    --copilot-kit-primary-color: #3b82f6;
    --copilot-kit-secondary-color: #10b981;
    --copilot-kit-background-color: #ffffff;
    --copilot-kit-text-color: #1f2937;
    --copilot-kit-border-radius: 8px;
}
```

### 6.4 Environment Configuration

```env
# .env.local
ADK_AGENT_URL=http://localhost:8000/
GEMINI_API_KEY=your_gemini_api_key
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 6.5 Multi-Agent Setup

```typescript
// app/api/copilotkit/route.ts
const runtime = new CopilotRuntime({
    agents: {
        research_agent: new HttpAgent({
            url: "http://localhost:8001/",
        }),
        writer_agent: new HttpAgent({
            url: "http://localhost:8002/",
        }),
        reviewer_agent: new HttpAgent({
            url: "http://localhost:8003/",
        }),
    },
});
```

```typescript
// app/layout.tsx - Switch agents dynamically
const [currentAgent, setCurrentAgent] = useState("research_agent");

<CopilotKit runtimeUrl="/api/copilotkit" agent={currentAgent}>
    {children}
</CopilotKit>
```

## 7. Complete Example: Proverbs App

### Backend (`backend/agent.py`)

```python
from google.adk.agents import LlmAgent
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
import uvicorn

def set_proverbs(context, proverbs: list[str]):
    """Set a list of proverbs in the application state."""
    context.state.set("proverbs", proverbs)
    return f"Set {len(proverbs)} proverbs successfully"

proverbs_agent = LlmAgent(
    name="ProverbsAgent",
    model="gemini-2.5-flash",
    instruction="""When users ask about proverbs, use the set_proverbs
    tool to store a comprehensive list of relevant proverbs.""",
    tools=[set_proverbs],
)

adk_agent = ADKAgent(
    adk_agent=proverbs_agent,
    app_name="proverbs_app",
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True
)

app = FastAPI(title="Proverbs Agent")
add_adk_fastapi_endpoint(app, adk_agent, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Frontend (`app/page.tsx`)

```typescript
"use client";
import { useCoAgent } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { useCopilotAction } from "@copilotkit/react-core";

type AgentState = {
    proverbs: string[];
};

export default function ProverbsPage() {
    const { state } = useCoAgent<AgentState>({
        name: "my_agent",
        initialState: { proverbs: [] },
    });

    // Register generative UI for set_proverbs tool
    useCopilotAction({
        name: "set_proverbs",
        description: "Set proverbs",
        available: "disabled",
        parameters: [
            { name: "proverbs", type: "array", required: true }
        ],
        render: ({ args, status }) => {
            if (status === "executing") {
                return <div>Setting proverbs...</div>;
            }
            return (
                <div className="success-message">
                    ✅ Set {args.proverbs.length} proverbs
                </div>
            );
        },
    });

    return (
        <main className="flex h-screen">
            <div className="flex-1 p-8">
                <h1 className="text-3xl font-bold mb-4">Proverbs Collection</h1>

                {state.proverbs.length === 0 ? (
                    <p className="text-gray-500">
                        Ask the AI for proverbs to get started!
                    </p>
                ) : (
                    <ul className="space-y-2">
                        {state.proverbs.map((proverb, i) => (
                            <li key={i} className="p-3 bg-gray-100 rounded">
                                {proverb}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <CopilotSidebar
                defaultOpen={true}
                instructions="You are a proverbs expert. Share wisdom with users."
                labels={{
                    title: "Proverbs Assistant",
                    initial: "Ask me for proverbs from any culture!",
                    placeholder: "E.g., 'Give me Chinese proverbs about wisdom'",
                }}
            />
        </main>
    );
}
```

## 8. Troubleshooting

### Common Issues

**1. Agent not connecting**
```bash
# Check backend is running
curl http://localhost:8000/

# Verify /run_sse endpoint exists
curl -N http://localhost:8000/run_sse
```

**2. State not syncing**
- Ensure agent name matches in `useCoAgent` and `CopilotKit` provider
- Check backend is sending STATE_DELTA events
- Verify state updates in context: `context.state.set(key, value)`

**3. Actions not rendering**
- Action name must exactly match ADK tool name
- Set `available: "disabled"` for backend-only tools
- Check `render` function returns valid React elements

**4. CORS errors**
```python
# Add CORS middleware to FastAPI
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**5. SSE connection drops**
- Check `session_timeout_seconds` in ADKAgent config
- Monitor network tab for connection status
- Increase timeout for long-running operations

## 9. Best Practices

### Frontend
✅ Use `"use client"` directive for all CopilotKit hooks
✅ Import CSS: `import "@copilotkit/react-ui/styles.css"`
✅ Set `available: "disabled"` for backend-only actions
✅ Register actions early in component lifecycle
✅ Use TypeScript for type-safe state management
✅ Handle loading states in render functions

### Backend
✅ Always close resources in FastAPI lifecycle
✅ Use persistent services for production (not `use_in_memory_services`)
✅ Implement proper error handling in tools
✅ Send STATE_DELTA events for all state changes
✅ Use meaningful tool names that match frontend expectations
✅ Add proper CORS configuration

### AG-UI Protocol
✅ Backend exposes `/run_sse` endpoint via `add_adk_fastapi_endpoint`
✅ Frontend connects via `HttpAgent` in CopilotRuntime
✅ SSE handles bidirectional streaming automatically
✅ Events: TEXT_MESSAGE_CONTENT, TOOL_CALL_*, STATE_DELTA

## 10. Quick Start Commands

```bash
# Bootstrap full-stack project
npx copilotkit@latest create -f adk

# Backend setup
cd backend
pip install -r requirements.txt
python agent.py  # Runs on :8000

# Frontend setup
cd frontend
npm install
npm run dev  # Runs on :3000
```

## 11. Resources & Documentation

- **CopilotKit Docs**: https://docs.copilotkit.ai/
- **AG-UI Protocol**: https://www.copilotkit.ai/blog/introducing-ag-ui
- **Google ADK**: https://google.adk.dev/
- **Examples**: https://github.com/CopilotKit/CopilotKit/tree/main/examples

---

You are now ready to build sophisticated React frontends for Google ADK agents using CopilotKit and the AG-UI protocol. Focus on seamless integration patterns, real-time state synchronization, and rich generative UI experiences.
