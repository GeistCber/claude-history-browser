#!/usr/bin/env python3
"""
history-search 缓存更新器（轻量索引）
扫描 JSONL 会话文件，提取会话列表 + 每条会话的问题列表文本（不存答案）。
被 SessionStart hook 自动调用。
"""
import json, glob, os, sys
from datetime import datetime

# ── 路径 ──────────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SKILL_DIR, ".history_cache")
JSONL_DIR = r"C:\Users\Laptop\.claude\projects\C--Users-Laptop"
OFF_FILE = os.path.join(CACHE_DIR, ".off")

os.makedirs(CACHE_DIR, exist_ok=True)

# ── 开关 ──────────────────────────────────────────────────────
if os.path.exists(OFF_FILE):
    print("[history-cache] SKIP — .off 文件存在")
    sys.exit(0)

# ── 扫描 ──────────────────────────────────────────────────────
files = sorted(glob.glob(os.path.join(JSONL_DIR, "[0-9a-f]*.jsonl")))
sessions = []

for fpath in files:
    uuid = os.path.basename(fpath).replace(".jsonl", "")
    first_ts = "0" * 20
    title = ""
    first_user_text = ""
    user_count = 0
    questions = []
    have_ai_title = False

    try:
        with open(fpath, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 标题（优先取 AI 生成的标题）
                if d.get("type") == "ai-title" and d.get("aiTitle"):
                    title = d["aiTitle"]
                    have_ai_title = True

                # 首次时间戳
                if first_ts == "0" * 20 and d.get("timestamp"):
                    first_ts = d["timestamp"]

                # 用户提问（跳过 tool_result 回传内容）
                is_user = False
                text = ""

                if d.get("type") == "user" and d.get("message", {}).get("role") == "user":
                    is_user = True
                    content = d["message"].get("content", "")
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text = item.get("text", "")
                                break

                if is_user and text and "tool_use_id" not in str(d):
                    if not user_count:
                        first_user_text = text[:60].replace("\n", " ").replace("\r", "")
                    user_count += 1
                    questions.append(text)

    except Exception as exc:
        print(f"  [warn] {uuid}: {exc}", file=sys.stderr)
        continue

    if user_count == 0:
        continue  # 空会话跳过

    sessions.append({
        "uuid": uuid,
        "timestamp": first_ts,
        "title": (title if have_ai_title else (first_user_text[:50] or "(无标题)")),
        "first_msg": first_user_text,
        "count": user_count,
    })

    # 写入该会话的问题列表缓存（仅文本，不存答案）
    with open(os.path.join(CACHE_DIR, f"{uuid}.json"), "w", encoding="utf-8") as f:
        json.dump({"uuid": uuid, "count": user_count, "questions": questions}, f, ensure_ascii=False)

# ── 排序 + 写出 ──────────────────────────────────────────────
sessions.sort(key=lambda s: s["timestamp"], reverse=True)

with open(os.path.join(CACHE_DIR, "sessions.json"), "w", encoding="utf-8") as f:
    json.dump({
        "updated_at": datetime.now().isoformat(),
        "total": len(sessions),
        "sessions": sessions,
    }, f, ensure_ascii=False, indent=2)

print(f"[history-cache] ✅ {len(sessions)} 个会话, {sum(s['count'] for s in sessions)} 条提问")
