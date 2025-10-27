---
name: "vite-adk-stack"
description: "Expert assistance with Vite + React 19 + TypeScript + Tailwind CSS v4 + Shadcn UI + Vanilla JS Google ADK integration. Use when building frontend applications with SSE streaming, session management, or working with this specific tech stack. Specializes in the project's patterns for ADK agent communication, styling conventions, and component architecture."
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

# Vite + Tailwind v4 + Shadcn + Vanilla ADK Stack Skill

You are now operating as an expert in this specific tech stack. Your expertise covers the project's conventions, patterns, and implementation details for building React frontends that communicate with Google ADK agents via SSE streaming.

## Stack Overview

**Build Tool**: Vite 6.3.4 with React-SWC plugin
**Frontend**: React 19.0.0 + TypeScript 5.7.2
**Styling**: Tailwind CSS v4.1.5 (via @tailwindcss/vite plugin)
**UI Components**: Shadcn UI (Radix UI primitives + custom styling)
**ADK Integration**: Vanilla JS SSE implementation (no CopilotKit)
**Icons**: Lucide React
**Markdown**: react-markdown + remark-gfm

## Project Structure

```
frontend/
├── index.html                 # Entry point
├── src/
│   ├── main.tsx              # React root
│   ├── App.tsx               # Main app component with ADK logic
│   ├── global.css            # Tailwind v4 + theme + animations
│   ├── utils.ts              # cn() utility
│   └── components/
│       ├── ui/               # Shadcn UI components
│       │   ├── button.tsx
│       │   └── scroll-area.tsx
│       ├── ChatMessagesView.tsx
│       ├── InputForm.tsx
│       └── WelcomeScreen.tsx
├── vite.config.ts            # Vite + proxy config
├── package.json
└── tsconfig.json
```

## 1. Vite Configuration

### vite.config.ts Pattern

```typescript
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    react(),           // React with SWC for fast refresh
    tailwindcss()      // Tailwind v4 Vite plugin
  ],
  base: "/app/",       // Base path for deployment
  resolve: {
    alias: {
      "@": path.resolve(new URL(".", import.meta.url).pathname, "./src"),
    },
  },
  server: {
    host: true,
    allowedHosts: true,
    proxy: {
      // Proxy API requests to ADK backend
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('Sending Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('Received Response:', proxyRes.statusCode, req.url);
          });
        },
      },
    },
  },
});
```

**Key Features:**
- `@vitejs/plugin-react-swc` for fast HMR
- `@tailwindcss/vite` for Tailwind v4 (no PostCSS config needed)
- Path alias `@` → `./src`
- API proxy to backend on port 8000
- Base path `/app/` for deployment routing

## 2. Tailwind CSS v4 Setup

### global.css Pattern

```css
/* Import Tailwind v4 (new syntax) */
@import "tailwindcss";
@import "tw-animate-css";

/* Custom dark mode variant */
@custom-variant dark (&:is(.dark *));

/* Theme configuration (inline @theme) */
@theme inline {
  /* Radius tokens */
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);

  /* Color tokens (mapped to CSS variables) */
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  /* ... more color tokens */
}

/* Root theme (OKLCH color space) */
:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  /* ... more colors */

  /* Custom brand colors */
  --nine-blue: #00A3E0;
  --nine-blue-dark: #0082B3;
  --nine-blue-light: #33B5E8;
}

/* Dark mode theme */
.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  /* ... dark mode colors */
}

/* Base layer */
@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
}

/* Custom animations */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fadeIn {
  animation: fadeIn 0.5s ease-out forwards;
}
.animate-fadeInUp {
  animation: fadeInUp 0.5s ease-out forwards;
}
```

**Key Patterns:**
- **Tailwind v4**: `@import "tailwindcss"` (no separate config file)
- **Inline @theme**: Define tokens directly in CSS
- **OKLCH Colors**: Modern color space for better perceptual uniformity
- **CSS Variables**: Design system tokens mapped to Tailwind
- **Dark Mode**: `.dark` class variant
- **Custom Animations**: Project-specific keyframes

## 3. Shadcn UI Component Pattern

### utils.ts (Required for Shadcn)

```typescript
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Button Component Example

```typescript
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/utils"

const buttonVariants = cva(
  // Base styles
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 outline-none focus-visible:ring-ring/50 focus-visible:ring-[3px]",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-xs hover:bg-primary/90",
        destructive: "bg-destructive text-white shadow-xs hover:bg-destructive/90",
        outline: "border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground shadow-xs hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        sm: "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
```

**Shadcn Patterns:**
- `cva` (class-variance-authority) for variant management
- `cn()` utility for class merging (clsx + tailwind-merge)
- Radix UI primitives for accessibility
- `asChild` prop for polymorphic components
- TypeScript with proper type inference
- `data-slot` attributes for styling hooks

## 4. Google ADK Integration (Vanilla JS)

### Session Management

```typescript
// Generate session ID
const generatedSessionId = crypto.randomUUID();

// Create session
const createSession = async () => {
  const response = await fetch(
    `/api/apps/app/users/u_999/sessions/${generatedSessionId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    }
  );

  const data = await response.json();
  return {
    userId: data.userId,
    sessionId: data.id,
    appName: data.appName
  };
};
```

### SSE Streaming Implementation

```typescript
const handleSubmit = async (input: string) => {
  // Send message with SSE streaming
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

  // Process SSE stream
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let lineBuffer = "";
  let eventDataBuffer = "";

  while (true) {
    const { done, value } = await reader.read();

    if (value) {
      lineBuffer += decoder.decode(value, { stream: true });
    }

    // Process lines
    let eolIndex;
    while ((eolIndex = lineBuffer.indexOf('\n')) >= 0 || (done && lineBuffer.length > 0)) {
      let line = eolIndex >= 0
        ? lineBuffer.substring(0, eolIndex)
        : lineBuffer;

      lineBuffer = eolIndex >= 0
        ? lineBuffer.substring(eolIndex + 1)
        : "";

      // Empty line = event complete
      if (line.trim() === "") {
        if (eventDataBuffer.length > 0) {
          const jsonData = eventDataBuffer.endsWith('\n')
            ? eventDataBuffer.slice(0, -1)
            : eventDataBuffer;

          processSseEventData(jsonData, aiMessageId);
          eventDataBuffer = "";
        }
      }
      // SSE data line
      else if (line.startsWith('data:')) {
        eventDataBuffer += line.substring(5).trimStart() + '\n';
      }
    }

    if (done) {
      // Process final event
      if (eventDataBuffer.length > 0) {
        const jsonData = eventDataBuffer.endsWith('\n')
          ? eventDataBuffer.slice(0, -1)
          : eventDataBuffer;
        processSseEventData(jsonData, aiMessageId);
      }
      break;
    }
  }
};
```

### SSE Event Parsing

```typescript
const extractDataFromSSE = (data: string) => {
  const parsed = JSON.parse(data);

  let textParts: string[] = [];
  let agent = '';
  let storyboard = null;
  let videoClips = null;
  let finalVideo = null;

  // Extract text parts
  if (parsed.content?.parts) {
    textParts = parsed.content.parts
      .filter((part: any) => part.text)
      .map((part: any) => part.text);
  }

  // Extract agent name
  if (parsed.author) {
    agent = parsed.author;
  }

  // Extract state deltas (agent outputs)
  if (parsed.actions?.stateDelta) {
    storyboard = parsed.actions.stateDelta.storyboard_images;
    videoClips = parsed.actions.stateDelta.video_clips;
    finalVideo = parsed.actions.stateDelta.final_video_uri;
  }

  return { textParts, agent, storyboard, videoClips, finalVideo };
};
```

**ADK Integration Patterns:**
- **Manual SSE**: No CopilotKit, direct fetch + ReadableStream
- **Session Management**: UUID-based sessions with backend
- **Line Buffering**: Handle partial SSE data correctly
- **Event Parsing**: Extract structured data from SSE events
- **State Accumulation**: Build up AI responses incrementally
- **Agent Tracking**: Monitor which agent is currently responding

### Retry Logic with Exponential Backoff

```typescript
const retryWithBackoff = async (
  fn: () => Promise<any>,
  maxRetries: number = 10,
  maxDuration: number = 120000
): Promise<any> => {
  const startTime = Date.now();
  let lastError: Error;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    if (Date.now() - startTime > maxDuration) {
      throw new Error(`Retry timeout after ${maxDuration}ms`);
    }

    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
      console.log(`Attempt ${attempt + 1} failed, retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError!;
};

// Usage
const sessionData = await retryWithBackoff(createSession);
```

### Backend Health Check

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

// Check on mount
useEffect(() => {
  const checkBackend = async () => {
    const maxAttempts = 60;
    let attempts = 0;

    while (attempts < maxAttempts) {
      const isReady = await checkBackendHealth();
      if (isReady) {
        setIsBackendReady(true);
        return;
      }
      attempts++;
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    console.error("Backend failed to start within 2 minutes");
  };

  checkBackend();
}, []);
```

## 5. TypeScript Patterns

### Message Types

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

interface ProcessedEvent {
  title: string;
  data: any;
}
```

### Component Props

```typescript
interface ChatMessagesViewProps {
  messages: Message[];
  isLoading: boolean;
  scrollAreaRef: React.RefObject<HTMLDivElement>;
  onSubmit: (input: string) => void;
  onCancel: () => void;
  displayData: string | null;
  messageEvents: Map<string, ProcessedEvent[]>;
}
```

**TypeScript Conventions:**
- Strict mode enabled
- Interface over type for props
- Explicit return types for complex functions
- Proper React.ComponentProps usage
- Generic types for utilities (cn, cva)

## 6. Component Patterns

### Auto-scrolling Chat

```typescript
const scrollAreaRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  if (scrollAreaRef.current) {
    const scrollViewport = scrollAreaRef.current.querySelector(
      "[data-radix-scroll-area-viewport]"
    );
    if (scrollViewport) {
      scrollViewport.scrollTop = scrollViewport.scrollHeight;
    }
  }
}, [messages]);
```

### Loading States

```typescript
{isLoading && (
  <div className="flex items-center gap-2">
    <div className="w-2 h-2 bg-[#00A3E0] rounded-full animate-bounce"
         style={{animationDelay: '0ms'}}></div>
    <div className="w-2 h-2 bg-[#33B5E8] rounded-full animate-bounce"
         style={{animationDelay: '150ms'}}></div>
    <div className="w-2 h-2 bg-[#0082B3] rounded-full animate-bounce"
         style={{animationDelay: '300ms'}}></div>
    <span className="text-neutral-400 ml-2">Processing...</span>
  </div>
)}
```

### Markdown Rendering

```typescript
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

<div className="prose prose-invert prose-sm max-w-none">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {message.content}
  </ReactMarkdown>
</div>
```

### Conditional Rendering with Media

```typescript
{message.storyboard && message.storyboard.length > 0 && (
  <div className="mt-4">
    <div className="text-sm font-semibold mb-2">🎨 Storyboard:</div>
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {message.storyboard.map((image, idx) => (
        <img
          key={idx}
          src={image}
          alt={`Storyboard frame ${idx + 1}`}
          className="w-full rounded border border-neutral-600"
        />
      ))}
    </div>
  </div>
)}

{message.finalVideo && (
  <div className="mt-4">
    <div className="text-sm font-semibold mb-2">✨ Final Advertisement:</div>
    <video
      src={message.finalVideo}
      controls
      className="w-full rounded border border-neutral-600"
    />
  </div>
)}
```

## 7. Styling Conventions

### Brand Colors

```typescript
// Direct hex usage (for consistency)
className="bg-[#00A3E0] hover:bg-[#0082B3] text-white"

// Or via CSS variables
className="bg-[var(--nine-blue)] hover:bg-[var(--nine-blue-dark)]"
```

### Consistent Spacing

```typescript
// Card-like containers
className="bg-neutral-800 rounded-lg p-4 border border-neutral-600"

// Form inputs
className="flex-1 px-4 py-3 rounded-lg bg-neutral-800 border border-neutral-600
           text-white placeholder-neutral-400 focus:outline-none focus:ring-2
           focus:ring-[#00A3E0] focus:border-transparent"
```

### Dark Mode First

```typescript
// Assume dark mode by default
className="bg-neutral-900 text-neutral-100 border-neutral-700"

// Light mode if needed (via .dark variant)
className="bg-white dark:bg-neutral-900 text-black dark:text-white"
```

### Animation Patterns

```css
/* Inline animation delays */
<div style={{animationDelay: '0ms'}} />
<div style={{animationDelay: '150ms'}} />
<div style={{animationDelay: '300ms'}} />

/* Custom animation classes */
.animate-fadeIn { animation: fadeIn 0.5s ease-out forwards; }
.animate-fadeInUp { animation: fadeInUp 0.5s ease-out forwards; }
```

## 8. Package.json Scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  }
}
```

**Development Workflow:**
```bash
npm run dev      # Start dev server (localhost:5173)
npm run build    # Type check + build
npm run preview  # Preview production build
```

## 9. Key Dependencies

```json
{
  "dependencies": {
    "@radix-ui/react-scroll-area": "^1.2.8",
    "@radix-ui/react-slot": "^1.2.2",
    "@tailwindcss/vite": "^4.1.5",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.508.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-markdown": "^9.0.3",
    "remark-gfm": "^4.0.1",
    "tailwind-merge": "^3.2.0",
    "tailwindcss": "^4.1.5"
  },
  "devDependencies": {
    "@vitejs/plugin-react-swc": "^3.9.0",
    "@types/react": "^19.1.2",
    "typescript": "~5.7.2",
    "vite": "^6.3.4"
  }
}
```

## 10. Common Patterns

### Input Form Component

```typescript
interface InputFormProps {
  onSubmit: (input: string) => void;
  isLoading: boolean;
  context: "homepage" | "chat";
}

export function InputForm({ onSubmit, isLoading, context }: InputFormProps) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSubmit(input.trim());
      setInput("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={isLoading}
        className="flex-1 px-4 py-3 rounded-lg bg-neutral-800
                   border border-neutral-600 text-white"
      />
      <Button type="submit" disabled={isLoading || !input.trim()}>
        {isLoading ? "Processing..." : "Send"}
      </Button>
    </form>
  );
}
```

### Agent Name Formatting

```typescript
const getEventTitle = (agentName: string): string => {
  switch (agentName) {
    case "scraper_agent": return "🔍 Analyzing Website";
    case "story_agent": return "💡 Developing Creative Concept";
    case "screenplay_agent": return "📝 Writing Ad Script";
    case "storyboard_agent": return "🎨 Creating Storyboards";
    case "video_agent": return "🎬 Producing Video Clips";
    case "stitch_agent": return "✂️ Assembling Final Video";
    case "director_agent":
    case "root_agent": return "🎭 Director Guidance";
    default: return `Processing (${agentName || 'Unknown Agent'})`;
  }
};
```

### State Management Pattern

```typescript
// Use refs for values that don't need re-renders
const currentAgentRef = useRef('');
const accumulatedTextRef = useRef("");

// Use state for UI updates
const [messages, setMessages] = useState<MessageWithAgent[]>([]);
const [isLoading, setIsLoading] = useState(false);
const [messageEvents, setMessageEvents] = useState<Map<string, ProcessedEvent[]>>(new Map());
```

## 11. Best Practices

### Performance
✅ Use `@vitejs/plugin-react-swc` for faster builds
✅ Lazy load heavy components
✅ Use refs for non-UI state
✅ Memoize expensive calculations
✅ Proper cleanup in useEffect

### TypeScript
✅ Enable strict mode
✅ Explicit return types for complex functions
✅ Use interfaces for props
✅ Proper generic types
✅ Avoid `any` type

### Styling
✅ OKLCH for colors
✅ CSS variables for theming
✅ Tailwind v4 inline @theme
✅ Dark mode by default
✅ Consistent spacing scale

### ADK Integration
✅ Proper SSE line buffering
✅ Exponential backoff retries
✅ Backend health checks
✅ Session management
✅ Error handling

### Components
✅ Shadcn UI patterns
✅ cn() utility for class merging
✅ Radix UI for accessibility
✅ Proper TypeScript props
✅ Composition over inheritance

## 12. Troubleshooting

### Vite Issues
- **Port in use**: Change port in `vite.config.ts` server.port
- **HMR not working**: Check network/firewall, try `host: true`
- **Import errors**: Verify @ alias in tsconfig and vite.config

### Tailwind v4 Issues
- **Styles not applying**: Check @import order in global.css
- **Dark mode not working**: Verify .dark class on root element
- **Custom colors not working**: Check OKLCH syntax and --color- prefix

### SSE Issues
- **Connection drops**: Check backend health, verify proxy config
- **Partial data**: Ensure proper line buffering
- **CORS errors**: Configure backend CORS headers

### Build Issues
- **Type errors**: Run `tsc -b` to check TypeScript
- **Build fails**: Check Vite config, verify all imports
- **Large bundle**: Use dynamic imports, check dependencies

---

You are now ready to work with this specific tech stack. Focus on maintaining consistency with existing patterns, proper TypeScript typing, and the project's established conventions for ADK integration.
