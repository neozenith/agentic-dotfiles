# Makefile for aws_diagrams_mingrammer skill
# Run from repo root: make -C .claude/skills/aws_diagrams_mingrammer/scripts <target>
#
# Self-describing output targets pattern:
#   1. The Python script declares what it produces via --output-targets
#   2. Make queries the script at parse time to learn the target list
#   3. Make only rebuilds when my_diagram.py is newer than its outputs

.PHONY: all clean help check

# ─────────────────────────────────────────────────────────────────────────────
# Diagrams — self-describing targets, minimal rebuilds
# ─────────────────────────────────────────────────────────────────────────────

DIAGRAM_SRC := my_diagram.py

# Query the script for its output targets (paths relative to skill root).
# Prefix with ../ because Make runs from scripts/ but outputs live in ../resources/.
DIAGRAM_TARGETS := $(addprefix ../,$(shell uv run --quiet $(DIAGRAM_SRC) --output-targets))

# Default target: ensure all diagram PNGs are up to date
all: $(DIAGRAM_TARGETS) ## Regenerate diagrams (only if source changed)

$(DIAGRAM_TARGETS): $(DIAGRAM_SRC)
	uv run $(DIAGRAM_SRC)

clean: ## Remove all generated diagram PNGs
	rm -f $(DIAGRAM_TARGETS)
	@echo "Cleaned diagram outputs"

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
