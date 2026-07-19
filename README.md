# Claude History Browser

键盘驱动的 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) 历史会话浏览器 Skill。
支持多项目浏览、可视化导出与跨机导入。

## 快速安装

```bash
# 1. 克隆到 skills 目录
git clone https://github.com/GeistCber/claude-history-browser.git \
  ~/.claude/skills/history-search/

# 2. 安装依赖
pip install prompt_toolkit wcwidth

# 3. 更新缓存
python ~/.claude/skills/history-search/scripts/update_cache.py

# 4. 启动 TUI
python ~/.claude/skills/history-search/scripts/history_tui.py
```

## 三层导航

```
层 1: 会话列表  ──Enter──>  层 2: 问题列表  ──Enter──>  层 3: AI 回答原文
  ↑                            ↑                             ↑
  └── ESC                      └── ESC                       └── ESC
```

- **↑↓** 选择或滚动，**Enter** 进入，**ESC** 逐级返回
- 层3的头部（时间戳+问题）**固定不动**，只滚动回答正文
- 右侧滚动条支持**鼠标左键按住拖动**
- AI 回答原文一字不改，Markdown 真实渲染
- 中日韩字符正确对齐

## 可视化导出

在 TUI 层1按 **`x`** 进入导出模式：

| 按键 | 功能 |
|------|------|
| `x` | 进入/退出导出模式 |
| `Space` | 选中/取消当前会话 |
| `a` | 全选/取消当前项目所有会话 |
| `Enter` | 执行导出 |
| `ESC` | 退出导出模式或结果页 |

导出目录结构：
```
claude-export-{timestamp}/
  metadata.json          # 导出清单（版本、项目、会话数）
  projects/
    C--Users-Laptop/
      {uuid}.jsonl       # 会话原文
      {uuid}/subagents/  # 子 agent 日志
      index.json         # 项目索引
  markdown/              # --format md 时生成人类可读版
```

## 跨机同步

**导出（源机器）：**

```bash
cd ~/.claude/skills/history-search/scripts

# 命令行导出全部
python export.py --output ./backup-20260719

# 或 TUI 中按 x 可视化选择后 Enter
```

**导入（目标机器）：**

```bash
cd ~/.claude/skills/history-search/scripts

# 验证
python import.py --input ./backup-20260719 --dry-run

# 导入 + 重建缓存
python import.py --input ./backup-20260719 --overwrite --update-cache

# 启动 TUI 浏览
python history_tui.py
```

目标机器只需 Claude Code + history-search skill 脚本即可，不需要源机器的整个环境。

## 多项目支持

自动扫描 `~/.claude/projects/` 下所有项目。TUI 层1每行显示 `[项目简称]` 标签：

```
[E][Laptop]   #1    07-18  export-import-history
   [Laptop]   #2    07-12  1000字要求反馈
   [Desktop]  #3    06-28  shared_ptr 用法示例
```

- `[E]` = 已导出标记
- `[项目简称]` = 归属项目

## 数据机制

- **开关**：`.history_cache/.off` 存在时跳过缓存更新
- **缓存**（轻量索引，不存回答正文）：`sessions.json` + `{uuid}.json`，支持多项目分目录存储
- **项目感知**：自动扫描 `~/.claude/projects/` 下所有项目目录
- **惰性加载**：回答原文实时从 JSONL 读取，不预存
- **自动更新**：SessionStart hook 调用 `scripts/update_cache.py`

## 文件结构

```
~/.claude/skills/history-search/
├── SKILL.md                     ← Skill 定义（Claude Code 识别入口）
├── README.md                    ← GitHub 项目说明
├── LICENSE                      ← MIT 许可
├── scripts/
│   ├── history_tui.py           ← 三层键盘 TUI 主程序（含可视化导出、可拖动滚动条）
│   ├── update_cache.py          ← JSONL→缓存索引扫描（多项目）
│   ├── export.py                ← 对话导出工具
│   └── import.py                ← 对话导入工具
└── .history_cache/              ← 缓存目录（自动生成）
```
