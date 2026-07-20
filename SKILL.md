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
| 1 | 所有历史会话（按时间倒序），显示项目标签 `[项目]` 和导出标记 `[E]` | ↑↓ 移动，Enter 进入，`x` 导出模式，ESC/^C 退出 |
| 2 | 该会话的历次提问列表 | ↑↓ 移动，Enter 查看回答，ESC 回层1 |
| 3 | AI 回答原文（一字不差，含 Write 内容），时间戳与问题固定不动 | ↑↓ 滚动/切换问题，PgUp/PgDn 翻页，ESC 回层2 |

### 按键总表

| 按键 | 层1 | 层2 | 层3 |
|------|-----|-----|-----|
| `↑` `↓` | 切换选中会话 | 切换选中问题 | 优先滚动，到边界切换问题 |
| `PgUp` `PgDn` | 快速翻页 | 快速翻页 | 翻页滚动，到边界切换问题 |
| `Enter` | 进入该会话的问题列表 | 查看该问题的回答 | — |
| `ESC` | 退出程序 | 返回层1 | 返回层2 |
| `x` | 进入导出模式 | — | — |
| **鼠标拖动** | 右侧滚动条点击/拖动 | 同左 | 仅正文区响应 |

### 层3 导航细节

- `↑` `↓` **优先滚动**当前回答内容，到边界才**自动切换问题**
- 头部（时间戳 + 用户问题）**固定不动**，不随正文滚动
- 切换问题后头部自动换为新问题的信息

## 数据机制

- **开关**：`.history_cache/.off` 存在时跳过缓存更新。
- **缓存**（轻量索引，不存回答正文）：`sessions.json` + `{uuid}.json`，支持多项目分目录存储。
- **项目感知**：自动扫描 `~/.claude/projects/` 下所有项目目录，按项目分组建立索引。
- **惰性加载**：回答原文实时从 JSONL 读取，不预存。
- **自动更新**：SessionStart hook 调用 `scripts/update_cache.py`。

## 导出 / 导入

将对话历史通过 `.claude-export` 格式在机器间传输。

> **核心原理**：导出就是把 `.jsonl` 文件从 `~/.claude/projects/` **复制**到一个便携目录树；导入就是把这个目录树里的文件**复制回去**。全程是文件级批量操作，不需要手动编辑任何 JSON 内容。

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

导出后生成的结构：
```
./my-backup/
├── metadata.json              # 元信息（导出时间、源机器名、项目列表）
└── projects/
    └── C--Users-Laptop/
        ├── index.json         # 会话索引
        ├── abc123.jsonl       # 单个会话文件（程序自动生成，不要手改）
        ├── def456.jsonl
        └── def456/            # 子代理会话目录（如有）
```

### 导入

```bash
# 1. 先预览（推荐）——只看会写哪些文件，不动磁盘
python scripts/import.py --input ./my-backup --dry-run

# 2. 正式导入——复制文件到 ~/.claude/projects/ 下
python scripts/import.py --input ./my-backup

# 3. 导入后一步到位（推荐）——导入 + 重建 TUI 搜索缓存
python scripts/import.py --input ./my-backup --update-cache

# 如遇"文件已存在"报错，可用 --overwrite 覆盖
python scripts/import.py --input ./my-backup --overwrite --update-cache

# 导入到不同的项目名下（改名）
python scripts/import.py --input ./my-backup --project MyNewProject
```

### 导入过程详解（脚本内部做了什么）

| 步骤 | 做了什么 | 出错怎么办 |
|------|----------|------------|
| ① 验证结构 | 检查 `metadata.json`、`index.json`、所有列出的 `.jsonl` 文件是否存在 | 显示具体缺失文件路径 |
| ② 安全检查 | 防止路径遍历攻击 | 直接报错退出 |
| ③ 磁盘检查 | 确保剩余空间 ≥ 数据量 × 2 | 警告但不中断 |
| ④ UUID 去重 | 检查不同项目间有没有重复 UUID | 警告但不中断 |
| ⑤ **复制文件** | `shutil.copy2()` 逐个复制 `.jsonl` 到 `~/.claude/projects/<项目名>/` | 会继续导其他文件，最后汇总错误 |
| ⑥ 复制子代理目录 | 对应的 `{uuid}/` 子目录也复制过去 | 警告，不影响主文件 |
| ⑦ 重建缓存（可选） | 跑 `update_cache.py` 刷新索引，让 TUI 能搜到 | 警告，后续可手动跑 |

**关键点**：第⑤步就是纯文件 `copy2`，跟你手动把 U 盘文件拖到文件夹里是一个道理。不是"粘贴 JSON 内容"，没有半行需要手改。

### 跨机传输完整示例

```bash
# ── 源机器 ──
cd ~/.claude/skills/history-search/scripts
python export.py --output ./backup-20260720

# ── 然后把 backup-20260720/ 目录传到目标机器 ──
# 可以用 U 盘、scp、网盘、共享文件夹，随便什么方式

# ── 目标机器 ──
cd ~/.claude/skills/history-search/scripts
python import.py --input /path/to/backup-20260720 --dry-run     # 先预览
python import.py --input /path/to/backup-20260720 --update-cache # 正式导入
winpty python history_tui.py                                     # 打开看
```

导出格式是纯文件目录树，不含机器特定依赖，跨平台通用。

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
