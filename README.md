# Claude History Browser

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Python check](https://github.com/GeistCber/claude-history-browser/actions/workflows/python-check.yml/badge.svg)](https://github.com/GeistCber/claude-history-browser/actions/workflows/python-check.yml)

> Keyboard-driven TUI for browsing, exporting, and importing Claude Code conversation history.
> Supports multi-project navigation, cross-machine sync, and `/resume` integration.

## Features

| Feature | Description |
|---------|-------------|
| 🎮 **Three-layer nav** | Session list → question list → AI response, arrow keys + ESC |
| 📌 **Sticky header** | Layer 3 pins timestamp + question, only body scrolls |
| 🖱️ **Draggable scrollbar** | Mouse drag on right-side scrollbar |
| 📝 **Markdown rendering** | Headings, bold, lists, code blocks in color |
| 📤 **Visual export** | Press `x` in TUI, Space to select, Enter to execute |
| 📥 **Interactive import** | Press `i` in TUI, enter path, auto-import to local project |
| 💬 **/resume ready** | Imported sessions available via `/resume <uuid>` immediately |
| 🔄 **Cross-machine sync** | Export → transfer → import; full conversation portability |
| 📁 **Multi-project** | Auto-scans all `~/.claude/projects/` directories |
| ⚡ **Lazy loading** | Response text read live from JSONL, no pre-caching |
| 🌏 **CJK support** | Proper character width via wcwidth |
| 🐧 **Cross-platform** | Windows (cmd/PowerShell) and Linux/macOS |

## Quick Install

```bash
# Clone to Claude Code skills directory
git clone https://github.com/GeistCber/claude-history-browser.git ~/.claude/skills/history-search/

# Install dependencies
pip install prompt_toolkit wcwidth

# Build session cache
python ~/.claude/skills/history-search/scripts/update_cache.py

# Launch TUI
python ~/.claude/skills/history-search/scripts/history_tui.py
```

### Platform-specific launch

```bash
# Linux / macOS
python ~/.claude/skills/history-search/scripts/history_tui.py

# Windows cmd
python %USERPROFILE%\.claude\skills\history-search\scripts\history_tui.py

# Windows PowerShell
python $env:USERPROFILE\.claude\skills\history-search\scripts\history_tui.py
```

## Navigation

```
Layer 1: Session list  ──Enter──>  Layer 2: Question list  ──Enter──>  Layer 3: AI response
  ↑                                   ↑                                    ↑
  └── ESC                             └── ESC                              └── ESC
```

| Key | Layer 1 | Layer 2 | Layer 3 |
|-----|---------|---------|---------|
| `↑` `↓` | Select session | Select question | Scroll response |
| `PgUp` `PgDn` | Page scroll | Page scroll | Page scroll |
| `Enter` | View questions | View response | — |
| `ESC` | Exit | Back to L1 | Back to L2 |
| `x` | Export mode | — | — |
| `i` | Import mode | — | — |
| `Space` | Toggle select (export) | — | — |
| `a` | Select all (export) | — | — |

## Import Mode

Press `i` at the session list to import conversations from another machine:

1. TUI exits, terminal shows: `>>> Enter export dir or .jsonl path:`
2. Enter path to an export directory (`claude-export-*`) or a `.jsonl` file
3. Sessions are copied into your local `~/.claude/projects/<project>/` directory
4. Cache is rebuilt automatically
5. TUI restarts with imported sessions visible
6. **Use `/resume <uuid>` in any Claude Code terminal** to continue an imported conversation

**UUID conflicts are auto-detected** — sessions with UUIDs already present locally are skipped.

## Export Mode

Press `x` at the session list:

1. `Space` to toggle session selection
2. `a` to select/deselect all in current project
3. `Enter` to execute export
4. Creates `claude-export-<timestamp>/` in the skill directory

## Cross-Machine Sync

```bash
# Source machine: export
python ~/.claude/skills/history-search/scripts/export.py --include-cache

# Transfer the claude-export-* directory via USB/SCP/cloud

# Target machine: import via TUI (press i) or CLI:
python ~/.claude/skills/history-search/scripts/import.py \
  --input claude-export-<timestamp> --update-cache

# Resume in any Claude Code terminal:
#   /resume <uuid>
```

## Project Structure

```
~/.claude/skills/history-search/
├── SKILL.md                  ← Claude Code skill entry point
├── README.md
├── CHANGELOG.md
├── LICENSE                   ← MIT
├── pyproject.toml            ← Python project metadata
├── requirements.txt          ← pip dependencies
├── .github/workflows/        ← CI workflows
└── scripts/
    ├── history_tui.py        ← Main TUI application
    ├── update_cache.py       ← Session cache indexer
    ├── export.py             ← Export tool (CLI + TUI)
    ├── import.py             ← Import tool (CLI)
    └── install_deps.py       ← Dependency installer
```

## Cache Mechanism

- Sessions are indexed in `.history_cache/` (question text only, no responses)
- Response bodies are read live from `~/.claude/projects/*/<uuid>.jsonl`
- Cache auto-updates on session start via SessionStart hook
- Place `.history_cache/.off` to disable cache updates

## Requirements

- Python 3.9+
- [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) ≥ 3.0
- [wcwidth](https://github.com/jquast/wcwidth) ≥ 0.2

## License

[MIT](LICENSE) © 2026 GeistCber
