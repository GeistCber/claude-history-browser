#!/usr/bin/env python3
"""
history_tui.py — 键盘驱动的三层历史浏览器 TUI

浏览 Claude Code 历史会话。方向键导航，Enter 选中，ESC 逐级返回。
中日韩字符宽度用 wcwidth 正确处理，选中行通栏高亮，回答文本 Markdown 渲染。

视觉：Claude 极简风格，无字符边框。

用法：
  python history_tui.py [--jsonl-dir PATH]

环境变量：
  CLAUDE_JSONL_DIR   JSONL 会话文件目录（默认 ~/.claude/projects/C--Users-Laptop）
  HISTORY_CACHE_DIR  缓存目录（默认 ./history_cache）
"""
import json, os, sys, asyncio, shutil, re, argparse
from datetime import datetime
from wcwidth import wcswidth

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

# ── 路径配置 ──────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # 项目根目录
HOME_DIR = os.path.expanduser("~")

DEFAULT_CACHE_DIR = os.path.join(PROJECT_DIR, ".history_cache")

# wcwidth 辅助
def wcs(x):
    return wcswidth(x) if wcswidth(x) != -1 else len(x)

def wcpad(s, w):
    cur = wcs(s)
    return s + " " * max(0, w - cur)

def wctrunc(s, w):
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

# ── 样式 ──────────────────────────────────────────────────────
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
})


# ═══════════════════════════════════════════════════════════════
#  数据层
# ═══════════════════════════════════════════════════════════════

def load_sessions(cache_dir):
    p = os.path.join(cache_dir, "sessions.json")
    if not os.path.exists(p):
        print(f"[history] 缓存未就绪: {p}")
        print("[history] 请先运行: python scripts/update_cache.py")
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def load_questions(uuid, cache_dir):
    p = os.path.join(cache_dir, f"{uuid}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def load_answer(uuid, qi, jsonl_dir):
    fp = os.path.join(jsonl_dir, f"{uuid}.jsonl")
    if not os.path.exists(fp):
        return None, "[文件不存在]", ""
    with open(fp, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    uc = 0; qs = -1; qt = ""; qts = ""
    for i, line in enumerate(lines):
        if not line.strip(): continue
        try: d = json.loads(line.strip())
        except: continue
        if d.get("type") != "user": continue
        c = d.get("message", {}).get("content", "")
        t = c if isinstance(c, str) else next((x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"), "")
        if t and "tool_use_id" not in str(d):
            if uc == qi:
                qs = i; qt = t; qts = d.get("timestamp", ""); break
            uc += 1
    if qs < 0:
        return None, "[未找到该提问]", ""
    ap = []
    for j in range(qs + 1, len(lines)):
        try: d = json.loads(lines[j].strip())
        except: continue
        if d.get("type") == "user":
            c = d.get("message", {}).get("content", "")
            t = c if isinstance(c, str) else next((x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"), "")
            if t and "tool_use_id" not in str(d):
                break
        if d.get("type") == "assistant":
            for x in d.get("message", {}).get("content", []):
                if isinstance(x, dict) and x.get("type") == "text" and x.get("text"):
                    ap.append(x["text"])
                if isinstance(x, dict) and x.get("type") == "tool_use":
                    inp = x.get("input", {})
                    fp2 = inp.get("file_path", "")
                    fc = inp.get("content", "")
                    if fp2 and fc:
                        ap.append(f"[Write] {fp2} ({len(fc)} 字):\n{fc}")
    at = "\n".join(ap) if ap else "(空)"
    try:
        ts = datetime.fromisoformat(qts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M") if qts else ""
    except:
        ts = ""
    return qt, at, ts


# ═══════════════════════════════════════════════════════════════
#  行构建器
# ═══════════════════════════════════════════════════════════════

def row_sessions(ss, total, upd):
    r = [("title", "  SESSIONS"),
         ("sep",   f"  {'─' * 74}")]
    for i, s in enumerate(ss):
        try:
            d = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")).strftime("%m-%d") if s["timestamp"] != "0" * 20 else "??-??"
        except:
            d = "??-??"
        lb = (s.get("title") or s.get("first_msg", "") or "(无)")[:40]
        uuid8 = s["uuid"][:8]
        cnt = s["count"]
        line = f"  #{i+1:<4} {d}  {lb}"
        meta = f"{cnt}条  {uuid8}"
        r.append(("session", line, meta))
    r.append(("sep",   f"  {'─' * 74}"))
    r.append(("dim",   f"  共 {total} 个会话 · 更新 {upd}"))
    r.append(("hint",  "  ↑↓  PgUp/PgDn  Enter 选择  ESC/^C 退出"))
    return r

def row_questions(qs, uuid8, ds, title):
    r = [("title", f"  QUESTIONS — {uuid8} ({ds})"),
         ("dim",   f"  {title}"),
         ("sep",   f"  {'─' * 74}")]
    for i, q in enumerate(qs):
        p = wctrunc(q.replace("\n", " ").replace("\r", ""), 66)
        r.append((None, f"  #{i+1:<5} {p}"))
    r.append(("sep",   f"  {'─' * 74}"))
    r.append(("dim",   f"  共 {len(qs)} 条"))
    r.append(("hint",  "  ↑↓  PgUp/PgDn  Enter 查看  ESC 返回"))
    return r

def row_answer(text, qt, ts_str):
    r = []
    if ts_str:
        r.append(("ts", f"  >>> {ts_str}"))
    r.append(("qtext", f"  {qt.replace(chr(10), chr(10) + '  ')}"))
    r.append(("sep",   f"  {'─' * 74}"))
    in_code = False
    for line in text.split("\n"):
        if not line:
            r.append((None, ""))
            continue
        if line.startswith("```"):
            in_code = not in_code
            r.append(("code", "  ```" if in_code else "  ```"))
            continue
        if in_code:
            r.append(("code", f"  {line}"))
            continue
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        hm = re.match(r'^(#{1,3})\s+(.*)', stripped)
        if hm:
            level = len(hm.group(1))
            st = "h1" if level == 1 else "h2" if level == 2 else "h3"
            r.append((st, f"{indent}{hm.group(2)}"))
            continue
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            r.append(("bold", f"{indent}{stripped[2:-2]}"))
            continue
        bm = re.match(r'^(\s*)[-*]\s+(.*)', stripped)
        if bm:
            indent2 = indent + bm.group(1)
            r.append(("list", f"{indent2}• {bm.group(2)}"))
            continue
        plain = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
        r.append((None, f"{indent}{plain}"))
    r.append(("sep",   f"  {'─' * 74}"))
    r.append(("hint",  f"  ↑↓ 滚动  ESC 返回  ·  {len(text)} 字"))
    return r


# ── 辅助 ──
def scrollbar_knob(total, view, pos):
    if total <= view: return None, 0
    kh = max(1, view * view // total)
    mp = total - view
    ky = (view - kh) * pos // mp if mp > 0 else 0
    return ky, kh


# ═══════════════════════════════════════════════════════════════
#  主程序
# ═══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Claude Code 历史浏览器 TUI")
    ap.add_argument("--jsonl-dir", default=None, help="JSONL 会话文件目录")
    args = ap.parse_args()

    jsonl_dir = args.jsonl_dir or os.environ.get("CLAUDE_JSONL_DIR")
    if not jsonl_dir:
        print("[history] 需要指定 JSONL 目录：")
        print("  python scripts/history_tui.py --jsonl-dir PATH")
        print("  或设置环境变量: export CLAUDE_JSONL_DIR=PATH")
        sys.exit(1)
    cache_dir = os.environ.get("HISTORY_CACHE_DIR") or os.path.join(PROJECT_DIR, ".history_cache")

    if not os.path.exists(jsonl_dir):
        print(f"[history] JSONL 目录不存在: {jsonl_dir}")
        print("[history] 设置环境变量 CLAUDE_JSONL_DIR 或传入 --jsonl-dir")
        sys.exit(1)

    data = load_sessions(cache_dir)
    sessions = data["sessions"]
    total_sessions = data["total"]
    updated_at = data.get("updated_at", "")[:10]

    # 状态
    level = 1
    sel = 0
    scroll_y = 0
    nav_stack = []

    cur_uuid = ""
    cur_title = ""
    cur_ts = ""
    cur_questions = []
    total_questions = 0
    show_text = ""
    show_q = ""
    show_ts = ""
    info_msg = ""
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
        rows = row_sessions(sessions, total_sessions, updated_at)
        fix_sel_abs()

    def rb2():
        nonlocal rows, sel_abs
        rows = row_questions(cur_questions, cur_uuid[:8] if cur_uuid else "", cur_ts[:10], cur_title)
        fix_sel_abs()

    def rb3():
        nonlocal rows, sel_abs
        rows = row_answer(show_text, show_q, show_ts)
        sel_abs = -1

    rb1()

    # ── 按键 ──
    kb = KeyBindings()

    @Condition
    def is_l12(): return level in (1, 2)
    @Condition
    def is_l1(): return level == 1
    @Condition
    def is_l2(): return level == 2
    @Condition
    def is_l3(): return level == 3

    def mx():
        return total_sessions - 1 if level == 1 else total_questions - 1 if level == 2 else 0

    def clamp():
        nonlocal scroll_y, sel_abs
        try: _, th = shutil.get_terminal_size()
        except: th = 24
        av = max(5, th - 1)
        if sel_abs < 0: return
        if sel_abs < scroll_y:
            scroll_y = max(0, sel_abs - 1)
        elif sel_abs >= scroll_y + av - 1:
            scroll_y = sel_abs - av + 2

    dirs = dict(up=-1, down=1)

    @kb.add("up", filter=is_l12)
    def _(e):
        nonlocal sel
        if sel > 0: sel -= 1; fix_sel_abs(); clamp()

    @kb.add("down", filter=is_l12)
    def _(e):
        nonlocal sel
        if sel < mx(): sel += 1; fix_sel_abs(); clamp()

    @kb.add("up", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = max(0, scroll_y - 1)

    @kb.add("down", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = min(max(0, len(rows) - 3), scroll_y + 1)

    @kb.add("pageup", filter=is_l12)
    def _(e):
        nonlocal sel
        sel = max(0, sel - 20); fix_sel_abs(); clamp()

    @kb.add("pagedown", filter=is_l12)
    def _(e):
        nonlocal sel
        sel = min(mx(), sel + 20); fix_sel_abs(); clamp()

    @kb.add("pageup", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = max(0, scroll_y - 20)

    @kb.add("pagedown", filter=is_l3)
    def _(e):
        nonlocal scroll_y
        scroll_y = min(max(0, len(rows) - 3), scroll_y + 20)

    @kb.add("enter", filter=is_l1)
    def _(e):
        nonlocal level, sel, scroll_y, cur_uuid, cur_title, cur_ts, cur_questions, total_questions, info_msg
        nav_stack.append((1, sel, scroll_y))
        s = sessions[sel]
        qd = load_questions(s["uuid"], cache_dir)
        if qd is None: return
        cur_uuid = s["uuid"]
        cur_title = s.get("title", "")
        cur_ts = (s.get("timestamp", "") or "")[:10]
        cur_questions = qd.get("questions", [])
        total_questions = len(cur_questions)
        sel = 0; scroll_y = 0; level = 2; rb2()
        info_msg = f"会话 #{nav_stack[-1][1] + 1} · {total_questions} 条"

    @kb.add("enter", filter=is_l2)
    def _(e):
        nonlocal level, sel, scroll_y, show_text, show_q, show_ts, info_msg
        if total_questions == 0: return
        nav_stack.append((2, sel, scroll_y))
        qt, at, ts = load_answer(cur_uuid, sel, jsonl_dir)
        show_q = qt
        show_ts = ts
        hd = f">>> {ts}\n\n" if ts else ""
        show_text = f"{hd}{qt}\n\n{'─' * 68}\n\n{at}"
        level = 3; scroll_y = 0; rb3()
        info_msg = f"#{sel + 1} · {len(show_text)} 字 · ESC 返回"

    @kb.add("escape")
    def _(e):
        nonlocal level, sel, scroll_y, info_msg
        if level == 3:
            level = 2
            if nav_stack: _, s2, ss2 = nav_stack.pop(); sel, scroll_y = s2, ss2; rb2()
            info_msg = ""
        elif level == 2:
            level = 1
            if nav_stack: _, s1, ss1 = nav_stack.pop(); sel, scroll_y = s1, ss1; rb1()
            info_msg = ""
        else:
            e.app.exit()

    @kb.add("c-c")
    def _(e): e.app.exit()

    # ── 渲染 ──
    term_h = [24]

    def render_body():
        nonlocal scroll_y
        try: _, th = shutil.get_terminal_size(); term_h[0] = th
        except: th = term_h[0]
        av = max(5, th - 1)
        total = len(rows)
        scroll_y = min(scroll_y, max(0, total - av))
        ky, kh = scrollbar_knob(total, av, scroll_y) if total > av else (None, 0)
        end = min(scroll_y + av, total)
        frags = []

        for ab in range(scroll_y, end):
            if ab >= len(rows): break
            row = rows[ab]
            is_session = isinstance(row, (list, tuple)) and len(row) == 3
            if is_session:
                st, tx, meta = row
            else:
                st, tx = row if isinstance(row, (list, tuple)) else (None, str(row))
                meta = None
            rel = ab - scroll_y
            bar = ("#" if ky is not None and ky <= rel < ky + kh else "│") if ky is not None else ""
            is_sel = (sel_abs is not None and ab == sel_abs)

            if is_session:
                avail_w = 72 - (1 if bar else 0)
                line = tx
                if meta:
                    md = f"  {meta}"
                    pad = max(1, avail_w - wcs(line) - wcs(md))
                    line = line + " " * pad + md
                line = wctrunc(line, avail_w) + bar
            else:
                line = tx + bar

            if is_sel:
                frags.append(("class:selected", f"{line}\n"))
            elif st:
                frags.append((f"class:{st}", f"{line}\n"))
            else:
                frags.append(("", f"{line}\n"))

        for rel in range(end - scroll_y, av):
            if ky is not None:
                ch = "#" if ky <= rel < ky + kh else "│"
                st2 = "sc.knob" if ky <= rel < ky + kh else "sc.track"
                frags.append((st2, f"  {ch}\n"))
            else:
                frags.append(("", "\n"))

        return FormattedText(frags)

    body = Window(content=FormattedTextControl(render_body), wrap_lines=True, always_hide_cursor=True)
    foot = Window(height=1, content=FormattedTextControl(lambda: [("class:status", f"  {info_msg}")] if info_msg else []), align=WindowAlign.LEFT)
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

if __name__ == "__main__":
    main()
