---
name: history-search
description: 三层深度浏览 TUI，浏览/导出/导入 Claude Code 历史会话。从本地缓存提取会话记录。
---

# history-search

键盘驱动的三层深度浏览 TUI，支持浏览、导出、导入 Claude Code 历史会话。

## 启动方式

调用此技能时：

1. **缓存检查**：`.history_cache/sessions.json` 不存在 → 提示运行 `update_cache.py`
2. **环境检测**：根据用户平台给出对应的启动命令

| 环境 | 命令 |
|---|---|
| **Linux / macOS (bash/zsh)** | `python ~/.claude/skills/history-search/scripts/history_tui.py` |
| **Windows cmd** | `python %USERPROFILE%\\.claude\\skills\\history-search\\scripts\\history_tui.py` |
| **Windows PowerShell** | `python $env:USERPROFILE\\.claude\\skills\\history-search\\scripts\\history_tui.py` |

> ⚠️ 使用 `~`（Linux/macOS）、`%USERPROFILE%`（cmd）或 `$env:USERPROFILE`（PowerShell），选错会报错。

## 三层导航

纵向下钻，非左右分栏：

| 层级 | 内容 | 进入方式 |
|---|---|---|
| **1 — 会话列表** | 所有历史会话（标题、日期、条数） | 默认界面 |
| **2 — 问题列表** | 选中会话的所有对话条目 | Enter（层级1） |
| **3 — 单条详情** | 完整 Q&A 内容 | Enter（层级2） |

## 快捷键

| 按键 | 层级1 | 层级2 | 层级3 | 导出模式 |
|---|---|---|---|---|
| `↑` `↓` | 导航会话 | 导航问题 | 滚动内容 | 导航会话 |
| `PgUp` `PgDn` | 快翻 | 快翻 | 快翻 | 快翻 |
| `Enter` | 进入问题列表 | 进入详情 | — | 执行导出 |
| `ESC` | 退出 | 返回层级1 | 返回层级2 | 取消 |
| `x` | 导出模式 | — | — | — |
| `i` | 导入模式 | — | — | — |
| `Space` | — | — | — | 勾选/取消 |
| `A` | — | — | — | 全选/取消 |
| `Ctrl+C` | 退出 | 退出 | 退出 | 取消 |

## 导出

层级1按 `x` → `Space` 勾选 / `A` 全选 → `Enter` 执行导出，保存在 `claude-export-<timestamp>/`。

## 导入

层级1按 `i` → 退出 TUI → 输入导出目录或 `.jsonl` 路径 → 自动复制到 `~/.claude/projects/` → 重建缓存。

## /resume 集成

导入的会话可直接通过 `/resume <uuid>` 恢复。

## 数据存储

- **缓存**：`.history_cache/`，仅索引（不含回答正文）
- **来源**：`~/.claude/projects/` 下所有会话文件夹
- **更新**：SessionStart hook 触发 `scripts/update_cache.py`

## 依赖

```bash
pip install prompt_toolkit wcwidth
```
