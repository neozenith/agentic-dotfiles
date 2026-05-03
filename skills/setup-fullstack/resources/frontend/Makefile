SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

API_PORT         ?= 8200
AGENTIC_API_PORT ?= 8201
DEV_PORT         ?= 5173
AGENTIC_DEV_PORT ?= 5174

.PHONY: install dev agentic-dev build preview \
        format format-check lint lint-fix \
        typecheck test test-e2e test-e2e-ui clean

install:
	bun install

# The dev / agentic-dev targets export ports as env vars; the package.json
# scripts read them with shell defaults. concurrently does the rest.
dev:
	API_PORT=$(API_PORT) DEV_PORT=$(DEV_PORT) bun run dev

agentic-dev:
	API_PORT=$(AGENTIC_API_PORT) DEV_PORT=$(AGENTIC_DEV_PORT) bun run agentic-dev

build:
	bun run build

preview:
	bun run preview

format:
	bun run format

format-check:
	bun run format-check

lint:
	bun run lint

lint-fix:
	bun run lint-fix

typecheck:
	bun run typecheck

test:
	bun run test

test-e2e:
	bun run test:e2e

test-e2e-ui:
	bun run test:e2e -- --ui

clean:
	rm -rf node_modules dist coverage e2e-screenshots playwright-report test-results
