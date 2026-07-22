---
name: history-search
description: >
  双栏搜索浏览器的 TUI，支持Vim键位操作，Enter 确认，ESC 取消返回。
  从本地缓存提取历史/收藏记录，动态构建 AI 浏览树结构（单次不重复）。
---

# history-search — 会话历史 TUI 浏览器

## 启动方式

当用户调用此技能时，按以下步骤执行：

1. **检查缓存**：确认 `.history_cache/sessions.json` 存在，否则提示运行 `update_cache.py`
2. **显示会话概览**：打印最近会话的简单摘要（项目、条数、时间）
3. **引导启动 TUI**：根据操作系统告诉用户适合的命令，或在当前对话输入带 `!` 前缀的版本。

   **Linux / macOS（PowerShell / bash 均支持 `~`）：**
   ```bash
   python ~/.claude/skills/history-search/scripts/history_tui.py
   # 或在本对话：
   ! python ~/.claude/skills/history-search/scripts/history_tui.py
   ```

   **Windows cmd：**
   ```cmd
   python %USERPROFILE%\.claude\skills\history-search\scripts\history_tui.py
   ```

   **Windows PowerShell：**
   ```powershell
   python $env:USERPROFILE\.claude\skills\history-search\scripts\history_tui.py
   ```

   > `!` 前缀会将命令在本会话中执行，输出直接显示在对话中。

## 双栏操作

| 栏位 | 功能 | 快捷键 |
|---|---|---|
| 1 | 最新浏览记录（含时间权重），显示 `[记录数]` 和操作提示 `[E]` | → 切换，Enter 查看，`x` 操作模式，ESC/^C 退出 |
| 2 | 对浏览记录的AI分析文件夹 | → 切换，Enter 展开树，ESC 返回1 |
| 3 | AI 浏览树结构（单次不重复，含 Write 功能），时间排序与切换不冲突 | → 收藏/分析文件夹，PgUp/PgDn 滚动，ESC 返回2 |

### 快捷键表

| 按键 | 栏1 | 栏2 | 栏3 |
|---|---|---|---|
| `→` `←` | 切换分析到浏览记录 | 切换分析到收藏 | 返回上一级，回到分析文件夹 |
| `PgUp` `PgDn` | 向上滚动 | 向上滚动 | 滚动导航，回到分析文件夹 |
| `Enter` | 查看所选记录的日记文件夹 | 展开所选收藏的树 | — |
| `ESC` | 退出界面 | 返回1 | 返回2 |
| `x` | 打开导出模式（Export） | — | — |
| `i` | 打开导入模式（Import） | — | — |

## 导入模式（Import Mode）

在栏 1 会话列表按 `i` 进入导入模式，流程如下：

1. **选择导出目录**：自动扫描 `~/.claude/skills/history-search/` 下以 `claude-export-` 开头的目录
2. **预览会话**：显示导出目录中的会话列表（支持 Space 勾选/A 项目全选）
3. **选择目标项目**：默认导入到 `~/.claude/projects/imported/`（可修改）
4. **执行导入**：Enter 确认后，将会话 JSONL 复制到 `~/.claude/projects/<project>/` 并重建缓存
5. **刷新列表**：新导入的会话出现在列表中，状态栏显示导入结果

快捷键：`Space` 勾选、`A` 项目全选、`Enter` 执行、`ESC` 取消返回

## /resume 集成

导入的会话会被复制到 `~/.claude/projects/` 下，Claude Code 的 `/resume <uuid>` 命令会自动搜索该目录。

导入完成后，在 Claude 终端直接运行即可继续对话：

```
/resume <uuid>
```

> 只有通过 `/resume <uuid>` 能成功恢复的会话才算导入成功。导入过程会验证 JSONL 文件的完整性（至少包含一条 user 和一条 assistant 消息）。

## 数据存储

- **缓存路径**：`.history_cache/.off` 存放在技能目录下
- **缓存内容**：`sessions.json` + `{uuid}.json`，仅索引（问题列表），不含完整答案
- **会话来源**：监听 `~/.claude/projects/` 下所有会话文件夹
- **自动更新**：由 SessionStart hook 触发 `scripts/update_cache.py`

## 依赖

```bash
pip install prompt_toolkit wcwidth
```
