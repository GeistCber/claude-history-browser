---
name: history-search
description: >
  键盘驱动的三层历史浏览器 TUI。方向键导航，Enter 选中，ESC 逐级返回。
  从预缓存读取会话/问题列表，惰性加载 AI 回答原文（一字不落）。
  纯只读，不影响当前上下文。
---

# history-search

在**你自己的终端**（cmd / PowerShell）里运行独立的交互式 TUI 程序：

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
| 1 | 所有历史会话（按时间倒序），显示项目标签 `[项目]` 和导出标记 `[E]` | ↑↓ 移动，Enter 进入，ESC/^C 退出 |
| 2 | 该会话的历次提问列表 | ↑↓ 移动，Enter 查看回答，ESC 回层1 |
| 3 | AI 回答原文（一字不差，含 Write 内容） | ↑↓ 滚动 / 切换问题，PgUp/PgDn 翻页，ESC 回层2 |

键盘导航与鼠标操作：

- **↑↓、PgUp/PgDn** — 层1/2切换选择行，层3优先滚动当前回答内容，滚到边界自动切换问题
- **右侧滚动条** — 支持**鼠标左键按住拖动**，内容多时快速定位
- **Enter** 进入下一层，**ESC** 逐级返回（层3→层2→层1→退出）
- **层3头部固定** — 时间戳与用户问题保持在顶部不动，只滚动回答正文
- **`x`** — 在层1按 x 进入可视化导出模式

ESC 逐级返回：第3→第2→第1→退出。

## 数据机制

- **开关**：`.history_cache/.off` 存在时跳过缓存更新。
- **缓存**（轻量索引，不存回答正文）：`sessions.json` + `{uuid}.json`，支持多项目分目录存储。
- **项目感知**：自动扫描 `~/.claude/projects/` 下所有项目目录，按项目分组建立索引。
- **惰性加载**：回答原文实时从 JSONL 读取，不预存。
- **自动更新**：SessionStart hook 调用 `scripts/update_cache.py`。

## 导出 / 导入

将对话历史通过 `.claude-export` 格式在机器间传输。

### 导出

```bash
# 导出所有项目
python scripts/export.py --output ./my-backup

# 只导出一个项目
python scripts/export.py --project C--Users-Laptop --output ./laptop-backup

# 只导出一个会话
python scripts/export.py --session <uuid> --output ./single-session

# 预览不复制
python scripts/export.py --dry-run

# 额外生成人类可读的 Markdown
python scripts/export.py --format md --output ./with-markdown
```

### 导入

```bash
# 先验证再导入
python scripts/import.py --input ./my-backup --dry-run

# 覆盖已有文件
python scripts/import.py --input ./my-backup --overwrite

# 导入到新项目名
python scripts/import.py --input ./my-backup --project MyNewProject

# 导入后重建缓存
python scripts/import.py --input ./my-backup --update-cache
```

### 跨机传输示例

1. 源机器：`python scripts/export.py --output ./backup-20260719`
2. 传输目录（USB、网络共享、云存储）
3. 目标机器：`cd ~/.claude/skills/history-search/scripts`
4. `python import.py --input ./backup-20260719 --update-cache`
5. 运行 `history_tui.py` 即可浏览导入会话

导出格式是可移植目录树，不含机器特定依赖。

## 多项目支持

update_cache.py 自动扫描 `~/.claude/projects/` 下所有项目。可以限制到单个项目：

```bash
python scripts/update_cache.py --project C--Users-Laptop
python scripts/update_cache.py --project c--Users-Laptop-Desktop-C--
```

TUI 中每行会话显示 `[项目简称]` 标签，已导出的会话显示 `[E]` 标记。

## 安装

```
pip install prompt_toolkit wcwidth
```
