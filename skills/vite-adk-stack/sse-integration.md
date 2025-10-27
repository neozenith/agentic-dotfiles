# SSE Integration Guide for Google ADK

Complete guide for implementing Server-Sent Events (SSE) streaming with Google ADK in vanilla JavaScript.

## Overview

This project uses **vanilla SSE implementation** (no CopilotKit) for real-time communication with Google ADK agents. The implementation handles:
- Session management
- SSE stream processing
- Line buffering
- Event parsing
- State accumulation
- Retry logic

## Architecture

```
Frontend                    Backend (ADK)
--------                    -------------
User Input    POST /api/run_sse
    ↓         -------------→    Agent receives message
createSession                   Agent processes with tools
    ↓         ←-------------
SSE Stream    SSE Events        Agent streams responses:
    ↓                           - text parts
processSseEventData             - agent name
    ↓                           - state deltas (images, videos)
updateMessages
    ↓
UI Updates
```

## 1. Session Management

### Create Session

```typescript
const createSession = async (): Promise<{
  userId: string,
  sessionId: string,
  appName: string
}> => {
  const generatedSessionId = crypto.randomUUID();

  const response = await fetch(
    `/api/apps/app/users/u_999/sessions/${generatedSessionId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status}`);
  }

  const data = await response.json();
  return {
    userId: data.userId,
    sessionId: data.id,
    appName: data.appName
  };
};
```

### Session State Management

```typescript
const [userId, setUserId] = useState<string | null>(null);
const [sessionId, setSessionId] = useState<string | null>(null);
const [appName, setAppName] = useState<string | null>(null);

// Create session if needed
if (!sessionId || !userId || !appName) {
  const sessionData = await retryWithBackoff(createSession);
  setUserId(sessionData.userId);
  setSessionId(sessionData.sessionId);
  setAppName(sessionData.appName);
}
```

## 2. SSE Stream Processing

### Send Message and Open Stream

```typescript
const handleSubmit = async (input: string) => {
  const response = await fetch("/api/run_sse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      appName: currentAppName,
      userId: currentUserId,
      sessionId: currentSessionId,
      newMessage: {
        parts: [{ text: input }],
        role: "user"
      },
      streaming: false
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.status}`);
  }

  // Process SSE stream
  await processSSEStream(response, aiMessageId);
};
```

### Line Buffering Implementation

**Critical**: SSE data can arrive in chunks. Must buffer partial lines.

```typescript
const reader = response.body?.getReader();
const decoder = new TextDecoder();
let lineBuffer = "";         // Buffer for incomplete lines
let eventDataBuffer = "";    // Buffer for multi-line SSE events

while (true) {
  const { done, value } = await reader.read();

  // Add new data to line buffer
  if (value) {
    lineBuffer += decoder.decode(value, { stream: true });
  }

  // Process complete lines
  let eolIndex;
  while ((eolIndex = lineBuffer.indexOf('\n')) >= 0 || (done && lineBuffer.length > 0)) {
    let line: string;

    if (eolIndex >= 0) {
      // Extract complete line
      line = lineBuffer.substring(0, eolIndex);
      lineBuffer = lineBuffer.substring(eolIndex + 1);
    } else {
      // Final line without \n
      line = lineBuffer;
      lineBuffer = "";
    }

    // Process SSE line
    processSSELine(line);
  }

  if (done) {
    // Handle any remaining buffered data
    if (eventDataBuffer.length > 0) {
      processFinalEvent(eventDataBuffer);
    }
    break;
  }
}
```

### SSE Line Processing

```typescript
const processSSELine = (line: string) => {
  // Empty line = event complete
  if (line.trim() === "") {
    if (eventDataBuffer.length > 0) {
      // Remove trailing newline if present
      const jsonData = eventDataBuffer.endsWith('\n')
        ? eventDataBuffer.slice(0, -1)
        : eventDataBuffer;

      console.log('[SSE EVENT]:', jsonData.substring(0, 200) + "...");
      processSseEventData(jsonData, aiMessageId);
      eventDataBuffer = "";
    }
  }
  // SSE data line
  else if (line.startsWith('data:')) {
    // Accumulate data (may be multi-line JSON)
    eventDataBuffer += line.substring(5).trimStart() + '\n';
  }
  // SSE comment line (ignore)
  else if (line.startsWith(':')) {
    // Comment, do nothing
  }
};
```

## 3. Event Data Extraction

### Parse SSE Event JSON

```typescript
const extractDataFromSSE = (data: string) => {
  try {
    const parsed = JSON.parse(data);
    console.log('[SSE PARSED]:', JSON.stringify(parsed, null, 2));

    let textParts: string[] = [];
    let agent = '';
    let storyboard = null;
    let videoClips = null;
    let finalVideo = null;

    // Extract text content
    if (parsed.content?.parts) {
      textParts = parsed.content.parts
        .filter((part: any) => part.text)
        .map((part: any) => part.text);
    }

    // Extract agent name
    if (parsed.author) {
      agent = parsed.author;
      console.log('[SSE] Agent:', agent);
    }

    // Extract state deltas (agent outputs)
    if (parsed.actions?.stateDelta) {
      storyboard = parsed.actions.stateDelta.storyboard_images;
      videoClips = parsed.actions.stateDelta.video_clips;
      finalVideo = parsed.actions.stateDelta.final_video_uri;
    }

    return { textParts, agent, storyboard, videoClips, finalVideo };
  } catch (error) {
    console.error('Error parsing SSE data:', error);
    return {
      textParts: [],
      agent: '',
      storyboard: null,
      videoClips: null,
      finalVideo: null
    };
  }
};
```

### Process Extracted Data

```typescript
const processSseEventData = (jsonData: string, aiMessageId: string) => {
  const { textParts, agent, storyboard, videoClips, finalVideo } =
    extractDataFromSSE(jsonData);

  // Track current agent
  if (agent && agent !== currentAgentRef.current) {
    currentAgentRef.current = agent;
  }

  // Accumulate text
  if (textParts.length > 0) {
    for (const text of textParts) {
      accumulatedTextRef.current += text + " ";

      // Update message with accumulated text
      setMessages(prev => prev.map(msg =>
        msg.id === aiMessageId
          ? {
              ...msg,
              content: accumulatedTextRef.current.trim(),
              agent: currentAgentRef.current || msg.agent
            }
          : msg
      ));
    }
  }

  // Update state deltas (images, videos, etc.)
  if (storyboard) {
    setMessages(prev => prev.map(msg =>
      msg.id === aiMessageId ? { ...msg, storyboard } : msg
    ));
  }

  if (videoClips) {
    setMessages(prev => prev.map(msg =>
      msg.id === aiMessageId ? { ...msg, videoClips } : msg
    ));
  }

  if (finalVideo) {
    setMessages(prev => prev.map(msg =>
      msg.id === aiMessageId ? { ...msg, finalVideo } : msg
    ));
  }
};
```

## 4. State Management

### Using Refs for Non-UI State

```typescript
// Use refs for values that shouldn't trigger re-renders
const currentAgentRef = useRef('');
const accumulatedTextRef = useRef("");

// Reset on new message
const aiMessageId = Date.now().toString() + "_ai";
currentAgentRef.current = '';
accumulatedTextRef.current = '';
```

### Message State Structure

```typescript
interface MessageWithAgent {
  type: "human" | "ai";
  content: string;
  id: string;
  agent?: string;
  storyboard?: any[];
  videoClips?: string[];
  finalVideo?: string;
}

const [messages, setMessages] = useState<MessageWithAgent[]>([]);

// Add user message
setMessages(prev => [...prev, {
  type: "human",
  content: input,
  id: userMessageId
}]);

// Add AI message (initially empty)
setMessages(prev => [...prev, {
  type: "ai",
  content: "",
  id: aiMessageId,
  agent: '',
}]);

// Update AI message as data arrives
setMessages(prev => prev.map(msg =>
  msg.id === aiMessageId
    ? { ...msg, content: newContent, agent: newAgent }
    : msg
));
```

## 5. Retry Logic

### Exponential Backoff

```typescript
const retryWithBackoff = async (
  fn: () => Promise<any>,
  maxRetries: number = 10,
  maxDuration: number = 120000
): Promise<any> => {
  const startTime = Date.now();
  let lastError: Error;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    // Check timeout
    if (Date.now() - startTime > maxDuration) {
      throw new Error(`Retry timeout after ${maxDuration}ms`);
    }

    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;

      // Calculate exponential backoff delay (cap at 5s)
      const delay = Math.min(1000 * Math.pow(2, attempt), 5000);

      console.log(
        `Attempt ${attempt + 1} failed, retrying in ${delay}ms...`,
        error
      );

      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError!;
};
```

### Usage

```typescript
// Retry session creation
const sessionData = await retryWithBackoff(createSession);

// Retry message sending
const response = await retryWithBackoff(sendMessage);
```

## 6. Backend Health Check

### Health Check Function

```typescript
const checkBackendHealth = async (): Promise<boolean> => {
  try {
    const response = await fetch("/api/docs", {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });
    return response.ok;
  } catch (error) {
    console.log("Backend not ready yet:", error);
    return false;
  }
};
```

### Startup Check

```typescript
useEffect(() => {
  const checkBackend = async () => {
    setIsCheckingBackend(true);

    const maxAttempts = 60;  // 2 minutes total
    let attempts = 0;

    while (attempts < maxAttempts) {
      const isReady = await checkBackendHealth();

      if (isReady) {
        setIsBackendReady(true);
        setIsCheckingBackend(false);
        return;
      }

      attempts++;
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    setIsCheckingBackend(false);
    console.error("Backend failed to start within 2 minutes");
  };

  checkBackend();
}, []);
```

## 7. Error Handling

### Try-Catch Wrapper

```typescript
const handleSubmit = useCallback(async (input: string) => {
  setIsLoading(true);

  try {
    // Session creation
    // Message sending
    // SSE processing
    setIsLoading(false);
  } catch (error) {
    console.error("Error:", error);

    // Add error message to chat
    const aiMessageId = Date.now().toString() + "_ai_error";
    setMessages(prev => [...prev, {
      type: "ai",
      content: `Sorry, there was an error: ${
        error instanceof Error ? error.message : 'Unknown error'
      }`,
      id: aiMessageId
    }]);

    setIsLoading(false);
  }
}, [userId, sessionId, appName]);
```

## 8. Complete Implementation Example

```typescript
const handleSubmit = useCallback(async (input: string) => {
  if (!input.trim()) return;
  setIsLoading(true);

  try {
    // 1. Create session if needed
    let currentUserId = userId;
    let currentSessionId = sessionId;
    let currentAppName = appName;

    if (!currentSessionId || !currentUserId || !currentAppName) {
      const sessionData = await retryWithBackoff(createSession);
      currentUserId = sessionData.userId;
      currentSessionId = sessionData.sessionId;
      currentAppName = sessionData.appName;
      setUserId(currentUserId);
      setSessionId(currentSessionId);
      setAppName(currentAppName);
    }

    // 2. Add user message
    const userMessageId = Date.now().toString();
    setMessages(prev => [...prev, {
      type: "human",
      content: input,
      id: userMessageId
    }]);

    // 3. Add empty AI message
    const aiMessageId = Date.now().toString() + "_ai";
    currentAgentRef.current = '';
    accumulatedTextRef.current = '';
    setMessages(prev => [...prev, {
      type: "ai",
      content: "",
      id: aiMessageId,
      agent: '',
    }]);

    // 4. Send message with SSE
    const sendMessage = async () => {
      const response = await fetch("/api/run_sse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          appName: currentAppName,
          userId: currentUserId,
          sessionId: currentSessionId,
          newMessage: {
            parts: [{ text: input }],
            role: "user"
          },
          streaming: false
        }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response;
    };

    const response = await retryWithBackoff(sendMessage);

    // 5. Process SSE stream
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let lineBuffer = "";
    let eventDataBuffer = "";

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();

        if (value) {
          lineBuffer += decoder.decode(value, { stream: true });
        }

        // Process lines
        let eolIndex;
        while ((eolIndex = lineBuffer.indexOf('\n')) >= 0 ||
               (done && lineBuffer.length > 0)) {
          let line = eolIndex >= 0
            ? lineBuffer.substring(0, eolIndex)
            : lineBuffer;

          lineBuffer = eolIndex >= 0
            ? lineBuffer.substring(eolIndex + 1)
            : "";

          if (line.trim() === "") {
            if (eventDataBuffer.length > 0) {
              const jsonData = eventDataBuffer.endsWith('\n')
                ? eventDataBuffer.slice(0, -1)
                : eventDataBuffer;
              processSseEventData(jsonData, aiMessageId);
              eventDataBuffer = "";
            }
          } else if (line.startsWith('data:')) {
            eventDataBuffer += line.substring(5).trimStart() + '\n';
          }
        }

        if (done) {
          if (eventDataBuffer.length > 0) {
            const jsonData = eventDataBuffer.endsWith('\n')
              ? eventDataBuffer.slice(0, -1)
              : eventDataBuffer;
            processSseEventData(jsonData, aiMessageId);
          }
          break;
        }
      }
    }

    setIsLoading(false);
  } catch (error) {
    console.error("Error:", error);
    setMessages(prev => [...prev, {
      type: "ai",
      content: `Error: ${error instanceof Error ? error.message : 'Unknown'}`,
      id: Date.now().toString() + "_ai_error"
    }]);
    setIsLoading(false);
  }
}, [userId, sessionId, appName]);
```

## 9. Troubleshooting

### SSE Connection Issues
- **Symptom**: No events received
- **Check**: Backend running on port 8000, proxy configured
- **Debug**: Monitor Network tab for SSE connection

### Partial Data Issues
- **Symptom**: JSON parse errors
- **Check**: Line buffering implementation
- **Debug**: Log `lineBuffer` and `eventDataBuffer` values

### State Not Updating
- **Symptom**: UI doesn't reflect SSE data
- **Check**: Message ID matching in state updates
- **Debug**: Console log state updates

### Backend Connection Errors
- **Symptom**: Failed to fetch
- **Check**: Backend health, CORS configuration
- **Debug**: Check proxy logs in terminal

## 10. Best Practices

✅ **Always buffer lines** - SSE data can arrive in chunks
✅ **Handle empty lines** - Indicates event completion
✅ **Reset refs on new message** - Prevent state pollution
✅ **Use retry logic** - Handle transient failures
✅ **Check backend health** - Before attempting connections
✅ **Proper error handling** - User-friendly error messages
✅ **Log strategically** - Debug SSE flow without spam
