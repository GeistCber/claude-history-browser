#!/usr/bin/env python3
"""
history_tui.py — 键盘驱动的三层历史浏览器 TUI
支持多项目、导出标记。

视觉：Claude 极简风格，无字符边框，中日韩字符宽度用 wcwidth 对齐。
"""
import json, os, sys, asyncio, shutil, re, glob
from datetime import datetime
from wcwidth import wcswidth  # 按东亚字符实际宽度排版

# 导入导出功能（用于 TUI 可视化导出）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export import export_selected_sessions

import prompt_toolkit.output.defaults as _ptk_out
_orig = _ptk_out.create_output
def _force_vt100(*a, **kw):
    from prompt_toolkit.output.vt100 import Vt100_Output
    return Vt100_Output.from_pty(sys.stdout, term=os.environ.get("TERM", "xterm-256color"))
_ptk_out.create_output = _force_vt100

from prompt_toolkit import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, FormattedTextControl, WindowAlign, HSplit
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.output import ColorDepth

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SKILL_DIR, ".history_cache")
DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
PROJECTS_DIR = os.environ.get("HISTORY_CACHE_PROJECTS_DIR", DEFAULT_PROJECTS_DIR)

# ── wcwidth 辅助 ──

def wcs(x):
    """返回字符串在终端中的显示宽度（东亚字符算 2）"""
    return wcswidth(x) if wcswidth(x) != -1 else len(x)

def wcpad(s, w):
    """右填充到显示宽度 w，考虑东亚双宽"""
    cur = wcs(s)
    need = w - cur
    return s + " " * max(0, need)

def wctrunc(s, w):
    """按显示宽度 w 截断，保留完整字符"""
    cur = wcs(s)
    if cur <= w:
        return s
    res = ""
    cw = 0
    for ch in s:
        chw = max(1, wcswidth(ch))
        if cw + chw > w - 1:
            res += "…"
            break
        res += ch
        cw += chw
    return res


# ── 样式 ──

STYLE = Style.from_dict({
    "status":        "bg:#222222 #ffffff",
    "selected":      "bg:#2a3a5a #ffffff bold",
    "selected.dim":  "bg:#2a3a5a #8899aa",
    "title":         "bold #ffffff",
    "sep":           "#444444",
    "dim":           "#666666",
    "hint":          "#555555",
    "info":          "#666666",
    "h1":            "bold #ffffff",
    "h2":            "bold #77aadd",
    "h3":            "bold #88bb88",
    "code":          "bg:#1a1a2a #88dd88",
    "bold":          "bold",
    "list":          "#88aadd",
    "sc.knob":       "#666666 bold",
    "sc.track":      "#333333",
    "qtext":         "#cccccc",
    "ts":            "#888888",
    "exported":      "bg:#1a2a1a #668866",
    "project":       "#aa8866",
    "checkbox.on":   "bold #88dd88",
    "checkbox.off":  "#555555",
    "result.ok":     "bold #88dd88",
    "result.err":    "#dd6666",
})


# ── 数据 ──

def load_sessions():
    """从缓存加载会话列表。支持多项目扁平 sessions.json"""
    p = os.path.join(CACHE_DIR, "sessions.json")
    if not os.path.exists(p):
        print("[history] Cache not ready. Run update_cache.py first.", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def load_questions(uuid):
    """加载某会话的问题列表（从缓存）"""
    # 先查分项目缓存，再查平铺式
    for proj_name in sorted(os.listdir(CACHE_DIR)):
        proj_cache = os.path.join(CACHE_DIR, proj_name)
        if not os.path.isdir(proj_cache):
            continue
        p = os.path.join(proj_cache, f"{uuid}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    # 向后兼容：平铺式
    p = os.path.join(CACHE_DIR, f"{uuid}.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

def find_session_file(uuid):
    """在所有项目目录中查找某个会话的 JSONL 路径。"""
    if not os.path.isdir(PROJECTS_DIR):
        return None
    for proj_name in sorted(os.listdir(PROJECTS_DIR)):
        proj_path = os.path.join(PROJECTS_DIR, proj_name)
        if not os.path.isdir(proj_path):
            continue
        fpath = os.path.join(proj_path, f"{uuid}.jsonl")
        if os.path.isfile(fpath):
            return fpath
    return None

def load_answer(uuid, qi):
    """惰性加载 AI 回答原文（从 JSONL）。"""
    fp = find_session_file(uuid)
    if fp is None:
        return None, "[Missing session file]", ""
    with open(fp, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    uc = 0; qs = -1; qt = ""; qts = ""
    for i, line in enumerate(lines):
        if not line.strip(): continue
        try: d = json.loads(line.strip())
        except: continue
        if d.get("type")!="user": continue
        c = d.get("message",{}).get("content","")
        t = c if isinstance(c,str) else next((x.get("text","") for x in c if isinstance(x,dict) and x.get("type")=="text"),"")
        if t and "tool_use_id" not in str(d):
            if uc==qi: qs=i; qt=t; qts=d.get("timestamp",""); break
            uc+=1
    if qs<0: return None,"[Not found]", ""
    ap = []
    for j in range(qs+1,len(lines)):
        try: d = json.loads(lines[j].strip())
        except: continue
        if d.get("type")=="user":
            c=d.get("message",{}).get("content","")
            t=c if isinstance(c,str) else next((x.get("text","") for x in c if isinstance(x,dict) and x.get("type")=="text"),"")
            if t and "tool_use_id" not in str(d): break
        if d.get("type")=="assistant":
            for x in d.get("message",{}).get("content",[]):
                if isinstance(x,dict) and x.get("type")=="text" and x.get("text"): ap.append(x["text"])
                if isinstance(x,dict) and x.get("type")=="tool_use":
                    inp=x.get("input",{}); fp2=inp.get("file_path",""); fc=inp.get("content","")
                    if fp2 and fc: ap.append(f"[Write] {fp2} ({len(fc)}字):\n{fc}")
    at = "\n".join(ap) if ap else "(empty)"
    try:
        ts = datetime.fromisoformat(qts.replace("Z","+00:00")).strftime("%Y-%m-%d %H:%M") if qts else ""
    except: ts = ""
    return qt, at, ts


def load_exported_uuids():
    """加载已导出会话的 UUID 集合（从最近的 claude-export 目录检测）。"""
    skill_dir = SKILL_DIR
    uuids = set()
    for name in sorted(os.listdir(skill_dir)):
        full = os.path.join(skill_dir, name)
        if not os.path.isdir(full):
            continue
        meta_path = os.path.join(full, "metadata.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            for proj_data in meta.get("projects", {}).values():
                for uuid in proj_data.get("sessions", []):
                    uuids.add(uuid)
        except Exception:
            continue
    return uuids


def get_session_project_path(uuid):
    """获取会话所属的项目名和 JSONL 路径。"""
    if not os.path.isdir(PROJECTS_DIR):
        return None, None
    for proj_name in sorted(os.listdir(PROJECTS_DIR)):
        proj_path = os.path.join(PROJECTS_DIR, proj_name)
        if not os.path.isdir(proj_path):
            continue
        fpath = os.path.join(proj_path, f"{uuid}.jsonl")
        if os.path.isfile(fpath):
            return proj_name, fpath
    return None, None


# ── 导出模式辅助 ────────────────────────────────────────────

def _build_export_item(session_data):
    """为 TUI 导出构建 selected_list item。"""
    uuid = session_data["uuid"]
    proj, jsonl_path = get_session_project_path(uuid)
    if not proj:
        return None
    subdir_path = os.path.join(os.path.dirname(jsonl_path), uuid)
    has_subdir = os.path.isdir(subdir_path)
    return {
        "project": proj,
        "uuid": uuid,
        "jsonl_path": jsonl_path,
        "has_subdir": has_subdir,
        "subdir_path": subdir_path if has_subdir else None,
    }


# ── 行构建 ──

def short_project_name(project):
    """从项目目录名提取简短标识（最后一段路径名）"""
    # C--Users-Laptop -> "Laptop"
    parts = project.replace("--", "/").replace("-", "/").split("/")
    return parts[-1] if parts else project[:6]


def row_sessions(ss, total, upd, exported_uuids):
    """
    层1：极简风格，带项目标签和导出标记。
    标题行 → 分隔线 → 每会话一行 → 分隔线 → 底栏
    """
    r = [("title", "  SESSIONS"),
         ("sep",   f"  {'─'*74}")]
    for i,s in enumerate(ss):
        try: d = datetime.fromisoformat(s["timestamp"].replace("Z","+00:00")).strftime("%m-%d") if s["timestamp"]!="0"*20 else "??-??"
        except: d = "??-??"
        lb = (s.get("title") or s.get("first_msg","") or "(无)")[:40]
        uuid8 = s['uuid'][:8]; cnt = s['count']
        proj = s.get("project", "")
        proj_short = short_project_name(proj) if proj else ""
        exported = s['uuid'] in exported_uuids

        # 组装行
        parts = []
        # 导出标记
        if exported:
            parts.append("[E]")
        else:
            parts.append("   ")
        # 项目标签
        if proj_short:
            parts.append(f"[{proj_short}]")
        else:
            parts.append("      ")
        # 编号 + 日期 + 标题
        parts.append(f"  #{i+1:<4} {d}  {lb}")

        line = "".join(parts)
        meta = f"{cnt}条  {uuid8}"
        r.append(("session", line, meta, exported))
    r.append(("sep",   f"  {'─'*74}"))
    r.append(("dim",   f"  共 {total} 个会话 · 更新 {upd}"))
    r.append(("hint",  "  [E]=已导出  ↑↓  PgUp/PgDn  Enter 选择  ESC/^C 退出"))
    return r  # list of (style|None, text, meta?, exported?)

def row_questions(qs, uuid8, ds, title):
    """层2：极简风格"""
    r = [("title", f"  QUESTIONS — {uuid8} ({ds})"),
         ("dim",   f"  {title}"),
         ("sep",   f"  {'─'*74}")]
    for i,q in enumerate(qs):
        p = wctrunc(q.replace("\n"," ").replace("\r",""), 66)
        r.append((None, f"  #{i+1:<5} {p}"))
    r.append(("sep",   f"  {'─'*74}"))
    r.append(("dim",   f"  共 {len(qs)} 条"))
    r.append(("hint",  "  ↑↓  PgUp/PgDn  Enter 查看  ESC 返回"))
    return r

def row_answer(text, qt, ts):
    """层3：Claude 干净风格。横幅移除，MD 标记真实渲染"""
    r = []
    if ts:
        r.append(("ts", f"  >>> {ts}"))
    # 用户提问
    r.append(("qtext", f"  {qt.replace(chr(10), chr(10)+'  ')}"))
    r.append(("sep",   f"  {'─'*74}"))
    # AI 回答正文——Markdown 渲染（去掉记号，保留原文）
    in_code = False
    for line in text.split("\n"):
        if not line:
            r.append((None, ""))
            continue
        # 代码块开关
        if line.startswith("```"):
            in_code = not in_code
            if in_code:
                r.append(("code", "  ```"))
            else:
                r.append(("code", "  ```"))
            continue
        if in_code:
            # 代码块内保持原文
            r.append(("code", f"  {line}"))
            continue
        # Markdown 行
        stripped = line.lstrip()
        indent = line[:len(line)-len(stripped)]
        # 标题
        hm = re.match(r'^(#{1,3})\s+(.*)', stripped)
        if hm:
            level = len(hm.group(1))
            st = "h1" if level == 1 else "h2" if level == 2 else "h3"
            r.append((st, f"{indent}{hm.group(2)}"))
            continue
        # 粗体行
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            r.append(("bold", f"{indent}{stripped[2:-2]}"))
            continue
        # 列表
        bm = re.match(r'^(\s*)[-*]\s+(.*)', stripped)
        if bm:
            indent2 = indent + bm.group(1)
            r.append(("list", f"{indent2}• {bm.group(2)}"))
            continue
        # 普通文本（行内做一个简易粗体替换：去掉 ** 但加粗）
        plain = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
        r.append((None, f"{indent}{plain}"))
    r.append(("sep",   f"  {'─'*74}"))
    r.append(("hint",  f"  ↑↓ 滚动  ESC 返回  ·  {len(text)} 字"))
    return r


def row_sessions_export(ss, selected_uuids, total_sessions):
    """
    导出模式下的层1行（带复选框 [x]/[ ]）。
    不改变原有 row_sessions 函数。
    """
    r = [("title", "  EXPORT — select sessions"),
         ("sep",   f"  {'─'*74}")]
    for i, s in enumerate(ss):
        try:
            d = datetime.fromisoformat(s["timestamp"].replace("Z","+00:00")).strftime("%m-%d") if s["timestamp"]!="0"*20 else "??-??"
        except:
            d = "??-??"
        lb = (s.get("title") or s.get("first_msg","") or "(无)")[:40]
        uuid8 = s['uuid'][:8]; cnt = s['count']
        proj = s.get("project", "")
        proj_short = short_project_name(proj) if proj else ""
        checked = s['uuid'] in selected_uuids

        # 复选框
        cb = "[x]" if checked else "[ ]"
        cb_style = "checkbox.on" if checked else "checkbox.off"
        proj_tag = f"[{proj_short}]" if proj_short else "      "
        line = f"  {proj_tag}  #{i+1:<4} {d}  {lb}"
        meta = f"{cnt}条  {uuid8}"

        if checked:
            r.append((cb_style, line, meta))
        else:
            r.append((cb_style, line, meta))

    n_sel = len(selected_uuids)
    r.append(("sep",   f"  {'─'*74}"))
    r.append(("dim",   f"  已选 {n_sel}/{total_sessions}  ·  Space 选中/取消  A 项目全选  Enter 导出  ESC 取消"))
    return r


def row_export_result(result, output_dir):
    """层4：导出完成后显示结果摘要"""
    r = [("title", "  EXPORT RESULT"),
         ("sep",   f"  {'─'*74}")]
    if result["success"]:
        r.append(("result.ok", f"  Export complete"))
    else:
        r.append(("result.err", f"  Export finished with errors"))
    r.append((None, ""))
    r.append(("dim",   f"  Output: {output_dir}"))
    r.append(("dim",   f"  Sessions exported: {result['count']}"))
    r.append(("dim",   f"  Total size: {result['total_size']:,} bytes ({result['total_size']/1024/1024:.1f} MB)"))
    if result["manifest"]:
        r.append(("dim",   f"  Manifest: {result['manifest']}"))
    r.append((None, ""))
    if result["errors"]:
        r.append(("result.err", f"  Errors ({len(result['errors'])}):"))
        for uuid, err in result["errors"]:
            r.append(("result.err", f"    - {uuid}: {err}"))
        r.append((None, ""))
    r.append(("sep",   f"  {'─'*74}"))
    r.append(("hint",  "  ESC 返回会话列表"))
    return r


# ── 辅助 ──

def scrollbar_knob(total, view, pos):
    if total <= view: return None, 0
    kh = max(1, view * view // total)
    mp = total - view
    ky = (view - kh) * pos // mp if mp > 0 else 0
    return ky, kh


# ── 主程序 ──

def main():
    data = load_sessions()
    sessions = data["sessions"]
    total_sessions = data["total"]
    updated_at = data.get("updated_at","")[:10]
    exported_uuids = load_exported_uuids()

    # ── 状态 ──
    level = 1
    sel = 0
    scroll_y = 0
    nav_stack = []

    # 导出模式状态（不影响原有状态）
    export_mode = False
    selected_uuids = set()
    export_result = None
    export_output_dir = ""

    cur_uuid = ""
    cur_title = ""
    cur_ts = ""
    cur_questions = []
    total_questions = 0
    show_text = ""
    show_q = ""
    show_ts = ""
    info_msg = ""

    # rows: list of (style|None, text[, meta, exported])
    rows = []
    sel_abs = 0

    def fix_sel_abs():
        nonlocal sel_abs
        if level == 1:
            sel_abs = 2 + sel
        elif level == 2:
            sel_abs = 3 + sel
        else:
            sel_abs = -1

    def rb1():
        nonlocal rows, sel_abs
        rows = row_sessions(sessions, total_sessions, updated_at, exported_uuids)
        fix_sel_abs()

    def rb2():
        nonlocal rows, sel_abs
        rows = row_questions(cur_questions, cur_uuid[:8] if cur_uuid else "", cur_ts[:10], cur_title)
        fix_sel_abs()

    def rb3():
        nonlocal rows, sel_abs
        rows = row_answer(show_text, show_q, show_ts)
        sel_abs = -1

    def rb_export():
        nonlocal rows, sel_abs
        rows = row_sessions_export(sessions, selected_uuids, total_sessions)
        sel_abs = 2 + sel

    def rb_result():
        nonlocal rows, sel_abs
        rows = row_export_result(export_result, export_output_dir)
        sel_abs = -1

    rb1()

    # ── 按键 ──
    kb = KeyBindings()

    @Condition
    def is_l12(): return level in (1,2) and not export_mode
    @Condition
    def is_l1(): return level == 1 and not export_mode and not export_result
    @Condition
    def is_l2(): return level == 2
    @Condition
    def is_l3(): return level == 3
    @Condition
    def is_export_mode(): return export_mode and level == 1
    @Condition
    def is_result(): return export_result is not None and level == 4

    def mx():
        return total_sessions-1 if level==1 else total_questions-1 if level==2 else 0

    def clamp():
        nonlocal scroll_y, sel_abs
        try: _,th = shutil.get_terminal_size()
        except: th=24
        av = max(5, th-1)
        if sel_abs < 0: return
        if sel_abs < scroll_y:
            scroll_y = max(0, sel_abs - 1)
        elif sel_abs >= scroll_y + av - 1:
            scroll_y = sel_abs - av + 2

    # ── 导出模式按键 ──
    @kb.add("x", filter=Condition(lambda: level == 1 and not export_mode and not export_result))
    def _(e):
        nonlocal level, export_mode, selected_uuids, scroll_y, sel, info_msg
        export_mode = True
        sel = 0
        scroll_y = 0
        info_msg = "Export mode - Space to select"
        rb_export()

    @kb.add("space", filter=is_export_mode)
    def _(e):
        nonlocal selected_uuids, info_msg
        if sel < len(sessions):
            uuid = sessions[sel]["uuid"]
            if uuid in selected_uuids:
                selected_uuids.discard(uuid)
            else:
                selected_uuids.add(uuid)
            info_msg = f"Selected {len(selected_uuids)} session(s)"
            rb_export()

    @kb.add("up", filter=is_export_mode)
    def _(e):
        nonlocal sel
        if sel > 0:
            sel -= 1
            fix_sel_abs()
            clamp()

    @kb.add("down", filter=is_export_mode)
    def _(e):
        nonlocal sel
        if sel < total_sessions - 1:
            sel += 1
            fix_sel_abs()
            clamp()

    @kb.add("pageup", filter=is_export_mode)
    def _(e):
        nonlocal sel
        sel = max(0, sel - 20)
        fix_sel_abs()
        clamp()

    @kb.add("pagedown", filter=is_export_mode)
    def _(e):
        nonlocal sel
        sel = min(total_sessions - 1, sel + 20)
        fix_sel_abs()
        clamp()

    @kb.add("escape", filter=is_export_mode)
    def _(e):
        nonlocal export_mode, selected_uuids, info_msg, scroll_y, sel
        export_mode = False
        selected_uuids = set()
        info_msg = ""
        sel = 0
        scroll_y = 0
        rb1()

    @kb.add("escape", filter=is_result)
    def _(e):
        nonlocal export_result, level, info_msg
        export_result = None
        level = 1
        info_msg = ""
        sel = 0
        scroll_y = 0
        rb1()

    @kb.add("enter", filter=is_export_mode)
    async def _(e):
        nonlocal export_result, export_output_dir, level, info_msg, export_mode, selected_uuids
        if not selected_uuids:
            info_msg = "No sessions selected"
            return
        export_items = []
        for s in sessions:
            if s["uuid"] in selected_uuids:
                item = _build_export_item(s)
                if item:
                    export_items.append(item)
        if not export_items:
            info_msg = "Cannot resolve session files"
            return

        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y%m%d-%H%M%S")
        export_output_dir = os.path.join(SKILL_DIR, f"claude-export-{ts}")
        info_msg = f"Exporting {len(export_items)} session(s)..."
        e.app.invalidate()
        await asyncio.sleep(0.05)

        result = export_selected_sessions(export_items, export_output_dir, verbose=False)
        export_result = result
        level = 4
        export_mode = False
        selected_uuids = set()
        info_msg = ""
        rb_result()
        e.app.invalidate()

    @kb.add("a", filter=is_export_mode)
    def _(e):
        nonlocal selected_uuids, info_msg
        if sel < len(sessions):
            cur_proj = sessions[sel].get("project", "")
            # Check if all sessions in this project are already selected
            proj_uuids = {s["uuid"] for s in sessions if s.get("project", "") == cur_proj}
            all_selected = proj_uuids.issubset(selected_uuids)
            if all_selected:
                # Deselect all in this project
                selected_uuids -= proj_uuids
            else:
                # Select all in this project
                selected_uuids |= proj_uuids
            info_msg = f"Selected {len(selected_uuids)} session(s)"
            rb_export()

    # ── 原有按键 ──
    @kb.add("up", filter=is_l12)
    def _(e):
        nonlocal sel
        if sel>0: sel-=1; fix_sel_abs(); clamp()

    @kb.add("down", filter=is_l12)
    def _(e):
        nonlocal sel
        if sel<mx(): sel+=1; fix_sel_abs(); clamp()

    @kb.add("up", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = max(0, scroll_y-1)

    @kb.add("down", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = min(max(0,len(rows)-3), scroll_y+1)

    @kb.add("pageup", filter=is_l12)
    def _(e):
        nonlocal sel
        sel=max(0, sel-20); fix_sel_abs(); clamp()

    @kb.add("pagedown", filter=is_l12)
    def _(e):
        nonlocal sel
        sel=min(mx(), sel+20); fix_sel_abs(); clamp()

    @kb.add("pageup", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = max(0, scroll_y-20)

    @kb.add("pagedown", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = min(max(0,len(rows)-3), scroll_y+20)

    @kb.add("enter", filter=is_l1)
    def _(e):
        nonlocal level, sel, scroll_y, cur_uuid, cur_title, cur_ts, cur_questions, total_questions, info_msg
        nav_stack.append((1, sel, scroll_y))
        s=sessions[sel]
        qd=load_questions(s["uuid"])
        if qd is None: return
        cur_uuid=s["uuid"]; cur_title=s.get("title","")
        cur_ts=(s.get("timestamp","") or "")[:10]
        cur_questions=qd.get("questions",[]); total_questions=len(cur_questions)
        sel=0; scroll_y=0; level=2; rb2()
        info_msg=f"会话 #{nav_stack[-1][1]+1} · {total_questions} 条"

    @kb.add("enter", filter=is_l2)
    def _(e):
        nonlocal level, sel, scroll_y, show_text, show_q, show_ts, info_msg
        if total_questions==0: return
        nav_stack.append((2, sel, scroll_y))
        qt, at, ts = load_answer(cur_uuid, sel)
        show_q = qt; show_ts = ts
        hd = f">>> {ts}\n\n" if ts else ""
        show_text = f"{hd}{qt}\n\n{'─'*68}\n\n{at}"
        level=3; scroll_y=0; rb3()
        info_msg=f"#{sel+1} · {len(show_text)}字 · ESC 返回"

    @kb.add("escape")
    def _(e):
        nonlocal level, sel, scroll_y, info_msg
        if level==3:
            level=2
            if nav_stack: _,s2,ss2=nav_stack.pop(); sel,scroll_y=s2,ss2; rb2()
            info_msg=""
        elif level==2:
            level=1
            if nav_stack: _,s1,ss1=nav_stack.pop(); sel,scroll_y=s1,ss1; rb1()
            info_msg=""
        else: e.app.exit()

    @kb.add("c-c")
    def _(e): e.app.exit()

    # ── 渲染 ──
    term_h = [24]

    def render_body():
        nonlocal scroll_y
        try: _,th = shutil.get_terminal_size(); term_h[0]=th
        except: th=term_h[0]
        av = max(5, th-1)
        total = len(rows)
        scroll_y = min(scroll_y, max(0, total-av))

        ky, kh = scrollbar_knob(total, av, scroll_y) if total>av else (None, 0)
        end = min(scroll_y+av, total)
        frags = []

        for ab in range(scroll_y, end):
            if ab >= len(rows): break
            row = rows[ab]

            # 解析行：兼容 3/4 元组
            if isinstance(row, (list, tuple)):
                if len(row) == 4:
                    st, tx, meta, exported = row
                elif len(row) == 3:
                    st, tx, meta = row
                    exported = False
                else:
                    st, tx = row[:2]
                    meta = None
                    exported = False
            else:
                st, tx = None, str(row)
                meta = None
                exported = False

            # 滚动条
            rel = ab - scroll_y
            if ky is not None:
                ch = "#" if ky <= rel < ky + kh else "│"
                bar = ch
            else:
                bar = ""

            is_sel = (sel_abs is not None and ab == sel_abs)

            # 构建行文本
            if meta is not None:
                avail_w = 72 - (1 if bar else 0)
                line = tx
                meta_display = f"  {meta}"
                meta_vis_w = wcs(meta_display)
                line_vis_w = wcs(line)
                pad = max(1, avail_w - line_vis_w - meta_vis_w)
                line = line + " " * pad + meta_display
                line = wctrunc(line, avail_w) + bar
            else:
                line = tx + bar

            # 样式选择
            style_class = ""
            if is_sel:
                style_class = "class:selected"
            elif exported:
                style_class = "class:exported"
            elif st:
                style_class = f"class:{st}"
            # else: default style (empty string)

            frags.append((style_class, f"{line}\n"))

        # 补空白 + 滚动条
        for rel in range(end-scroll_y, av):
            if ky is not None:
                ch = "#" if ky <= rel < ky + kh else "│"
                st2 = "sc.knob" if ky <= rel < ky + kh else "sc.track"
                frags.append((st2, f"  {ch}\n"))
            else:
                frags.append(("", "\n"))

        return FormattedText(frags)

    body = Window(content=FormattedTextControl(render_body), wrap_lines=True, always_hide_cursor=True)

    def get_foot_text():
        if export_mode:
            return [("class:status", f"  EXPORT MODE - {len(selected_uuids)} selected  ·  Space toggle  A project-all  Enter execute  ESC cancel")]
        if export_result and level == 4:
            ok = export_result["count"]
            err = len(export_result["errors"])
            status = "OK" if export_result["success"] else "WARN"
            return [("class:status", f"  Export {status} - {ok} sessions, {err} errors  ·  ESC back")]
        if info_msg:
            return [("class:status",f"  {info_msg}")]
        return []

    foot = Window(height=1, content=FormattedTextControl(get_foot_text), align=WindowAlign.LEFT)

    layout = Layout(container=HSplit([body, foot]))

    app = Application(layout=layout, key_bindings=kb, style=STYLE, full_screen=True,
                      color_depth=ColorDepth.DEPTH_8_BIT, mouse_support=True)

    async def run():
        async def rf():
            while True: app.invalidate(); await asyncio.sleep(0.05)
        t = asyncio.create_task(rf())
        try: await app.run_async()
        finally: t.cancel()

    asyncio.run(run())

if __name__=="__main__":
    main()
