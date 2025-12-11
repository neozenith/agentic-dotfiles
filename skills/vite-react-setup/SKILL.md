---
name: vite-react-setup
description: Automated setup for Vite + React + TypeScript + Tailwind CSS v4 + shadcn/ui + Vitest projects. Use when setting up new React projects, creating Vite apps, initializing React TypeScript projects, or setting up modern React development environments.
---

# Vite React Setup

Automatically scaffolds a complete modern React development environment with:
- Vite + React + TypeScript
- Tailwind CSS v4 with @tailwindcss/vite plugin
- shadcn/ui pre-configured with components.json
- Vitest for testing with React Testing Library
- Path aliases configured (@/*)
- Production build verified

## Usage

By default, sets up in the current directory. Optionally specify a subdirectory:

```bash
# Setup in current directory
node .claude/skills/vite-react-setup/setup-vite-react.js

# Setup in a subdirectory
node .claude/skills/vite-react-setup/setup-vite-react.js frontend/
```

## What Gets Configured

1. **Vite Configuration**: React plugin + Tailwind v4 + Vitest + path aliases
2. **TypeScript**: Proper tsconfig with path mappings
3. **Tailwind CSS v4**: Modern @import syntax with Vite plugin
4. **shadcn/ui**: Initialized with defaults, ready to add components
5. **Testing**: Vitest + jsdom + React Testing Library
6. **Scripts**: dev, build, test, test:ui

## After Setup

```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run test         # Run tests
npm run test:ui      # Run tests with UI

# Add shadcn components
npx shadcn@latest add button card
```
