---
name: history-search
description: >
  键盘驱动的三层历史浏览器 TUI。方向键导航，Enter 选中，ESC 逐级返回。
  从预缓存读取会话/问题列表，惰性加载 AI 回答原文（一字不落）。
  纯只读，不影响当前上下文。
---

# history-search

浏览 Claude Code 历史会话的三层键盘驱动 TUI。

## 用法

在**你自己的终端**（cmd / PowerShell）里运行：

```bash
python C:\Users\Laptop\.claude\skills\history-search\scripts\history_tui.py
```

Git Bash 下用 `winpty`：

```bash
winpty python C:\Users\Laptop\.claude\skills\history-search\scripts\history_tui.py
```

## 三层导航

| 层级 | 内容 | 操作 |
|------|------|------|
| 1 | 所有历史会话（按时间倒序） | ↑↓ 移动，Enter 进入，ESC/^C 退出 |
| 2 | 该会话的历次提问列表 | ↑↓ 移动，Enter 查看回答，ESC 回层1 |
| 3 | AI 回答原文（一字不差，含 Write 内容） | ↑↓ 滚动，ESC 回层2 |

ESC 逐级返回：第3→第2→第1→退出。

## 安装

```bash
pip install prompt_toolkit wcwidth
```

## 数据机制

- **开关**：`.history_cache/.off` 存在时跳过缓存更新。
- **缓存**（轻量索引，不存回答正文）：`sessions.json` + `{uuid}.json`
- **惰性加载**：回答原文实时从 JSONL 读取，不预存。
- **自动更新**：SessionStart hook 调用 `scripts/update_cache.py`。

## Hook 配置

在 `~/.claude/settings.local.json` 的 `hooks.SessionStart` 中添加：

```json
{
  "type": "command",
  "command": "python3 .../scripts/update_cache.py",
  "timeout": 30,
  "statusMessage": "更新历史缓存…"
}
```

## 文件结构

```
~/.claude/skills/history-search/
├── SKILL.md                  ← 技能定义（本文件）
├── README.md
├── scripts/
│   ├── history_tui.py        ← 三层 TUI 主程序
│   └── update_cache.py       ← JSONL→缓存索引扫描
└── .history_cache/           ← 缓存目录（自动生成）
