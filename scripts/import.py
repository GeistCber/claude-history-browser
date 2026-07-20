#!/usr/bin/env python3
"""
import.py -- Claude Code conversation history import tool

Reads a .claude-export directory (produced by export.py) and copies the JSONL
files into ~/.claude/projects/<project>/ on the target machine. Then optionally
rebuilds the history cache so the TUI can browse imported sessions.

核心原理：
  导出 = shutil.copy2() 把 ~/.claude/projects/ 下的 .jsonl 文件复制到一个便携目录。
  导入 = shutil.copy2() 把便携目录里的 .jsonl 文件复制回 ~/.claude/projects/。
  全程文件级操作，无需手动编辑任何 JSON 内容。

典型流程（推荐完整命令）：
  1. 预览：python import.py --input ./backup-20260720 --dry-run
  2. 导入：python import.py --input ./backup-20260720 --update-cache

参数：
  --input        必需。导出的 .claude-export 目录路径。
  --project      将导入的会话放到不同的项目名下（重命名）。
  --session      只导入指定 UUID 的单条会话。
  --dry-run      预览模式：只验证和列出将要执行的操作，不写任何文件。
  --overwrite    如果目标文件已存在，覆盖之（默认跳过）。
  --update-cache 导入后自动跑 update_cache.py 重建历史缓存（推荐）。
  --verbose      打印详细日志。

注意事项：
  - 默认遇到已存在的文件会跳过（不会覆盖）。确认要替换时加 --overwrite。
  - --update-cache 会自动运行，如果失败可在导入后手动执行：
      python scripts/update_cache.py
  - 导入的会话可以在 TUI 三层浏览器中查看：python scripts/history_tui.py

示例：
  python scripts/import.py --input ./backup-20260720 --dry-run
  python scripts/import.py --input ./backup-20260720 --overwrite
  python scripts/import.py --input ./backup-20260720 --project MyNewProject
  python scripts/import.py --input ./backup-20260720 --update-cache
  python scripts/import.py --input ./backup-20260720 -s <uuid> --update-cache
"""
import argparse, json, os, shutil, subprocess, sys
from datetime import datetime


# ── Paths ─────────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
CACHE_SCRIPT = os.path.join(SCRIPTS_DIR, "update_cache.py")


# ── Safe print (GBK-safe) ─────────────────────────────────────

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


def p(*a, **kw):
    _safe_print(*a, **kw)


def eprint(*a, **kw):
    kw["file"] = sys.stderr
    _safe_print(*a, **kw)


# ── Validation ────────────────────────────────────────────────

def validate_export(export_dir):
    """Validate export directory structure. Returns metadata dict or raises."""
    meta_path = os.path.join(export_dir, "metadata.json")
    if not os.path.exists(meta_path):
        raise ValueError(f"Not a valid export: {meta_path} not found")

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    required_keys = ["exported_at", "projects"]
    for key in required_keys:
        if key not in meta:
            raise ValueError(f"Invalid metadata.json: missing '{key}'")

    # Validate each listed project has its directory
    for proj_name in meta.get("projects", {}):
        proj_dir = os.path.join(export_dir, "projects", proj_name)
        if not os.path.isdir(proj_dir):
            raise ValueError(f"Project directory missing: {proj_dir}")

        proj_index = os.path.join(proj_dir, "index.json")
        if not os.path.exists(proj_index):
            raise ValueError(f"Project index missing: {proj_index}")

        # Verify each listed session file exists
        proj_data = meta["projects"][proj_name]
        for uuid in proj_data.get("sessions", []):
            sess_path = os.path.join(proj_dir, f"{uuid}.jsonl")
            if not os.path.isfile(sess_path):
                raise ValueError(f"Session file missing: {sess_path}")

    return meta


def check_path_traversal(base_dir, target_path):
    """Reject paths that escape outside base_dir."""
    real_base = os.path.realpath(base_dir)
    real_target = os.path.realpath(target_path)
    if not real_target.startswith(real_base + os.sep) and real_target != real_base:
        raise ValueError(f"Path traversal detected: {target_path}")
    return real_target


def get_export_size(export_dir, meta):
    """Calculate total size of all files in the export."""
    total = 0
    projects_root = os.path.join(export_dir, "projects")
    for proj_name in meta.get("projects", {}):
        proj_dir = os.path.join(projects_root, proj_name)
        for root, dirs, files in os.walk(proj_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass
    return total


# ── Core import logic ────────────────────────────────────────

def import_session(export_dir, project_name, target_project, uuid,
                   overwrite, verbose=False):
    """Import a single session from export to target projects directory.

    Returns (uuid, ok, error_msg)
    """
    src = os.path.join(export_dir, "projects", project_name, f"{uuid}.jsonl")
    dst_dir = os.path.expanduser(f"~/.claude/projects/{target_project}")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{uuid}.jsonl")

    if os.path.exists(dst) and not overwrite:
        return (uuid, False, f"Already exists (use --overwrite): {dst}")

    try:
        shutil.copy2(src, dst)
        size = os.path.getsize(dst)
    except OSError as e:
        return (uuid, False, str(e))

    # Import subagent subdirectory (if present in export)
    src_sub = os.path.join(export_dir, "projects", project_name, uuid)
    if os.path.isdir(src_sub):
        dst_sub = os.path.join(dst_dir, uuid)
        try:
            if os.path.exists(dst_sub) and overwrite:
                shutil.rmtree(dst_sub)
            if not os.path.exists(dst_sub):
                shutil.copytree(src_sub, dst_sub)
        except OSError as e:
            return (uuid, True, f"Subagent copy warning: {e}")

    if verbose:
        eprint(f"    OK {uuid} ({size:,} bytes)")

    return (uuid, True, None)


def run_cache_update(target_project, verbose=False):
    """Run update_cache.py for the imported project."""
    if not os.path.isfile(CACHE_SCRIPT):
        return (False, "update_cache.py not found")

    try:
        cmd = [sys.executable, CACHE_SCRIPT]
        if target_project:
            cmd.extend(["--project", target_project])
        if verbose:
            eprint(f"  Running: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if verbose:
                for line in result.stdout.strip().split("\n"):
                    eprint(f"    {line}")
            return (True, None)
        else:
            return (False, f"Cache update failed (exit {result.returncode}): {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        return (False, "Cache update timed out")
    except Exception as e:
        return (False, str(e))


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Claude Code conversation history import tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "━━━ 快速入门 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "  1. 先预览：python import.py --input ./backup --dry-run\n"
            "  2. 正式导入：python import.py --input ./backup --update-cache\n"
            "  3. 打开看：python ../scripts/history_tui.py\n"
            "\n"
            "━━━ 常见场景 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "  # 完整流程（推荐）：预览 → 导入+更新缓存 → 打开TUI\n"
            "  python import.py --input ./backup-20260720 --dry-run\n"
            "  python import.py --input ./backup-20260720 --update-cache\n"
            "  python ../scripts/history_tui.py\n"
            "\n"
            "  # 覆盖已有文件\n"
            "  python import.py --input ./backup --overwrite\n"
            "\n"
            "  # 导入后改名（目标项目不存在则自动创建）\n"
            "  python import.py --input ./backup --project MyNewProject\n"
            "\n"
            "  # 只导入一个会话\n"
            "  python import.py --input ./backup --session <uuid>\n"
            "\n"
            "━━━ 工作原理 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "  导出生成了一个 .claude-export 目录，里面是 .jsonl 文件。\n"
            "  导入就是把那些 .jsonl 文件复制到 ~/.claude/projects/ 下，\n"
            "  不需要手动编辑任何 JSON 内容。\n"
        ),
    )
    parser.add_argument("--input", required=True,
                        help="Path to .claude-export directory")
    parser.add_argument("--project", help="Remap to a different project name")
    parser.add_argument("--session", help="Import only this session UUID")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate export without writing")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing files on target")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--update-cache", action="store_true",
                        help="Run update_cache.py after import")
    args = parser.parse_args()

    # ── Resolve input path ──
    export_dir = os.path.abspath(args.input)
    if not os.path.isdir(export_dir):
        p(f"[import] ERROR: input directory not found: {export_dir}", file=sys.stderr)
        sys.exit(2)

    # ── Validate export ──
    try:
        meta = validate_export(export_dir)
    except ValueError as e:
        p(f"[import] ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    source_info = (
        f"exported_at: {meta.get('exported_at', 'unknown')}, "
        f"source: {meta.get('source_hostname', 'unknown')}"
    )
    p(f"[import] Valid export: {source_info}")
    p(f"[import] Source projects: {', '.join(meta.get('projects', {}).keys())}")

    # ── Filter projects ──
    projects_data = meta.get("projects", {})
    if not projects_data:
        p("[import] ERROR: no projects in export", file=sys.stderr)
        sys.exit(2)

    # ── Count sessions ──
    total_sessions = 0
    for proj_name, proj_data in projects_data.items():
        session_list = proj_data.get("sessions", [])
        if args.session:
            session_list = [s for s in session_list if s == args.session]
        if not session_list:
            continue
        total_sessions += len(session_list)

    total_size = get_export_size(export_dir, meta)

    p(f"[import] Sessions to import: {total_sessions}")
    p(f"[import] Total size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")

    # ── Check disk space ──
    target_dir = os.path.expanduser("~/.claude/projects")
    try:
        usage = shutil.disk_usage(os.path.dirname(target_dir))
        free_mb = usage.free / 1024 / 1024
        if free_mb < total_size / 1024 / 1024 * 2:
            p(f"[import] WARNING: low disk space ({free_mb:.0f} MB free, "
              f"{total_size/1024/1024:.0f} MB needed)", file=sys.stderr)
    except Exception:
        pass

    # ── Check for UUID collisions ──
    all_uuids = []
    for proj_data in projects_data.values():
        all_uuids.extend(proj_data.get("sessions", []))
    if len(all_uuids) != len(set(all_uuids)):
        p("[import] WARNING: duplicate session UUIDs found across projects")

    # ── Dry-run ──
    if args.dry_run:
        p(f"\n[import] -- Dry-run mode (no files written) --")
        for proj_name, proj_data in projects_data.items():
            session_list = proj_data.get("sessions", [])
            if args.session:
                session_list = [s for s in session_list if s == args.session]
            if not session_list:
                continue
            target_project = args.project or proj_name
            p(f"\n  [{proj_name}] -> [{target_project}] ({len(session_list)} sessions):")
            existing = []
            new = []
            for uuid in session_list:
                dst = os.path.join(os.path.expanduser(f"~/.claude/projects/{target_project}"),
                                   f"{uuid}.jsonl")
                if os.path.exists(dst):
                    existing.append(uuid)
                else:
                    new.append(uuid)
            p(f"    New: {len(new)}, Already exists: {len(existing)}")
            if existing and not args.overwrite:
                p(f"    NOTE: {len(existing)} file(s) exist, use --overwrite to replace")
            if existing:
                for uuid in existing:
                    p(f"    [EXISTS] {uuid}")

        # Check target project directories exist
        target_projects = set()
        for proj_name in projects_data:
            target_projects.add(args.project or proj_name)
        missing_projects = []
        existing_projects = []
        for tp in target_projects:
            tp_path = os.path.join(target_dir, tp)
            if os.path.isdir(tp_path):
                existing_projects.append(tp)
            else:
                missing_projects.append(tp)
        if missing_projects:
            p(f"\n  New project dirs to create: {', '.join(missing_projects)}")
        if existing_projects:
            p(f"  Existing project dirs: {', '.join(existing_projects)}")

        p(f"\n[import] Dry-run complete, no files written")
        sys.exit(0)

    # ── Execute import ──
    imported = 0
    imported_bytes = 0
    errors = []
    warnings = []
    any_subagent_warning = False

    for proj_name, proj_data in projects_data.items():
        session_list = proj_data.get("sessions", [])
        if args.session:
            session_list = [s for s in session_list if s == args.session]
        if not session_list:
            continue

        target_project = args.project or proj_name
        if args.verbose:
            eprint(f"\n[import] [{proj_name}] -> [{target_project}]")

        for uuid in session_list:
            u, ok, err = import_session(
                export_dir, proj_name, target_project, uuid,
                overwrite=args.overwrite, verbose=args.verbose
            )
            if ok:
                imported += 1
                imported_bytes += os.path.getsize(
                    os.path.join(os.path.expanduser(f"~/.claude/projects/{target_project}"),
                                 f"{uuid}.jsonl")
                )
            else:
                if "warning" in (err or "").lower():
                    warnings.append((uuid, err))
                    any_subagent_warning = True
                else:
                    errors.append((uuid, err))
                    eprint(f"  [error] {uuid}: {err}")

    # ── Report ──
    p(f"\n[import] Import complete")
    p(f"  Source:    {export_dir}")
    p(f"  Target:    {target_dir}")
    p(f"  Sessions:  {imported}")
    p(f"  Size:      {imported_bytes:,} bytes ({imported_bytes/1024/1024:.1f} MB)")

    if warnings:
        p(f"  Warnings:  {len(warnings)}")
        if args.verbose:
            for uuid, err in warnings:
                eprint(f"    - {uuid}: {err}")

    if errors:
        p(f"  Errors:    {len(errors)}")
        for uuid, err in errors:
            eprint(f"    - {uuid}: {err}")
        sys.exit(1)

    # ── Update cache ──
    if args.update_cache:
        target_project = args.project or list(projects_data.keys())[0]
        p(f"\n[import] Rebuilding history cache...")
        ok, err = run_cache_update(target_project, verbose=args.verbose)
        if ok:
            p(f"  [import] Cache rebuilt")
        else:
            p(f"  [import] WARNING: {err}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
