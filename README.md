# Claude History Browser

键盘驱动的 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) 历史会话浏览器 Skill。

## 快速安装

```bash
# 1. 克隆到 skills 目录
git clone https://github.com/GeistCber/claude-history-browser.git \
  ~/.claude/skills/history-search/

# 2. 安装依赖
pip install prompt_toolkit wcwidth

# 3. 在 Claude Code 中触发
# /history-search
```

## 三层导航

```
层 1: 会话列表  ──Enter──>  层 2: 问题列表  ──Enter──>  层 3: AI 回答原文
  ↑                            ↑                             ↑
  └── ESC                      └── ESC                       └── ESC
```

- **↑↓** 选择，**Enter** 进入，**ESC** 逐级返回
- AI 回答原文一字不改，Markdown 真实渲染
- 中日韩字符正确对齐
