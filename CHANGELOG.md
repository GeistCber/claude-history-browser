# Changelog

## v2.0.0 (2026-07-22)

### 🚀 New Features

- **Interactive Import Mode** — Press `i` at the session list to import conversations. TUI exits, prompts for an export directory or `.jsonl` path, then auto-imports to the local project.
- **/resume Integration** — Imported sessions are placed directly into the user's `~/.claude/projects/<project>/` directory, immediately available via `/resume <uuid>`.
- **Cross-Platform Support** — Explicit launch instructions for Windows (cmd & PowerShell) and Linux/macOS.
- **UUID Conflict Prevention** — Sessions with UUIDs already present locally are skipped during import.

### 🐛 Bug Fixes

- **Cache overwrite** — `_term_import()` no longer passes `--project` to `update_cache.py`; scans all projects after import.
- **Stale cache** — Full project scan runs after import, not just the target project.
- **Session list display** — Changed from 5 to 10 sessions shown.

### 📚 Documentation

- SKILL.md updated with cross-platform launch instructions.
- Import Mode and `/resume` integration documented.
- README.md updated with features table and cross-platform install guide.

### 🛠 Technical

- `_term_import()` — New terminal-based import flow replacing the multi-step TUI import.
- `_get_user_project()` — Auto-detects the Claude Code project directory from CWD.
- `short_project_name()` — Handles both Windows (`C--Users-...`) and Linux project names.
- Path-based import instead of multi-step UI.

## v1.0.0 (Original)

- Three-layer keyboard navigation TUI (session list → questions → response)
- Export mode via `x` key with Space/A selection
- Cross-machine sync via export/import scripts
- Multi-project support
- CJK character width support via wcwidth
- Lazy loading from JSONL files (no answer pre-caching)
