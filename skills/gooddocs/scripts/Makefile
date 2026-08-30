# gooddocs skill scripts (TypeScript-only).
# Run from repo root: make -C .claude/skills/gooddocs/scripts <target>

TS_SCRIPTS = prose_gates
TS_SRC = $(addsuffix .ts,$(TS_SCRIPTS)) $(addsuffix .test.ts,$(TS_SCRIPTS))

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
BIOME = bunx --bun @biomejs/biome

.PHONY: all help clean \
        format format-ts format-check format-check-ts \
        lint lint-ts lint-fix lint-fix-ts \
        typecheck typecheck-ts \
        test test-ts test-cov test-cov-ts \
        install-ts ci fix

all: format lint typecheck test-cov

format: format-ts
format-ts:       ; $(BIOME) format --write $(TS_SRC)
format-check: format-check-ts
format-check-ts: ; $(BIOME) format $(TS_SRC)

lint: lint-ts
lint-ts:         ; $(BIOME) lint $(TS_SRC)
lint-fix: lint-fix-ts
lint-fix-ts:     ; $(BIOME) lint --write $(TS_SRC)

typecheck: typecheck-ts
typecheck-ts:    ; $(THIS_DIR)node_modules/.bin/tsc --project $(THIS_DIR)tsconfig.json --noEmit

test: test-ts
test-ts:         ; bun test --cwd $(THIS_DIR)

test-cov: test-cov-ts
test-cov-ts:     ; bun test --cwd $(THIS_DIR) --coverage

install-ts:      ; bun install --cwd $(THIS_DIR)

ci: format-check lint typecheck test-cov
fix: format lint-fix

clean:           ; rm -rf node_modules
