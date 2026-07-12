# Claude History Browser

键盘驱动的 Cluade Code 历史会话浏览器 TUI。方向键导航，Enter 选中，ESC 逐级返回。

从 Cluade Code 的 JSONL 会话文件中读取历史，惰性加载 AI 回答原文，
用 prompt_toolkit 实现全屏交互界面，支持中日韩字符正确对齐。

## 预览

```
  SESSIONS
  ──────────────────────────────────────────────────────────────
  #1     07-12  1000字要求反馈                                       25条  ff48ee80
  #2     07-12  <command-message>history-search</command-message>   8条  ec8d348f
  #3     07-12  fix-ui-file-format                                   10条  678f5dc0
  ...
  ──────────────────────────────────────────────────────────────
  共 44 个会话 · 更新 2026-07-12
  ↑↓  PgUp/PgDn  Enter 选择  ESC/^C 退出
```

## 三层导航

| 层级 | 内容 | 操作 |
|------|------|------|
| 1 | 所有历史会话（按时间倒序） | ↑↓ 移动，Enter 进入 |
| 2 | 选中会话的历次提问列表 | ↑↓ 移动，Enter 查看 |
| 3 | AI 回答原文（Markdown 美化） | ↑↓ 滚动，☰ ESC 逐级返回 |

## 安装

```bash
pip install prompt_toolkit wcwidth
```

## 用法

```bash
# 1. 先扫描 JSONL 生成缓存（指向你的 Cluade Code 会话目录）
python scripts/update_cache.py \
  --jsonl-dir "$HOME/.claude/projects/C--Users-Laptop" \
  --cache-dir .history_cache

# 2. 打开浏览器
python scripts/history_tui.py \
  --jsonl-dir "$HOME/.claude/projects/C--Users-Laptop"
```

也支持环境变量：

```bash
export CLAUDE_JSONL_DIR="$HOME/.claude/projects/C--Users-Laptop"
export HISTORY_CACHE_DIR=".history_cache"
python scripts/update_cache.py
python scripts/history_tui.py
```

## Windows 用户

Cmd/PowerShell 下直接运行。Git Bash 下需要 `winpty`：

```bash
winpty python scripts/history_tui.py --jsonl-dir "C:/Users/Laptop/.claude/projects/C--Users-Laptop"
```

## 数据机制

| 机制 | 说明 |
|------|------|
| **列表** | 缓存 `.history_cache/sessions.json` + `{uuid}.json`，轻量只存元数据 |
| **回答** | 惰性加载，选中后才从 JSONL 读取，不预存 |
| **开关** | `.history_cache/.off` 存在时跳过缓存更新 |
| **自动** | 配合 SessionStart hook 自动调用 `update_cache.py` |

## 文件结构

```
claude-history-browser/
├── README.md
├── scripts/
│   ├── history_tui.py      # 三层 TUI 主程序
│   └── update_cache.py     # JSONL→缓存索引扫描
└── .history_cache/         # 缓存目录（自动生成）
    ├── .off                # 开关
    ├── sessions.json       # 会话列表
    └── {uuid}.json         # 每会话问题列表
```

## 特性

- **键盘驱动**：方向键 + PgUp/PgDn + Enter + ESC，全键盘操作
- **三级返回**：ESC 从层3→层2→层1→退出，不丢导航位置
- **中日韩对齐**：用 wcwidth 库正确处理东亚双宽字符
- **Markdown 美化**：标题/粗体/列表/代码块在终端中真实渲染
- **原文保证**：AI 回答原文一字不改，包括 Write 工具写入的文件内容
- **选中高亮**：通栏深灰蓝背景，清晰不刺眼
- **滚动条**：右侧指示进度
