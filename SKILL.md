---
name: history-search
description: >
  键盘驱动的三层历史浏览器 TUI。方向键导航，Enter 选中，ESC 逐级返回。
  从预缓存读取会话/问题列表，惰性加载 AI 回答原文（一字不落）。
  全键盘操作，中日韩对齐，纯只读，不影响当前上下文。
---

# history-search

浏览 Claude Code 历史会话的三层键盘驱动 TUI。

## 何时使用

- 想快速翻看或搜索历史对话记录时
- 需要回顾某个会话中 AI 给出的完整回答（一字不落）
- 不想在 Claude Code 聊天框里翻 JSONL 文件时

## 安装

```bash
pip install prompt_toolkit wcwidth
```

## 用法

把本目录放到 `~/.claude/skills/history-search/`，然后在终端运行：

```bash
python scripts/history_tui.py --jsonl-dir "PATH_TO_YOUR_JSONL"
```

Claude Code 中通过 `/history-search` 触发本 skill。

## 三层导航

| 层级 | 内容 | 按键 |
|------|------|------|
| 1 | 所有历史会话（按时间倒序） | ↑↓ 选择，Enter 进入，ESC/^C 退出 |
| 2 | 该会话的历次提问列表 | ↑↓ 选择，Enter 查看回答，ESC 返回 |
| 3 | AI 回答原文（Markdown 渲染） | ↑↓ 滚动，ESC 返回问题列表 |

## 特性

- **键盘驱动** — 方向键 + PgUp/PgDn + Enter + ESC，全键盘操作
- **三级 ESC 返回** — 第3→第2→第1→退出，不丢导航位置
- **中日韩对齐** — 使用 wcwidth 正确处理东亚双宽字符
- **Markdown 渲染** — 标题/粗体/列表/代码块在终端中真实渲染，去掉标记符号
- **原文保证** — AI 回答一字不改，包括 Write 工具写入的文件内容
- **惰性加载** — 回答正文不预存，选中后才从 JSONL 读取
- **预缓存** — 会话列表和问题列表通过 update_cache.py 预生成索引

## 数据机制

- **开关**：`.history_cache/.off` 存在时跳过缓存更新
- **缓存**（轻量索引，不存回答正文）：`sessions.json` + `{uuid}.json`
- **惰性加载**：回答原文实时从 JSONL 读取，不预存
- **自动更新**：SessionStart hook 调用 `scripts/update_cache.py`

## 文件结构

```
~/.claude/skills/history-search/
├── SKILL.md                     ← Skill 定义（Claude Code 识别入口）
├── README.md                    ← GitHub 项目说明
├── LICENSE                      ← MIT 许可
├── scripts/
│   ├── history_tui.py           ← 三层键盘 TUI 主程序
│   └── update_cache.py          ← JSONL→缓存索引扫描
└── .history_cache/              ← 缓存目录（自动生成）
