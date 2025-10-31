# CLEM - Sleep Cycle Makefile
# Run: make -C .claude/scripts/clem sleepytime

.PHONY: sleepytime sleep-session sleep-project sleep-global sleep-skills help

# Default target
help:
	@echo "CLEM Sleep Cycle - Incremental Intelligence Consolidation"
	@echo ""
	@echo "Usage:"
	@echo "  make sleepytime        Run complete sleep cycle (all levels)"
	@echo "  make sleep-session     Level 1: Extract session memories"
	@echo "  make sleep-project     Level 2: Consolidate project knowledge (BDD.md)"
	@echo "  make sleep-global      Level 3: Synthesize global patterns"
	@echo "  make sleep-skills      Level 4: Generate skill updates"
	@echo ""
	@echo "Hierarchy:"
	@echo "  Session (minutes) → Project (hours) → Global (weeks) → Skills (continuous)"
	@echo ""
	@echo "Example: make -C .claude/scripts/clem sleepytime"

# Complete sleep cycle - all hierarchical levels
sleepytime: sleep-session sleep-project sleep-global sleep-skills
	@echo ""
	@echo "✅ Sleep cycle complete! Knowledge consolidated across all levels."
	@echo ""
	@echo "Generated artifacts:"
	@echo "  - Session memories: ~/.claude/memories.duckdb"
	@echo "  - Project knowledge: BDD.md"
	@echo "  - Global patterns: ~/.claude/misc/PATTERNS.md"
	@echo "  - Lessons learned: ~/.claude/misc/LESSONS.md"
	@echo "  - Skills: ~/.claude/misc/SKILLS.md"
	@echo ""

# Level 1: Session Memory Extraction (existing functionality)
sleep-session:
	@echo "💤 Level 1: Extracting session memories..."
	@uv run $(PWD)/clem.py memory-extract --scope session --user $(USER)
	@echo "✓ Session memories extracted"

# Level 2: Project Knowledge Consolidation
sleep-project:
	@echo "📋 Level 2: Consolidating project knowledge..."
	@uv run $(PWD)/clem.py sleep --level project
	@echo "✓ Project knowledge consolidated (BDD.md)"

# Level 3: Global Pattern Recognition
sleep-global:
	@echo "🌐 Level 3: Recognizing global patterns..."
	@uv run $(PWD)/clem.py sleep --level global
	@echo "✓ Global patterns synthesized"

# Level 4: Skill Synthesis
sleep-skills:
	@echo "🧠 Level 4: Synthesizing skills..."
	@uv run $(PWD)/clem.py sleep --level skills
	@echo "✓ Skill updates generated"

# Quick sleep - session and project only (faster iteration)
quick-sleep: sleep-session sleep-project
	@echo "✅ Quick sleep complete (session + project)"

# Deep sleep - include global and skills (comprehensive)
deep-sleep: sleepytime
	@echo "✅ Deep sleep complete (all levels)"

# Validate sleep cycle setup
validate:
	@echo "Validating CLEM sleep cycle setup..."
	@command -v uv >/dev/null 2>&1 || { echo "❌ uv not found. Install: pip install uv"; exit 1; }
	@test -f $(PWD)/clem.py || { echo "❌ clem.py not found in $(PWD)"; exit 1; }
	@echo "✅ Setup validated"

# Show current memory statistics
stats:
	@echo "Memory Statistics:"
	@uv run $(PWD)/clem.py memory-stats --user $(USER)

# Clean generated artifacts (for testing)
clean:
	@echo "⚠️  This will remove all generated knowledge artifacts!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f ~/.claude/memories.duckdb; \
		rm -f BDD.md; \
		rm -f ~/.claude/misc/PATTERNS.md; \
		rm -f ~/.claude/misc/LESSONS.md; \
		rm -f ~/.claude/misc/SKILLS.md; \
		echo "✓ Artifacts cleaned"; \
	else \
		echo "Cancelled"; \
	fi
