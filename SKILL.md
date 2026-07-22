---
name: history-search
description: >
  键盘驱动的三层深度浏览 TUI，支持导出/导入会话历史。
  从本地缓存提取会话记录。
---

# history-search — 会话历史 TUI 浏览器

## 启动方式

当用户调用此技能时，按以下步骤执行：

1. **检查缓存**：确认 `.history_cache/sessions.json` 存在
   - 不存在 → 提示运行 `update_cache.py`
   - 存在 → 继续，**不**打印概览
2. **检测当前用户环境**：
   - 检查 `session_info["platform"]` 和用户的 shell 对话历史
   - **只给出对应该环境的命令**，不要列出所有平台版本
3. **给出唯一命令**：

   根据环境选择其一：

   | 环境 | 命令 |
   |---|---|
   | **Linux / macOS (bash/zsh)** | `python ~/.claude/skills/history-search/scripts/history_tui.py` |
   | **Windows cmd** | `python %USERPROFILE%\.claude\skills\history-search\scripts\history_tui.py` |
   | **Windows PowerShell** | `python $env:USERPROFILE\.claude\skills\history-search\scripts\history_tui.py` |

   > ⚠️ `~` 只适用于 Linux/macOS，不适用于 Windows cmd
   > ⚠️ `%USERPROFILE%` 只适用于 Windows cmd
   > ⚠️ `$env:USERPROFILE` 只适用于 PowerShell
   > ⚠️ 选错命令会报错，务必根据用户环境只发对应的那条

## 三层深度浏览（不是三栏！）

TUI 是**纵向下钻**结构，不是左右分栏：

| 层级 | 内容 | 进入方式 |
|---|---|---|
| **1 — 会话列表** | 显示所有历史会话（标题、日期、条数） | 默认界面 |
| **2 — 问题列表** | 选中会话的所有对话条目 | Enter（在层级1） |
| **3 — 单条详情** | 显示单条 Q&A 的完整内容 | Enter（在层级2） |

## 快捷键表

| 按键 | 层级1（会话） | 层级2（问题） | 层级3（详情） | 导出模式 |
|---|---|---|---|---|
| `↑` `↓` | 导航会话列表 | 导航问题列表 | 滚动内容 | 导航会话列表 |
| `PgUp` `PgDn` | 快翻 | 快翻 | 快翻 | 快翻 |
| `Enter` | 进入会话的问题列表 | 进入单条 Q&A 详情 | — | 执行导出 |
| `ESC` | 退出 TUI | 返回层级1 | 返回层级2 | 取消导出 |
| `x` | 进入导出模式 | — | — | — |
| `i` | 进入导入模式（退出TUI到终端） | — | — | — |
| `Space` | — | — | — | 勾选/取消选中 |
| `A` | — | — | — | 项目全选/全取消 |
| `Ctrl+C` | 退出 TUI | 退出 TUI | 退出 TUI | 取消导出 |

## 导出模式（Export Mode）

在层级1按 `x` 进入：

1. `Space` — 勾选/取消会话
2. `A` — 全选/取消当前项目的所有会话
3. `Enter` — 执行导出
4. `ESC` — 取消返回

导出的会话保存在 `claude-export-<timestamp>/` 目录下。

## 导入模式（Import Mode）

在层级1按 `i` 进入，TUI 退出后终端显示：

```
>>> Enter export dir or .jsonl path:
```

输入导出目录或 `.jsonl` 文件路径，自动复制到 `~/.claude/projects/` 并重建缓存。

## /resume 集成

导入的会话会被复制到 `~/.claude/projects/` 下，Claude Code 的 `/resume <uuid>` 命令会自动搜索该目录。

导入完成后，在 Claude 终端直接运行即可继续对话：

```
/resume <uuid>
```

> 只有通过 `/resume <uuid>` 能成功恢复的会话才算导入成功。导入过程会验证 JSONL 文件的完整性。

## 数据存储

- **缓存路径**：`.history_cache/` 存放在技能目录下
- **缓存内容**：`sessions.json` + `{uuid}.json`，仅索引（问题列表），不含完整答案
- **会话来源**：监听 `~/.claude/projects/` 下所有会话文件夹
- **自动更新**：由 SessionStart hook 触发 `scripts/update_cache.py`

## 依赖

```bash
pip install prompt_toolkit wcwidth
```
