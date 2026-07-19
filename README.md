# Claude History Browser

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![prompt_toolkit](https://img.shields.io/badge/deps-prompt__toolkit-00aaff)](https://github.com/prompt-toolkit/python-prompt-toolkit)

> 键盘驱动的 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) 历史会话浏览器 Skill。  
> 支持多项目浏览、可视化导出与跨机导入。

---

## ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 🎮 **三层键盘导航** | 会话列表 → 问题列表 → AI 回答原文，方向键操作，ESC 逐级返回 |
| 📌 **固定头部** | 层3时间戳与用户问题固定在顶部，仅滚动回答正文，查看长内容不丢失上下文 |
| 🖱️ **可拖动滚动条** | 右侧滚动条支持鼠标左键按住拖动，内容再多也能快速定位 |
| 📝 **Markdown 渲染** | AI 回答原文一字不改，标题/粗体/列表/代码块真实着色 |
| 📤 **可视化导出** | TUI 中直接按 `x` 进入导出模式，Space 勾选，Enter 执行 |
| 🔄 **跨机同步** | 导出为便携目录树，USB/网络传输后在目标机器导入即可浏览 |
| 📁 **多项目支持** | 自动扫描 `~/.claude/projects/` 下所有项目，列表显示 `[项目]` 标签 |
| ⚡ **惰性加载** | 回答正文从 JSONL 实时读取，不预存，启动快 |
| 🌏 **中日韩字符** | 基于 wcwidth 正确对齐 |

---

## 📦 快速安装

```bash
# 1. 克隆到 skills 目录
git clone https://github.com/GeistCber/claude-history-browser.git \
  ~/.claude/skills/history-search/

# 2. 安装依赖
pip install prompt_toolkit wcwidth

# 3. 更新缓存（首次必须）
python ~/.claude/skills/history-search/scripts/update_cache.py

# 4. 启动 TUI
python ~/.claude/skills/history-search/scripts/history_tui.py
```

> **Windows 提示**：Git Bash 下需使用 `winpty python ...` 启动，避免终端冲突。

---

## 🧭 三层导航

```
层 1: 会话列表  ──Enter──>  层 2: 问题列表  ──Enter──>  层 3: AI 回答原文
  ↑                            ↑                             ↑
  └── ESC                      └── ESC                       └── ESC
```

### 按键总表

| 按键 | 层1（会话列表） | 层2（问题列表） | 层3（回答正文） |
|------|----------------|----------------|----------------|
| `↑` `↓` | 切换选中会话 | 切换选中问题 | 先滚动当前回答内容，到边界则切换问题 |
| `PgUp` `PgDn` | 快速翻页 | 快速翻页 | 先翻页滚动，到边界切换问题 |
| `Enter` | 进入该会话的问题列表 | 查看该问题的回答 | — |
| `ESC` | 退出程序 | 返回层1 | 返回层2 |
| `x` | 进入导出模式 | — | — |
| **鼠标拖动** | 右侧滚动条点击/拖动跳转 | 同左 | 固定头部不滚动，仅正文区响应 |

### 层3 导航细节

在查看 AI 回答原文时：
- `↑` `↓` 优先在**当前回答内容内**滚动
- 只有滚动到内容**边界**时，才会自动**切换到上/下一条问题**
- 头部（时间戳 + 用户问题 + 分隔线）**固定不动**，不会随正文滚动
- 切换问题后头部自动更新为新问题的信息

---

## 📤 可视化导出

在 TUI 层1按 **`x`** 进入导出模式：

| 按键 | 功能 |
|------|------|
| `x` | 进入/退出导出模式 |
| `Space` | 选中/取消当前会话 |
| `a` | 全选/取消当前项目所有会话 |
| `Enter` | 执行导出，完成后显示结果摘要 |
| `ESC` | 退出导出模式或返回结果页 |

### 导出目录结构

```
claude-export-{timestamp}/
├── metadata.json              # 导出清单（版本、项目、会话数）
├── projects/
│   └── C--Users-Laptop/
│       ├── {uuid}.jsonl       # 会话原文
│       ├── {uuid}/            # 子 agent 日志（如有）
│       └── index.json         # 项目索引
└── markdown/                  # --format md 时生成人类可读版
```

---

## 🔄 跨机同步

### 导出（源机器）

```bash
cd ~/.claude/skills/history-search/scripts

# 命令行导出全部
python export.py --output ./backup-20260719

# 或 TUI 中按 x 可视化选择后 Enter
```

### 导入（目标机器）

```bash
cd ~/.claude/skills/history-search/scripts

# 先验证
python import.py --input ./backup-20260719 --dry-run

# 导入 + 重建缓存
python import.py --input ./backup-20260719 --overwrite --update-cache

# 启动 TUI 浏览
python history_tui.py
```

> 目标机器只需 Claude Code + history-search 脚本即可，不需要源机器的完整环境。

---

## 📂 文件结构

```
~/.claude/skills/history-search/
├── SKILL.md                     ← Skill 定义（Claude Code 识别入口）
├── README.md                    ← GitHub 项目说明
├── LICENSE                      ← MIT 许可
├── scripts/
│   ├── history_tui.py           ← 三层键盘 TUI 主程序（含可视化导出、可拖动滚动条）
│   ├── update_cache.py          ← JSONL → 缓存索引扫描（多项目）
│   ├── export.py                ← 对话导出工具
│   └── import.py                ← 对话导入工具
└── .history_cache/              ← 缓存目录（自动生成，不纳入版本控制）
```

---

## ⚙️ 数据机制

| 机制 | 说明 |
|------|------|
| **缓存开关** | `.history_cache/.off` 存在时跳过缓存更新 |
| **轻量索引** | 仅存会话/问题列表元信息，不存回答正文，体积小 |
| **项目感知** | 自动扫描 `~/.claude/projects/` 下所有项目目录 |
| **惰性加载** | 回答原文实时从 JSONL 逐条读取，不预存 |
| **自动更新** | SessionStart hook 自动调用 `scripts/update_cache.py` |
| **更新阈值** | 缓存超过1小时才会重新扫描 |

---

## 🛠️ CLI 命令参考

### 缓存管理

```bash
# 手动更新所有项目缓存
python scripts/update_cache.py

# 只更新指定项目
python scripts/update_cache.py --project C--Users-Laptop
```

### 导出命令

```bash
# 导出全部
python scripts/export.py

# 指定项目 + 输出目录
python scripts/export.py --project C--Users-Laptop --output ./backup

# 指定单个会话
python scripts/export.py --session <uuid> --output ./single

# 包含人类可读 Markdown
python scripts/export.py --format md --output ./with-markdown

# 仅预览（不复制文件）
python scripts/export.py --dry-run

# 导出时包含 .history_cache
python scripts/export.py --include-cache
```

### 导入命令

```bash
# 验证导入内容（不写入）
python scripts/import.py --input ./backup --dry-run

# 标准导入
python scripts/import.py --input ./backup

# 覆盖已有文件
python scripts/import.py --input ./backup --overwrite

# 指定项目名导入
python scripts/import.py --input ./backup --project MyProject

# 导入后自动重建缓存
python scripts/import.py --input ./backup --update-cache
```

---

## 📄 许可

[MIT](LICENSE)

---

## 🙏 致谢

- [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) — 终端交互框架
- [wcwidth](https://github.com/jquast/wcwidth) — 中日韩字符宽度计算
