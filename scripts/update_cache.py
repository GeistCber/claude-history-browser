#!/usr/bin/env python3
"""
update_cache.py — history-cache 轻量索引生成

从 JSONL 目录提取会话列表 + 每条会话的问题列表（不存 AI 回答正文），
写入 .history_cache/ 缓存目录，供 history_tui.py 读取。
"""
import json, glob, os, sys
from datetime import datetime


def run(jsonl_dir, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    off_file = os.path.join(cache_dir, ".off")
    if os.path.exists(off_file):
        print("[history-cache] SKIP — .off 文件存在")
        sys.exit(0)

    files = sorted(glob.glob(os.path.join(jsonl_dir, "[0-9a-f]*.jsonl")))
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

                    if d.get("type") == "ai-title" and d.get("aiTitle"):
                        title = d["aiTitle"]
                        have_ai_title = True

                    if first_ts == "0" * 20 and d.get("timestamp"):
                        first_ts = d["timestamp"]

                    if d.get("type") == "user" and d.get("message", {}).get("role") == "user":
                        content = d["message"].get("content", "")
                        text = ""
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text = item.get("text", "")
                                    break
                        if text and "tool_use_id" not in str(d):
                            if not user_count:
                                first_user_text = text[:60].replace("\n", " ").replace("\r", "")
                            user_count += 1
                            questions.append(text)

        except Exception as exc:
            print(f"  [warn] {uuid}: {exc}", file=sys.stderr)
            continue

        if user_count == 0:
            continue

        sessions.append({
            "uuid": uuid,
            "timestamp": first_ts,
            "title": (title if have_ai_title else (first_user_text[:50] or "(无标题)")),
            "first_msg": first_user_text,
            "count": user_count,
        })

        with open(os.path.join(cache_dir, f"{uuid}.json"), "w", encoding="utf-8") as f:
            json.dump({"uuid": uuid, "count": user_count, "questions": questions}, f, ensure_ascii=False)

    sessions.sort(key=lambda s: s["timestamp"], reverse=True)

    with open(os.path.join(cache_dir, "sessions.json"), "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "total": len(sessions),
            "sessions": sessions,
        }, f, ensure_ascii=False, indent=2)

    print(f"[history-cache] ✅ {len(sessions)} 个会话, {sum(s['count'] for s in sessions)} 条提问")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl-dir", required=True, help="JSONL 会话文件目录")
    ap.add_argument("--cache-dir", required=True, help="缓存输出目录")
    args = ap.parse_args()
    run(args.jsonl_dir, args.cache_dir)
