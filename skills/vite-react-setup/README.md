# Vite React Setup Skill

Automated setup script for creating a production-ready Vite + React + TypeScript project with modern tooling.

## What it includes

- ⚡ **Vite** - Next generation frontend tooling
- ⚛️ **React 18** with **TypeScript**
- 🎨 **Tailwind CSS v4** - Utility-first CSS framework (using new Vite plugin)
- 🎭 **shadcn/ui** - Re-usable component library
- 🧪 **Vitest** - Fast unit testing framework
- 🧩 Path aliases configured (`@/*` → `./src/*`)

## Usage

### From command line:
```bash
node .claude/skills/vite-react-setup/setup-vite-react.js my-project-name
```

### From Claude Code:
Ask Claude to "set up a new Vite React project" and provide the project name.

## What the script does

1. Creates a new Vite + React + TypeScript project
2. Installs all dependencies
3. Configures Tailwind CSS v4 with the new Vite plugin
4. Sets up shadcn/ui with default configuration
5. Configures Vitest for testing
6. Updates TypeScript config with path aliases
7. Creates necessary type definition files
8. Verifies the build works

## After setup

Navigate to your project and run:
```bash
cd my-project-name
npm run dev          # Start development server
npm run build        # Build for production
npm run test         # Run tests
npm run test:ui      # Run tests with UI
```

Add shadcn/ui components:
```bash
npx shadcn@latest add button card
```

## Script features

- ✅ Automated installation of all dependencies
- ✅ Proper file configuration (no manual editing needed)
- ✅ Build verification to ensure everything works
- ✅ Clear progress indicators
- ✅ Error handling with helpful messages

## Requirements

- Node.js 18+
- npm 9+

## Notes

- The script uses `shadcn@latest init -d` for automatic setup
- All configurations follow official documentation from Vite, Tailwind CSS v4, and shadcn/ui
- The script verifies the build at the end to ensure everything is working
