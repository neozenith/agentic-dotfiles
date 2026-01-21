# agentic-dotfiles

Starting to version control my agentic coding dotfiles as I start to feel the pain tracking them across projects.


## Option #1: Submodule

### Setup

```sh
git submodule add https://github.com/neozenith/agentic-dotfiles.git .claude
```

### Update

```sh
git submodule update --init --recursive --remote
```

## Option #2: gitignored clone

### Setup

`.gitignore`

```gitignore
.claude/
```

Then clone this repo into the gitignored folder:

```sh
git clone https://github.com/neozenith/agentic-dotfiles.git .claude
```

### Update

```sh
cd .claude
git pull
```

# MCPs

Important MCPs to setup per project as needed:

## Dev Tools

### Context7 - Technical Documentation

Look up the latest documentation and code snippets

```bash
claude mcp add context7 npx -y @context7/mcp
```

### Playwright - Browser testing

Give agent the ability to drive a browser and check the browser console logs.
Can also take screenshots and get the coding agent to interpret visual aspects of websites.

```bash
claude mcp add playwright npx @playwright/mcp@latest
```

## Cognitive Tools

### Sequential Thinking

Force the agent to take a minimum of N thoughts to have extended thinking.
Can also prompt to allow branching thoughts, relfective thoughts on prior thoughts.

Best to prompt by specifying "thought budgets"

```bash
claude mcp add sequential-thinking npx -y @modelcontextprotocol/server-sequential-thinking
```

### Serena MCP

Uses actual Language Server Protocol (LSPs) to index the symbols in your project and where they are used.

Ideal for planning features, refactoring and actual symbol look up to create documentation.

```bash
claude mcp add serena 'uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --enable-web-dashboard false --project $(pwd)'
```

Ideal `Makefile` to complement this MCP will:

- Ensure the project is setup and the Serena config files are setup
- ONLY when code formatting, linting and typechecking pass then reindex the symbols in the project.

```Makefile
# Ensure the .make folder exists when starting make
# We need this for build targets that have multiple or no file output.
# We 'touch' files in here to mark the last time the specific job completed.
_ := $(shell mkdir -p .make)
SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

.PHONY: docs init fix check docs

#########################################################################################
# Project Setup
#########################################################################################

.serena/project.yml:
	uvx --from git+https://github.com/oraios/serena serena project create --language python --language typescript $$(pwd)

init: .make/init .serena/project.yml
.make/init:
	uv sync --dev

	# Initialize SerenaMCP project if not already done
	# uvx --from git+https://github.com/oraios/serena serena project create --language python --language typescript $$(pwd)

	uvx --from git+https://github.com/oraios/serena serena project index
	@touch $@

fix: init
	uv run ruff format .
	uv run ruff check . --fix

check: init docs fix
	uv sync --dev
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run mypy src/

	# As long as the whole project is formatted, linted, type checked, and tested then we can update the symbol index for SerenaMCP
	uvx --from git+https://github.com/oraios/serena serena project index
```

# LMStudio + Claude Code Router

- Start LMStudio with model `qwen/qwen2.5-coder-14b`
- Setup and start claude code router:

```sh
npm install -g @musistudio/claude-code-router
# Start router proxy
ccr start 
```

- Setup `~/.claude-code-router/config.json` like this:

```json
{
  "LOG": true,
  "HOST": "127.0.0.1",
  "PORT": 3456,
  "APIKEY": "",
  "API_TIMEOUT_MS": "600000",
  "transformers": [],
  "Providers": [
    {
      "name": "lmstudio",
      "api_base_url": "http://localhost:1234/v1/chat/completions",
      "models": [
        "qwen/qwen2.5-coder-14b"
      ],
      "api_key": "sk-1234",
      "transformer": {
        "use": [
          ["maxtoken",{ "max_tokens": 32768 }],
          "openrouter"
        ]
      }
    }
  ],
  "Router": {
    "default": "lmstudio,qwen/qwen2.5-coder-14b",
    "background": "lmstudio,qwen/qwen2.5-coder-14b",
    "think": "lmstudio,qwen/qwen2.5-coder-14b",
    "longContext": "lmstudio,qwen/qwen2.5-coder-14b",
    "longContextThreshold": 32768,
    "webSearch": "lmstudio,qwen/qwen2.5-coder-14b",
    "image": ""
  }
}
```

- `ccr restart`
- `ccr code` to start claude code using the wrapper that sets up the environment variables to redirect claude code to the model proxy.

