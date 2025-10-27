# CopilotKit + ADK Troubleshooting Guide

## Common Issues & Solutions

### 1. Agent Not Connecting

**Symptoms:**
- "Failed to connect to agent" error
- No responses in chat
- 404 or 500 errors in console

**Solutions:**

```bash
# Verify backend is running
curl http://localhost:8000/

# Test /run_sse endpoint (should return SSE stream)
curl -N http://localhost:8000/run_sse

# Check backend logs
# Should see FastAPI startup message and agent initialization
```

**Checklist:**
- ✅ Backend running on correct port (default: 8000)
- ✅ `add_adk_fastapi_endpoint` called in backend
- ✅ `HttpAgent` URL matches backend address
- ✅ No firewall blocking connection
- ✅ CORS configured if frontend/backend on different domains

---

### 2. State Not Syncing

**Symptoms:**
- UI doesn't update when agent modifies state
- Frontend state empty or outdated
- STATE_DELTA events not appearing

**Solutions:**

**Backend:**
```python
def my_tool(context, value: str):
    # ✅ Correct: Use context.state.set()
    context.state.set("key", value)

    # ❌ Wrong: Direct assignment won't sync
    # some_var = value  # Won't send STATE_DELTA

    return "Success"
```

**Frontend:**
```typescript
// ✅ Correct: Agent name must match runtime config
const { state } = useCoAgent<MyState>({
    name: "my_agent",  // Must match CopilotKit agent prop
    initialState: { key: "" },
});

// ❌ Wrong: Mismatched agent names
// Runtime config: agents: { my_agent: ... }
// Hook: useCoAgent({ name: "different_name" })  // Won't work!
```

**Checklist:**
- ✅ Agent name matches in `useCoAgent`, `CopilotKit`, and runtime
- ✅ Backend uses `context.state.set(key, value)` for updates
- ✅ Initial state structure matches backend state
- ✅ No type mismatches between frontend/backend state

---

### 3. Actions Not Rendering

**Symptoms:**
- Tool calls happen but no UI appears
- Generative UI components not displaying
- "Action not found" warnings

**Solutions:**

```typescript
// ✅ Correct: available="disabled" for backend-only tools
useCopilotAction({
    name: "search_web",  // Must exactly match ADK tool name
    available: "disabled",  // Don't let frontend trigger
    parameters: [
        { name: "query", type: "string", required: true }
    ],
    render: ({ args, status }) => {
        if (status === "executing") {
            return <Spinner />;
        }
        return <Results query={args.query} />;
    },
});

// ❌ Wrong: Name mismatch with backend
// Backend tool: "search_web"
// Frontend: name: "searchWeb"  // Won't match!
```

**Checklist:**
- ✅ Action `name` exactly matches backend tool name (case-sensitive)
- ✅ Set `available: "disabled"` for backend-only tools
- ✅ `render` function returns valid React elements
- ✅ Action registered before tool is called
- ✅ Component is client-side (`"use client"` directive)

---

### 4. CORS Errors

**Symptoms:**
- "CORS policy blocked" errors in console
- OPTIONS preflight requests failing
- Requests blocked despite backend running

**Solutions:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware BEFORE other routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        "http://localhost:3001",  # Alternative port
        "https://yourdomain.com"  # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Or ["GET", "POST"] for stricter control
    allow_headers=["*"],  # Or specific headers
)

# Then add your endpoints
add_adk_fastapi_endpoint(app, adk_agent, path="/")
```

**Production CORS:**
```python
import os

origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Checklist:**
- ✅ CORS middleware added to FastAPI app
- ✅ Frontend origin included in `allow_origins`
- ✅ `allow_credentials=True` if using cookies/auth
- ✅ Middleware added BEFORE route definitions

---

### 5. SSE Connection Drops

**Symptoms:**
- Connection closes after timeout
- "EventSource failed" errors
- Long operations interrupted

**Solutions:**

```python
# Increase session timeout for long operations
adk_agent = ADKAgent(
    adk_agent=my_agent,
    app_name="my_app",
    user_id="user_123",
    session_timeout_seconds=7200,  # 2 hours instead of default 1 hour
    use_in_memory_services=True
)
```

**Monitor Connection:**
```typescript
"use client";
import { useEffect } from "react";

export function ConnectionMonitor() {
    useEffect(() => {
        // Monitor SSE connection in browser DevTools
        // Network tab → Filter: EventStream
        console.log("CopilotKit mounted");
    }, []);

    return null;
}
```

**Checklist:**
- ✅ `session_timeout_seconds` sufficient for operations
- ✅ Network stable (check for proxy/firewall issues)
- ✅ Backend not crashing during processing
- ✅ Proper error handling in tools

---

### 6. TypeScript Type Errors

**Symptoms:**
- Type errors in `useCoAgent` or `useCopilotAction`
- "Property does not exist" warnings
- Strict mode compilation errors

**Solutions:**

```typescript
// Define strict types
type AppState = {
    items: string[];
    status: "idle" | "loading" | "complete";
    metadata?: Record<string, any>;
};

// Use with useCoAgent
const { state, setState } = useCoAgent<AppState>({
    name: "my_agent",
    initialState: {
        items: [],
        status: "idle",
    },
});

// Access with type safety
const firstItem = state.items[0];  // ✅ Type-safe
const status = state.status;       // ✅ Correctly typed
```

**Action Parameters:**
```typescript
useCopilotAction({
    name: "my_tool",
    available: "disabled",
    parameters: [
        {
            name: "query",
            type: "string",
            required: true,
            description: "Search query"
        },
        {
            name: "limit",
            type: "number",
            required: false,
            description: "Max results"
        }
    ] as const,  // Make readonly for better type inference
    render: ({ args }) => {
        // args is now typed correctly
        return <Results query={args.query} limit={args.limit} />;
    },
});
```

---

### 7. Styling Issues

**Symptoms:**
- Default styles not applying
- Components look unstyled
- CSS conflicts

**Solutions:**

```typescript
// ✅ Import CSS in layout.tsx
import "@copilotkit/react-ui/styles.css";

// Then customize with CSS variables
// styles/copilot-theme.css
:root {
    --copilot-kit-primary-color: #3b82f6;
    --copilot-kit-secondary-color: #10b981;
    --copilot-kit-background-color: #ffffff;
    --copilot-kit-text-color: #1f2937;
    --copilot-kit-border-radius: 8px;
}
```

**Check CSS Load Order:**
```typescript
// layout.tsx
import "@copilotkit/react-ui/styles.css";  // First
import "./globals.css";  // Then your globals
import "./copilot-theme.css";  // Then overrides
```

---

### 8. Environment Variables Not Loading

**Symptoms:**
- "API key not found" errors
- 401 authentication failures
- Undefined environment variables

**Solutions:**

**Next.js:**
```env
# .env.local
NEXT_PUBLIC_APP_URL=http://localhost:3000
ADK_AGENT_URL=http://localhost:8000/
GEMINI_API_KEY=your_key_here
```

**Access in Code:**
```typescript
// Client-side (requires NEXT_PUBLIC_ prefix)
const appUrl = process.env.NEXT_PUBLIC_APP_URL;

// Server-side (API routes, no prefix needed)
const agentUrl = process.env.ADK_AGENT_URL;
```

**Python:**
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not set")
```

**Checklist:**
- ✅ `.env.local` in project root (Next.js)
- ✅ Client-side vars use `NEXT_PUBLIC_` prefix
- ✅ Python uses `python-dotenv` and `load_dotenv()`
- ✅ Restart dev servers after changing .env

---

### 9. Build/Deployment Errors

**Symptoms:**
- Build fails with module errors
- "use client" directive errors
- Production deployment issues

**Solutions:**

**Next.js Build:**
```bash
# Clear cache and rebuild
rm -rf .next node_modules
npm install
npm run build
```

**Vercel Deployment:**
```bash
# Ensure environment variables set in Vercel dashboard
# Settings → Environment Variables
ADK_AGENT_URL=https://your-backend.com/
NEXT_PUBLIC_APP_URL=https://your-frontend.vercel.app
```

**Check Dependencies:**
```json
// package.json
{
  "dependencies": {
    "@copilotkit/react-ui": "latest",
    "@copilotkit/react-core": "latest",
    "@copilotkit/runtime": "latest",
    "react": "^18.0.0",  // Ensure React 18+
    "next": "^14.0.0"     // Ensure Next.js 14+
  }
}
```

---

### 10. Performance Issues

**Symptoms:**
- Slow responses
- UI lag during agent operations
- High memory usage

**Solutions:**

**Optimize State Updates:**
```python
# ❌ Avoid: Frequent small updates
for item in items:
    context.state.set("item", item)  # Sends many STATE_DELTA events

# ✅ Better: Batch updates
context.state.set("items", items)  # Single STATE_DELTA event
```

**Optimize Frontend:**
```typescript
// Memoize expensive renders
import { memo } from "react";

const ExpensiveComponent = memo(({ data }: Props) => {
    return <div>{/* Expensive render */}</div>;
});

// Debounce state updates
import { useMemo } from "react";

const { state } = useCoAgent<State>({
    name: "my_agent",
    initialState: { items: [] },
});

const sortedItems = useMemo(
    () => state.items.sort((a, b) => a.localeCompare(b)),
    [state.items]
);
```

**Backend Optimization:**
```python
# Use async operations
async def my_tool(context, query: str):
    result = await async_search(query)  # Non-blocking
    context.state.set("results", result)
    return result

# Connection pooling for databases
# Caching for repeated operations
```

---

## Debugging Tools

### Browser DevTools
1. **Network Tab**: Monitor `/run_sse` requests and SSE events
2. **Console Tab**: Check for JavaScript errors and logs
3. **React DevTools**: Inspect component state and props

### Backend Logging
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def my_tool(context, value: str):
    logger.debug(f"Tool called: {value}")
    context.state.set("result", value)
    logger.debug("State updated")
    return "Success"
```

### Frontend Debugging
```typescript
// Enable verbose logging
console.log("Agent state:", state);
console.log("Action args:", args);
console.log("Render status:", status);

// Monitor useEffect
useEffect(() => {
    console.log("State changed:", state);
}, [state]);
```

---

## Getting Help

- **CopilotKit Discord**: https://discord.gg/copilotkit
- **GitHub Issues**: https://github.com/CopilotKit/CopilotKit/issues
- **ADK Issues**: https://github.com/google/adk-python/issues
- **Documentation**: https://docs.copilotkit.ai/
