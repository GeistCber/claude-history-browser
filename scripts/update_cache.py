#!/usr/bin/env python3
"""
history-search 缓存更新器（轻量索引）
扫描 JSONL 会话文件，提取会话列表 + 每条会话的问题列表文本（不存答案）。
被 SessionStart hook 自动调用。

支持多项目扫描：遍历 ~/.claude/projects/ 下所有子目录。
向后兼容：同时写平铺式（sessions.json）和分项目式缓存。
"""
import argparse, json, glob, os, sys
from datetime import datetime


# ── 路径 ──────────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SKILL_DIR, ".history_cache")
DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
OFF_FILE = os.path.join(CACHE_DIR, ".off")

os.makedirs(CACHE_DIR, exist_ok=True)


# ── 辅助 ──────────────────────────────────────────────────────

def _safe_print(*a, **kw):
    try:
        print(*a, **kw)
    except UnicodeEncodeError:
        args = []
        for x in a:
            if isinstance(x, str):
                args.append(x.encode("ascii", errors="replace").decode("ascii"))
            else:
                args.append(x)
        print(*args, **kw)


def scan_project(project_path, project_name):
    """扫描单个项目目录，返回 (sessions_list, total_questions)"""
    files = sorted(glob.glob(os.path.join(project_path, "[0-9a-f]*.jsonl")))
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
            _safe_print(f"  [warn] {uuid}: {exc}", file=sys.stderr)
            continue

        if user_count == 0:
            continue  # 空会话跳过

        sessions.append({
            "uuid": uuid,
            "timestamp": first_ts,
            "title": (title if have_ai_title else (first_user_text[:50] or "(无标题)")),
            "first_msg": first_user_text,
            "count": user_count,
            "project": project_name,
        })

        # 写入该会话的问题列表缓存
        # 新的分项目路径
        proj_cache_dir = os.path.join(CACHE_DIR, project_name)
        os.makedirs(proj_cache_dir, exist_ok=True)
        with open(os.path.join(proj_cache_dir, f"{uuid}.json"), "w", encoding="utf-8") as f:
            json.dump({
                "uuid": uuid,
                "count": user_count,
                "questions": questions,
                "project": project_name,
            }, f, ensure_ascii=False)

        # 向后兼容：也写平铺式
        with open(os.path.join(CACHE_DIR, f"{uuid}.json"), "w", encoding="utf-8") as f:
            json.dump({
                "uuid": uuid,
                "count": user_count,
                "questions": questions,
                "project": project_name,
            }, f, ensure_ascii=False)

    total_q = sum(s["count"] for s in sessions)
    return sessions, total_q


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="history-search 缓存更新器"
    )
    parser.add_argument("--project", help="只扫描指定项目")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    # ── 开关 ──
    if os.path.exists(OFF_FILE):
        _safe_print("[history-cache] SKIP -- .off file exists")
        sys.exit(0)

    # ── 项目根目录 ──
    projects_root = os.environ.get("HISTORY_CACHE_PROJECTS_DIR", DEFAULT_PROJECTS_DIR)
    if not os.path.isdir(projects_root):
        _safe_print(f"[history-cache] ERROR: projects dir not found: {projects_root}", file=sys.stderr)
        sys.exit(2)

    # ── 发现项目 ──
    all_projects = []
    for name in sorted(os.listdir(projects_root)):
        path = os.path.join(projects_root, name)
        if os.path.isdir(path):
            all_projects.append((name, path))

    if args.project:
        filtered = [(n, p) for n, p in all_projects if n == args.project]
        if not filtered:
            _safe_print(f"[history-cache] ERROR: project '{args.project}' not found", file=sys.stderr)
            sys.exit(2)
        all_projects = filtered

    if not all_projects:
        _safe_print("[history-cache] SKIP -- no projects found")
        sys.exit(0)

    # ── 扫描每个项目 ──
    all_sessions = []
    grand_total_q = 0

    for proj_name, proj_path in all_projects:
        if args.verbose:
            _safe_print(f"[history-cache] Scanning [{proj_name}]...")
        sessions, total_q = scan_project(proj_path, proj_name)
        all_sessions.extend(sessions)
        grand_total_q += total_q

        # 写入分项目 sessions.json
        if sessions:
            proj_cache_dir = os.path.join(CACHE_DIR, proj_name)
            os.makedirs(proj_cache_dir, exist_ok=True)
            sorted_sessions = sorted(sessions, key=lambda s: s["timestamp"], reverse=True)
            with open(os.path.join(proj_cache_dir, "sessions.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": datetime.now().isoformat(),
                    "project": proj_name,
                    "total": len(sorted_sessions),
                    "sessions": sorted_sessions,
                }, f, ensure_ascii=False, indent=2)

    # ── 写入平铺式 sessions.json（向后兼容） ──
    all_sessions.sort(key=lambda s: s["timestamp"], reverse=True)
    with open(os.path.join(CACHE_DIR, "sessions.json"), "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "total": len(all_sessions),
            "sessions": all_sessions,
        }, f, ensure_ascii=False, indent=2)

    _safe_print(f"[history-cache] OK {len(all_sessions)} sessions, {grand_total_q} questions across {len(all_projects)} project(s)")
    sys.exit(0)


if __name__ == "__main__":
    main()
