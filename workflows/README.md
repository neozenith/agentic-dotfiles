# `.claude/workflows/`

Named orchestration scripts. Trigger by prompting Claude with `ultracode` +
the workflow name.

## `gooddocs-audit`

```text
ultracode: gooddocs-audit                          # audit all *.md
ultracode: gooddocs-audit README.md src/tfs/app.py # audit specific files
ultracode: gooddocs-audit fix                       # apply safe doc-only fixes
ultracode: gooddocs-audit fix README.md             # fix specific files
```
