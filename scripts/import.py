#!/usr/bin/env python3
"""
import.py -- Claude Code conversation history import tool

Reads a .claude-export directory (produced by export.py) and copies the JSONL
files into ~/.claude/projects/<project>/ on the target machine. Then optionally
rebuilds the history cache so the TUI can browse imported sessions.
"""
import argparse, json, os, shutil, subprocess, sys
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
CACHE_SCRIPT = os.path.join(SCRIPTS_DIR, "update_cache.py")


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


def validate_export(export_dir):
    meta_path = os.path.join(export_dir, "metadata.json")
    if not os.path.exists(meta_path):
        raise ValueError(f"Not a valid export: {meta_path} not found")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    required_keys = ["exported_at", "projects"]
    for key in required_keys:
        if key not in meta:
            raise ValueError(f"Invalid metadata.json: missing '{key}'")
    for proj_name in meta.get("projects", {}):
        proj_dir = os.path.join(export_dir, "projects", proj_name)
        if not os.path.isdir(proj_dir):
            raise ValueError(f"Project directory missing: {proj_dir}")
        proj_index = os.path.join(proj_dir, "index.json")
        if not os.path.exists(proj_index):
            raise ValueError(f"Project index missing: {proj_index}")
        proj_data = meta["projects"][proj_name]
        for uuid in proj_data.get("sessions", []):
            sess_path = os.path.join(proj_dir, f"{uuid}.jsonl")
            if not os.path.isfile(sess_path):
                raise ValueError(f"Session file missing: {sess_path}")
    return meta


def get_export_size(export_dir, meta):
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


def import_session(export_dir, project_name, target_project, uuid, overwrite, verbose=False):
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
    if not os.path.isfile(CACHE_SCRIPT):
        return (False, "update_cache.py not found")
    try:
        cmd = [sys.executable, CACHE_SCRIPT]
        if target_project:
            cmd.extend(["--project", target_project])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return (True, None)
        else:
            return (False, f"Cache update failed (exit {result.returncode}): {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        return (False, "Cache update timed out")
    except Exception as e:
        return (False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Claude Code conversation history import tool")
    parser.add_argument("--input", required=True, help="Path to .claude-export directory")
    parser.add_argument("--project", help="Remap to a different project name")
    parser.add_argument("--session", help="Import only this session UUID")
    parser.add_argument("--dry-run", action="store_true", help="Validate export without writing")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files on target")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--update-cache", action="store_true", help="Run update_cache.py after import")
    args = parser.parse_args()

    export_dir = os.path.abspath(args.input)
    if not os.path.isdir(export_dir):
        p(f"[import] ERROR: input directory not found: {export_dir}", file=sys.stderr)
        sys.exit(2)

    try:
        meta = validate_export(export_dir)
    except ValueError as e:
        p(f"[import] ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    projects_data = meta.get("projects", {})
    if not projects_data:
        p("[import] ERROR: no projects in export", file=sys.stderr)
        sys.exit(2)

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
                dst = os.path.join(os.path.expanduser(f"~/.claude/projects/{target_project}"), f"{uuid}.jsonl")
                if os.path.exists(dst):
                    existing.append(uuid)
                else:
                    new.append(uuid)
            p(f"    New: {len(new)}, Already exists: {len(existing)}")
        p(f"\n[import] Dry-run complete, no files written")
        sys.exit(0)

    imported = 0
    imported_bytes = 0
    errors = []
    warnings = []

    for proj_name, proj_data in projects_data.items():
        session_list = proj_data.get("sessions", [])
        if args.session:
            session_list = [s for s in session_list if s == args.session]
        if not session_list:
            continue
        target_project = args.project or proj_name
        for uuid in session_list:
            u, ok, err = import_session(export_dir, proj_name, target_project, uuid,
                                        overwrite=args.overwrite, verbose=args.verbose)
            if ok:
                imported += 1
                imported_bytes += os.path.getsize(
                    os.path.join(os.path.expanduser(f"~/.claude/projects/{target_project}"), f"{uuid}.jsonl"))
            else:
                if "warning" in (err or "").lower():
                    warnings.append((uuid, err))
                else:
                    errors.append((uuid, err))
                    eprint(f"  [error] {uuid}: {err}")

    p(f"\n[import] Import complete")
    p(f"  Source:    {export_dir}")
    p(f"  Sessions:  {imported}")
    p(f"  Size:      {imported_bytes:,} bytes ({imported_bytes/1024/1024:.1f} MB)")

    if errors:
        p(f"  Errors:    {len(errors)}")
        for uuid, err in errors:
            eprint(f"    - {uuid}: {err}")
        sys.exit(1)

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
