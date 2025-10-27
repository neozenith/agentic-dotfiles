# Vite + Tailwind v4 + Shadcn + ADK Quick Reference

## Stack Summary
- **Vite** 6.3.4 + React-SWC
- **React** 19.0.0 + TypeScript 5.7.2
- **Tailwind** v4.1.5 (@tailwindcss/vite)
- **Shadcn UI** (Radix + custom styling)
- **ADK** Vanilla SSE (no CopilotKit)

## Quick Start

```bash
# Install dependencies
npm install

# Run dev server
npm run dev        # localhost:5173

# Build for production
npm run build      # tsc + vite build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── main.tsx              # Entry
├── App.tsx               # Main app + ADK logic
├── global.css            # Tailwind v4 + theme
├── utils.ts              # cn() utility
└── components/
    ├── ui/               # Shadcn components
    └── *.tsx             # Feature components
```

## Tailwind v4 Setup

```css
/* global.css */
@import "tailwindcss";

@theme inline {
  --color-primary: var(--primary);
  /* ... more tokens */
}

:root {
  --primary: oklch(0.205 0 0);
  /* OKLCH colors */
}
```

## Vite Config Essentials

```typescript
// vite.config.ts
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve("./src") }
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
});
```

## Shadcn Component Pattern

```typescript
import { cn } from "@/utils"
import { cva, type VariantProps } from "class-variance-authority"

const variants = cva("base-classes", {
  variants: {
    variant: { default: "...", outline: "..." },
    size: { default: "...", sm: "..." }
  },
  defaultVariants: { variant: "default" }
})

function Component({ className, variant, size }: Props) {
  return <div className={cn(variants({ variant, size, className }))} />
}
```

## ADK SSE Pattern

```typescript
// Create session
const sessionId = crypto.randomUUID();
const response = await fetch(
  `/api/apps/app/users/u_999/sessions/${sessionId}`,
  { method: "POST" }
);

// Send message with SSE
const streamResponse = await fetch("/api/run_sse", {
  method: "POST",
  body: JSON.stringify({
    appName, userId, sessionId,
    newMessage: { parts: [{ text: input }], role: "user" },
    streaming: false
  })
});

// Process SSE stream
const reader = streamResponse.body?.getReader();
const decoder = new TextDecoder();
let lineBuffer = "";
let eventDataBuffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (value) lineBuffer += decoder.decode(value, { stream: true });

  // Process lines ending with \n
  let eolIndex;
  while ((eolIndex = lineBuffer.indexOf('\n')) >= 0) {
    const line = lineBuffer.substring(0, eolIndex);
    lineBuffer = lineBuffer.substring(eolIndex + 1);

    if (line.trim() === "" && eventDataBuffer) {
      // Parse complete SSE event
      const data = JSON.parse(eventDataBuffer);
      processEvent(data);
      eventDataBuffer = "";
    } else if (line.startsWith('data:')) {
      eventDataBuffer += line.substring(5).trimStart() + '\n';
    }
  }

  if (done) break;
}
```

## Common Patterns

### cn() Utility
```typescript
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Retry with Backoff
```typescript
const retryWithBackoff = async (fn, maxRetries = 10) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      const delay = Math.min(1000 * Math.pow(2, i), 5000);
      await new Promise(r => setTimeout(r, delay));
    }
  }
};
```

### Loading Animation
```typescript
<div className="flex items-center gap-2">
  <div className="w-2 h-2 bg-[#00A3E0] rounded-full animate-bounce"
       style={{animationDelay: '0ms'}}></div>
  <div className="w-2 h-2 bg-[#33B5E8] rounded-full animate-bounce"
       style={{animationDelay: '150ms'}}></div>
  <div className="w-2 h-2 bg-[#0082B3] rounded-full animate-bounce"
       style={{animationDelay: '300ms'}}></div>
</div>
```

### Markdown Rendering
```typescript
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

<div className="prose prose-invert prose-sm max-w-none">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {content}
  </ReactMarkdown>
</div>
```

### Auto-scroll Chat
```typescript
const scrollRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  if (scrollRef.current) {
    const viewport = scrollRef.current.querySelector(
      "[data-radix-scroll-area-viewport]"
    );
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }
}, [messages]);
```

## Brand Colors

```typescript
// Direct usage
className="bg-[#00A3E0] hover:bg-[#0082B3]"

// CSS variables
--nine-blue: #00A3E0;
--nine-blue-dark: #0082B3;
--nine-blue-light: #33B5E8;
```

## TypeScript Types

```typescript
interface Message {
  type: "human" | "ai";
  content: string;
  id: string;
  agent?: string;
}

interface ComponentProps {
  messages: Message[];
  isLoading: boolean;
  onSubmit: (input: string) => void;
}
```

## Key Dependencies

```json
{
  "@radix-ui/react-slot": "^1.2.2",
  "@tailwindcss/vite": "^4.1.5",
  "@vitejs/plugin-react-swc": "^3.9.0",
  "class-variance-authority": "^0.7.1",
  "clsx": "^2.1.1",
  "lucide-react": "^0.508.0",
  "react": "^19.0.0",
  "react-markdown": "^9.0.3",
  "tailwind-merge": "^3.2.0",
  "tailwindcss": "^4.1.5",
  "vite": "^6.3.4"
}
```

## Troubleshooting

**Vite not starting**: Check port 5173, try `--host`
**Styles not applying**: Verify @import order in global.css
**SSE not working**: Check backend on port 8000, proxy config
**Type errors**: Run `tsc -b` to check TypeScript
**Build fails**: Verify all imports, check vite.config.ts
