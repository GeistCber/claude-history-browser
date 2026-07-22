# Changelog

## v2.0.0 (2026-07-22)

### 🚀 New Features

- **Interactive Import Mode** (`i` key in TUI) — exit TUI → enter path → auto-import to local project
- **/resume Integration** — imported sessions automatically placed in user's project directory, immediately available via `/resume <uuid>` in any Claude Code terminal
- **Cross-platform support** — fully compatible with Windows (cmd & PowerShell) and Linux/macOS
- **UUID conflict prevention** — import skips sessions whose UUID already exists locally

### 🐛 Bug Fixes

- Cache overwrite: import no longer passes `--project` to `update_cache.py`, preserving all sessions
- Stale cache: all projects are scanned after import, not just the target
- Session list now shows all local sessions (fixed 5→10 session display bug)

### 📝 Documentation

- SKILL.md: cross-platform launch instructions (Linux/macOS, Windows cmd, PowerShell)
- Import Mode and /resume integration documented
- README.md: updated features table, cross-platform install guide

### 🔧 Technical

- `_term_import()`: new terminal-mode import function with path input
- `_get_user_project()`: auto-detects Claude Code project directory
- `short_project_name()`: handles both Windows (`--`-separated) and Linux project names
- Removed multi-step import UI in favor of simple path-input flow
- Added `_find_existing_uuids()` for cross-project UUID conflict detection

---

## v1.0.0 (Original)

- Three-layer keyboard navigation TUI
- Export mode (`x` key) with session selection
- Cross-machine sync via export/import scripts
- Multi-project support
- CJK character support via wcwidth
- Lazy loading from JSONL files
