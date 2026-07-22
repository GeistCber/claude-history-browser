#!/usr/bin/env python3
"""
export.py -- Claude Code conversation history export tool

Packages ~/.claude/projects/ conversations into a portable directory tree.
Import on another machine with import.py for history-search TUI browsing.
"""
import argparse, glob, json, os, platform, shutil, sys
from datetime import datetime
from collections import defaultdict

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SKILL_DIR, ".history_cache")
DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
TOOL_VERSION = "1.0.0"
KNOWN_VERSIONS = {"2.1.179", "2.1.186", "2.1.191", "2.1.205", "2.1.206"}


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


def eprint(*a, **kw):
    kw["file"] = sys.stderr
    _safe_print(*a, **kw)


def p(*a, **kw):
    _safe_print(*a, **kw)


def get_file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def count_user_messages(jsonl_path):
    count = 0
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "user":
                    count += 1
    except Exception:
        pass
    return count


def collect_versions(jsonl_path):
    versions = set()
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if '"version"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                v = d.get("version")
                if v:
                    versions.add(v)
    except Exception:
        pass
    return versions


def discover_projects(projects_root):
    if not os.path.isdir(projects_root):
        return []
    projects = []
    for name in sorted(os.listdir(projects_root)):
        path = os.path.join(projects_root, name)
        if os.path.isdir(path):
            projects.append((name, path))
    return projects


def collect_sessions(project_path, session_uuid=None, verbose=False):
    sessions = []
    items = sorted(os.listdir(project_path))
    for name in items:
        if not name.endswith(".jsonl"):
            continue
        uuid = name[:-6]
        if session_uuid and uuid != session_uuid:
            continue
        jsonl_path = os.path.join(project_path, name)
        if not os.path.isfile(jsonl_path):
            continue
        subdir_path = os.path.join(project_path, uuid)
        has_subdir = os.path.isdir(subdir_path)
        sessions.append({
            "uuid": uuid,
            "jsonl_path": jsonl_path,
            "has_subdir": has_subdir,
            "subdir_path": subdir_path if has_subdir else None,
        })
        if verbose:
            extra = " [subagents]" if has_subdir else ""
            eprint(f"    -> {uuid}{extra}")
    return sessions


def export_session(export_base, project_name, session, verbose=False):
    uuid = session["uuid"]
    proj_dir = os.path.join(export_base, "projects", project_name)
    os.makedirs(proj_dir, exist_ok=True)
    dst_jsonl = os.path.join(proj_dir, f"{uuid}.jsonl")
    try:
        shutil.copy2(session["jsonl_path"], dst_jsonl)
        size = get_file_size(dst_jsonl)
    except OSError as e:
        return (uuid, 0, False, str(e))
    if session["has_subdir"]:
        dst_sub = os.path.join(proj_dir, uuid)
        try:
            if os.path.exists(dst_sub):
                shutil.rmtree(dst_sub)
            shutil.copytree(session["subdir_path"], dst_sub)
        except OSError as e:
            return (uuid, size, True, f"subagent copy failed: {e}")
    if verbose:
        eprint(f"    OK {uuid} ({size:,} bytes)")
    return (uuid, size, True, None)


def write_metadata(export_base, meta):
    path = os.path.join(export_base, "metadata.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return path


def write_project_index(export_base, project_name, sessions):
    proj_dir = os.path.join(export_base, "projects", project_name)
    index_path = os.path.join(proj_dir, "index.json")
    entries = []
    total_size = 0
    for s in sessions:
        size = get_file_size(s["jsonl_path"])
        total_size += size
        entries.append({
            "uuid": s["uuid"],
            "size": size,
            "has_subagents": s["has_subdir"],
            "user_count": count_user_messages(s["jsonl_path"]),
        })
    index = {
        "project": project_name,
        "session_count": len(sessions),
        "total_size_bytes": total_size,
        "sessions": entries,
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return index_path


def export_history_cache(export_base, verbose=False):
    if not os.path.isdir(CACHE_DIR):
        if verbose:
            eprint("  [skip] .history_cache not found")
        return
    dst = os.path.join(export_base, "history_cache")
    try:
        shutil.copytree(CACHE_DIR, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        if verbose:
            eprint("  OK cache copied -> history_cache/")
    except OSError as e:
        eprint(f"  [warn] cache copy failed: {e}")


def generate_markdown(export_base, project_name, sessions, verbose=False):
    md_dir = os.path.join(export_base, "markdown", project_name)
    os.makedirs(md_dir, exist_ok=True)
    for s in sessions:
        uuid = s["uuid"]
        jsonl_path = s["jsonl_path"]
        lines = []
        try:
            with open(jsonl_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    lines.append(d)
        except Exception as e:
            if verbose:
                eprint(f"  [warn] {uuid} markdown failed: {e}")
            continue
        md = []
        md.append(f"# Session: {uuid}\n")
        md.append(f"> Exported: {datetime.now().isoformat()}\n")
        for d in lines:
            t = d.get("type")
            ts = (d.get("timestamp") or "")[:19].replace("T", " ")
            if t == "user":
                content = d.get("message", {}).get("content", "")
                if isinstance(content, list):
                    text_parts = [
                        x.get("text", "") for x in content
                        if isinstance(x, dict) and x.get("type") == "text"
                    ]
                    content = " ".join(text_parts)
                user_msg = content.strip() if isinstance(content, str) else str(content)
                if user_msg and "tool_use_id" not in str(d):
                    md.append(f"\n## Q {ts}\n\n{user_msg}\n")
            elif t == "assistant":
                content = d.get("message", {}).get("content", [])
                text_parts = []
                for x in content:
                    if isinstance(x, dict) and x.get("type") == "text":
                        text_parts.append(x.get("text", ""))
                    elif isinstance(x, dict) and x.get("type") == "tool_use":
                        fp = x.get("input", {}).get("file_path", "")
                        fc = x.get("input", {}).get("content", "")
                        if fp and fc:
                            text_parts.append(f"\n> [Write] {fp}\n```\n{fc}\n```\n")
                if text_parts:
                    answer = "\n".join(text_parts)
                    md.append(f"\n## A {ts}\n\n{answer}\n")
        content = "\n".join(md)
        md_path = os.path.join(md_dir, f"{uuid}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        if verbose:
            eprint(f"    OK {uuid}.md ({len(content):,} chars)")


def main():
    parser = argparse.ArgumentParser(description="Claude Code conversation history export tool")
    parser.add_argument("--project", help="Export only this project")
    parser.add_argument("--session", help="Export only this session UUID")
    parser.add_argument("--output", help="Output directory (default: ./claude-export-{timestamp})")
    parser.add_argument("--format", choices=["json", "md"], default="json",
                        help='Output format: "json" = JSONL archive, "md" = also generate Markdown')
    parser.add_argument("--include-cache", action="store_true", help="Include .history_cache data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without copying")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    projects_root = os.environ.get("HISTORY_CACHE_PROJECTS_DIR", DEFAULT_PROJECTS_DIR)
    if not os.path.isdir(projects_root):
        p(f"[export] ERROR: projects directory not found: {projects_root}", file=sys.stderr)
        sys.exit(2)

    all_projects = discover_projects(projects_root)
    if not all_projects:
        p(f"[export] ERROR: no projects found", file=sys.stderr)
        sys.exit(2)

    if args.project:
        filtered = [(n, p) for n, p in all_projects if n == args.project]
        if not filtered:
            p(f"[export] ERROR: project '{args.project}' does not exist", file=sys.stderr)
            sys.exit(2)
        all_projects = filtered

    project_sessions = {}
    total_sessions = 0
    total_bytes = 0
    all_versions = set()

    for proj_name, proj_path in all_projects:
        sessions = collect_sessions(proj_path, session_uuid=args.session, verbose=args.verbose)
        if not sessions:
            continue
        project_sessions[proj_name] = sessions
        total_sessions += len(sessions)
        for s in sessions:
            total_bytes += get_file_size(s["jsonl_path"])
            for v in collect_versions(s["jsonl_path"]):
                all_versions.add(v)

    if not project_sessions:
        p(f"[export] ERROR: no sessions to export", file=sys.stderr)
        sys.exit(2)

    if args.dry_run:
        p(f"\n[export] -- Dry-run mode (no files written) --\n")
        p(f"  Source:        {projects_root}")
        p(f"  Projects:      {len(project_sessions)}")
        p(f"  Sessions:      {total_sessions}")
        p(f"  Total size:    {total_bytes:,} bytes ({total_bytes/1024/1024:.1f} MB)")
        for proj_name, sessions in project_sessions.items():
            p(f"\n  [{proj_name}] ({len(sessions)} sessions):")
            for s in sessions:
                sz = get_file_size(s["jsonl_path"])
                sub = " [sub]" if s["has_subdir"] else ""
                p(f"    - {s['uuid']} ({sz:,} bytes){sub}")
        p(f"\n[export] Dry-run complete, no files written")
        sys.exit(0)

    if args.output:
        export_base = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_base = f"claude-export-{ts}"

    if os.path.exists(export_base):
        p(f"[export] ERROR: output directory already exists: {export_base}", file=sys.stderr)
        sys.exit(2)

    os.makedirs(export_base)
    os.makedirs(os.path.join(export_base, "projects"))

    exported_count = 0
    exported_bytes = 0
    errors = []
    project_meta = {}

    for proj_name, sessions in project_sessions.items():
        for s in sessions:
            uuid, size, ok, err = export_session(export_base, proj_name, s, verbose=args.verbose)
            if ok:
                exported_count += 1
                exported_bytes += size
            else:
                errors.append((uuid, err))
                eprint(f"  [error] {uuid}: {err}")
        write_project_index(export_base, proj_name, sessions)
        project_meta[proj_name] = {
            "session_count": len(sessions),
            "total_size_bytes": sum(get_file_size(s["jsonl_path"]) for s in sessions),
            "sessions": [s["uuid"] for s in sessions],
        }

    if args.include_cache:
        export_history_cache(export_base, verbose=args.verbose)

    if args.format == "md":
        for proj_name, sessions in project_sessions.items():
            generate_markdown(export_base, proj_name, sessions, verbose=args.verbose)

    meta = {
        "exported_at": datetime.now().isoformat(),
        "source_hostname": platform.node(),
        "source_platform": sys.platform,
        "claude_version_range": sorted(all_versions) if all_versions else list(KNOWN_VERSIONS),
        "projects": project_meta,
        "tool": "history-search/export.py",
        "tool_version": TOOL_VERSION,
        "summary": {
            "total_projects": len(project_sessions),
            "total_sessions": exported_count,
            "total_size_bytes": exported_bytes,
        },
    }
    meta_path = write_metadata(export_base, meta)

    p(f"\n[export] Export complete")
    p(f"  Output:   {os.path.abspath(export_base)}")
    p(f"  Projects: {len(project_sessions)}")
    p(f"  Sessions: {exported_count}")
    p(f"  Size:     {exported_bytes:,} bytes ({exported_bytes/1024/1024:.1f} MB)")
    p(f"  Manifest: {meta_path}")

    if errors:
        p(f"\n[export] WARNING: {len(errors)} error(s):")
        for uuid, err in errors:
            p(f"  - {uuid}: {err}")
        sys.exit(1)
    sys.exit(0)


def export_selected_sessions(selected_list, output_dir, verbose=False):
    if not selected_list:
        return {"success": False, "count": 0, "total_size": 0,
                "errors": [("", "No sessions selected")],
                "output_dir": output_dir, "manifest": ""}
    by_project = defaultdict(list)
    for s in selected_list:
        by_project[s["project"]].append(s)
    export_base = output_dir
    try:
        os.makedirs(export_base, exist_ok=True)
        os.makedirs(os.path.join(export_base, "projects"), exist_ok=True)
    except OSError as e:
        return {"success": False, "count": 0, "total_size": 0,
                "errors": [("", f"Cannot create output dir: {e}")],
                "output_dir": export_base, "manifest": ""}
    errors = []
    exported_count = 0
    exported_bytes = 0
    project_meta = {}
    for proj_name, sessions in by_project.items():
        session_dicts = []
        for s in sessions:
            session_dicts.append({
                "uuid": s["uuid"],
                "jsonl_path": s["jsonl_path"],
                "has_subdir": s.get("has_subdir", False),
                "subdir_path": s.get("subdir_path", None),
            })
        for sd in session_dicts:
            uuid, size, ok, err = export_session(export_base, proj_name, sd, verbose=verbose)
            if ok:
                exported_count += 1
                exported_bytes += size
            else:
                errors.append((uuid, err))
        write_project_index(export_base, proj_name, session_dicts)
        project_meta[proj_name] = {
            "session_count": len(session_dicts),
            "total_size_bytes": sum(get_file_size(sd["jsonl_path"]) for sd in session_dicts),
            "sessions": [sd["uuid"] for sd in session_dicts],
        }
    all_versions = set()
    for s in selected_list:
        for v in collect_versions(s["jsonl_path"]):
            all_versions.add(v)
    meta = {
        "exported_at": datetime.now().isoformat(),
        "source_hostname": platform.node(),
        "source_platform": sys.platform,
        "claude_version_range": sorted(all_versions) if all_versions else list(KNOWN_VERSIONS),
        "projects": project_meta,
        "tool": "history-search/export.py (TUI)",
        "tool_version": TOOL_VERSION,
        "summary": {
            "total_projects": len(project_meta),
            "total_sessions": exported_count,
            "total_size_bytes": exported_bytes,
        },
    }
    meta_path = write_metadata(export_base, meta)
    return {
        "success": len(errors) == 0,
        "count": exported_count,
        "total_size": exported_bytes,
        "errors": errors,
        "output_dir": os.path.abspath(export_base),
        "manifest": meta_path,
    }


if __name__ == "__main__":
    main()
