#!/usr/bin/env python3
"""
history_tui.py — 键盘驱动的三层历史浏览器 TUI

视觉：Claude 极简风格，无字符边框，中日韩字符宽度用 wcwidth 对齐。
"""
import json, os, sys, asyncio, shutil, re
from datetime import datetime
from wcwidth import wcswidth  # 按东亚字符实际宽度排版

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
JSONL_DIR = r"C:\Users\Laptop\.claude\projects\C--Users-Laptop"

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
})


# ── 数据 ──

def load_sessions():
    p = os.path.join(CACHE_DIR, "sessions.json")
    if not os.path.exists(p):
        print("[history] 缓存未就绪"); sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def load_questions(uuid):
    p = os.path.join(CACHE_DIR, f"{uuid}.json")
    if not os.path.exists(p): return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def load_answer(uuid, qi):
    fp = os.path.join(JSONL_DIR, f"{uuid}.jsonl")
    if not os.path.exists(fp): return None, "[缺失]", ""
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
    if qs<0: return None,"[未找到]", ""
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
    at = "\n".join(ap) if ap else "(空)"
    try:
        ts = datetime.fromisoformat(qts.replace("Z","+00:00")).strftime("%Y-%m-%d %H:%M") if qts else ""
    except: ts = ""
    return qt, at, ts


# ── 行构建 ──

def row_sessions(ss, total, upd):
    """
    层1：极简风格。
    标题行 → 分隔线 → 每会话一行 → 分隔线 → 底栏
    """
    r = [("title", "  SESSIONS"),
         ("sep",   f"  {'─'*74}")]
    for i,s in enumerate(ss):
        try: d = datetime.fromisoformat(s["timestamp"].replace("Z","+00:00")).strftime("%m-%d") if s["timestamp"]!="0"*20 else "??-??"
        except: d = "??-??"
        lb = (s.get("title") or s.get("first_msg","") or "(无)")[:40]
        uuid8 = s['uuid'][:8]; cnt = s['count']
        # 编号 + 日期(灰) + 标题，uuid和条数 dim 灰行尾
        line = f"  #{i+1:<4} {d}  {lb}"
        meta = f"{cnt}条  {uuid8}"
        r.append(("session", line, meta))
    r.append(("sep",   f"  {'─'*74}"))
    r.append(("dim",   f"  共 {total} 个会话 · 更新 {upd}"))
    r.append(("hint",  "  ↑↓  PgUp/PgDn  Enter 选择  ESC/^C 退出"))
    return r  # list of (style|None, text) OR (style, text, meta_dim)

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

    # ── 状态 ──
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

    # rows: list of (style|None, text)  OR  (style, text, meta)  for session rows
    rows = []
    # sel_abs: 选中行的绝对行号在 rows 中的索引
    sel_abs = 0

    def fix_sel_abs():
        nonlocal sel_abs
        if level == 1:
            # 2 行头 + sel*1 行内容
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
    def is_l12(): return level in (1,2)
    @Condition
    def is_l1(): return level == 1
    @Condition
    def is_l2(): return level == 2
    @Condition
    def is_l3(): return level == 3

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
            # 判断是否是带 meta 的 session 行
            is_session_row = isinstance(row, (list, tuple)) and len(row) == 3
            if is_session_row:
                st, tx, meta = row
            else:
                st, tx = row if isinstance(row, (list, tuple)) else (None, str(row))
                meta = None

            # 滚动条
            rel = ab - scroll_y
            if ky is not None:
                ch = "#" if ky <= rel < ky + kh else "│"
                bar = ch
            else:
                bar = ""

            is_sel = (sel_abs is not None and ab == sel_abs)

            # 构建行文本
            if is_session_row:
                # 计算可用的显示宽度
                avail_w = 72 - (1 if bar else 0)
                line = tx
                if meta:
                    meta_display = f"  {meta}"
                    meta_vis_w = wcs(meta_display)
                    # 把 meta 推到右侧，用空格填充
                    line_vis_w = wcs(line)
                    pad = max(1, avail_w - line_vis_w - meta_vis_w)
                    line = line + " " * pad + meta_display
                line = wctrunc(line, avail_w) + bar
            else:
                line = tx + bar

            if is_sel and is_session_row and meta:
                # 选中 + 有元信息 → 不同区域不同样式
                # 分两段渲染太复杂，统一用 selected 高亮整行
                frags.append(("class:selected", f"{line}\n"))
            elif is_sel:
                frags.append(("class:selected", f"{line}\n"))
            elif st:
                frags.append((f"class:{st}", f"{line}\n"))
            else:
                frags.append(("", f"{line}\n"))

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
    foot = Window(height=1, content=FormattedTextControl(lambda: [("class:status",f"  {info_msg}")] if info_msg else []), align=WindowAlign.LEFT)

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
