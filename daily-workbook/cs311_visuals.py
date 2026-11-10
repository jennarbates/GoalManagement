"""Friendly inline-SVG diagrams for the CS311 workbook pages.

    import cs311_visuals
    svg_html = cs311_visuals.render(spec)            # one diagram
    svg_html = cs311_visuals.render_walkthrough(fs)  # a list of {"caption", "visual"} frames

render() returns a self-contained <svg> string (no scripts, no external assets)
with width="100%", a viewBox sized to its content and a max-width equal to
its natural size, so 1 unit = 1 CSS px and 12 units of font = 12px. The
viewBox is computed from everything drawn, so labels never get clipped.
Standard library only.

Colors
------
Anywhere a color is accepted use a palette name or a "#rrggbb" hex:
"blue", "yellow", "pink", "lavender", "teal", "coral", "gray".

Common keys (every spec)
------------------------
type      required, one of the types below
caption   optional small muted line under the drawing
legend    optional [{"color": c, "label": str, "kind": "node"|"edge"|"dash"}]

Labels
------
"n^2", "n^(log2 3)", "S_a", "t_(m+1)" render as super/subscripts.

Spec types
----------
graph
    nodes   [{"id", "label"?, "x"?, "y"? (0..1 of width/height),
              "color"?, "highlight"? bool, "faded"? bool, "shape"? "circle"|"box",
              "note"? str, "note_pos"? "above"|"below"|"left"|"right", "note_color"?}]
            labels may contain "\\n" (box nodes get one line per row)
    edges   [{"from", "to", "label"?, "directed"? bool, "highlight"? bool,
              "color"?, "dashed"? bool, "faded"? bool, "mark"? "x",
              "bend"? float (curve, + or -), "label_pos"? 0..1}]
    directed   default for edges (false)
    layout     "circle" (default when nodes lack x/y) | "row"
    layers     [[ids], [ids], ...]   left-to-right columns (BFS layers, DAGs)
    bands      [{"x": 0..1, "label", "color"?, "width"? px}]  soft column shading
    groups     [{"nodes": [ids], "label"?, "color"?}]  rounded blob around nodes (cuts, sets)
    width, height (layout box, default 400 x 160), node_radius (15)

bipartite (alias "matching")
    left, right   [ids] or [{"id", "label"?, "color"?, "highlight"?, "note"?}]
    edges         [{"from" (left id), "to" (right id),
                    "style": "match"|"plain"|"propose"|"reject"|"faded", "color"?, "label"?}]
    left_title, right_title, row_gap (36), span (column distance, 150)
    "note" on a node prints beside it on the outside (e.g. a preference list)

intervals
    items    [{"label", "start", "end", "state": "chosen"|"plain"|"skipped"|"faded",
               "color"?, "note"?}]   one row each, top to bottom
    min, max, tick_step (1), width (420), markers [{"at", "label"?, "color"?}]

array
    cells    [values]  ("" or null = empty box to write in)
    or rows  [{"label"?, "cells", "offset"? (cells to shift right), ...per-row keys}]
    per-row: highlight [idx] | colors {"idx": color}, faded [idx],
             pointers [{"at", "label", "color"?}] (arrow under a cell),
             ranges [{"from", "to", "label"?, "color"?}] (bracket above cells)
    index    true to number cells (start_index, default 0), cell_width (34)

tree
    root     {"label", "color"?, "highlight"?, "note"?, "children": [...]}
             a node with "label": "..." and no children is drawn as plain dots
    level_labels [str per depth], level_title str (e.g. "work"), level_gap (48)

table
    cells    2-D list (null or "" = blank cell to fill in)
    row_headers, col_headers, corner
    highlight [[r, c]], colors {"r,c": color}, faded [[r, c]]
    arrows   [{"from": [r, c], "to": [r, c], "color"?}]  (dependency arrows)
    cell_width (34), cell_height (26)

numberline
    min, max, tick_step (1), width (420), tick_labels (true)
    points   [{"at", "label"?, "state": "plain"|"center"|"faded", "color"?}]
    ranges   [{"from", "to", "label"?, "color"?, "row"? int}]   bands above the line
    hops     [{"from", "to", "label"?}]   arcs above the line

ladder   (slowest-to-fastest staircase)
    steps    [labels] ("" = empty step to fill in), notes [str]? under each step
    pool     [labels]? chips shown above ("sort these")
    left_label, right_label

curves   (function plot)
    series   [{"label", "expr" (e.g. "3*n^2+10*n+5", supports + - * / ^,
               log, log2, ln, sqrt, exp), "color"?, "dashed"?}]
    x_min (0), x_max, y_max, width (380), height (150), x_label, y_label
    markers  [{"x", "label"?, "shade"? bool (shade x >= this)}]

stacks   (load balancing bars)
    rows     [{"label", "items": [{"size", "label"?, "color"?}]}]
    max, lines [{"at", "label"?, "color"?}], queue [sizes or labels], queue_label
    width (360), show_totals (true)

strip    (side-by-side panels, used for walkthroughs)
    panels   [{"caption"?, "visual": spec}]
    columns  (default min(len, 4)), width (650 max), numbered (true)
"""
from __future__ import annotations

import html
import math
import re

FONT = '"Avenir Next", Avenir, "Helvetica Neue", sans-serif'
INK = "#3c3c3c"
MUTED = "#8a7f75"
LINE = "#B9AFA3"
BG = "#fffdf8"
NODE_STROKE = "#C9BDAE"
MAX_W = 650

# name: (light fill, mid/pastel, line, ink)
PALETTE = {
    "blue": ("#EAF3F9", "#A8C4D8", "#6F9DC0", "#2F5277"),
    "yellow": ("#FFF5D9", "#F5D38B", "#D6A53C", "#7D5B21"),
    "pink": ("#FDEDF4", "#F2B5CF", "#DB82A8", "#8A3B5E"),
    "lavender": ("#F1ECFF", "#C8B6FF", "#9A84E6", "#4F3F8F"),
    "teal": ("#E5F6F3", "#9DD9D2", "#4FB0A5", "#2B6B64"),
    "coral": ("#FDEAE5", "#F4B4A4", "#E07A62", "#9A4434"),
    "gray": ("#F4F0EA", "#DDD4C8", "#B3A796", "#6F655B"),
}


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(c, other, t):
    a, b = _hex(c), _hex(other)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def _pal(color, default="gray"):
    if not color:
        color = default
    if color in PALETTE:
        return PALETTE[color]
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        return (_mix(color, "#ffffff", 0.75), color, _mix(color, "#000000", 0.2), _mix(color, "#000000", 0.55))
    return PALETTE[default]


# ── text helpers ──────────────────────────────────────────────────────────

_NARROW = set("il.,:;|!'1()[]{}tfjrI ")
_WIDE = set("mwMW%@")


def _segments(text):
    """Split a label into (string, kind) runs; kind is '', 'sup' or 'sub'."""
    text = str(text)
    out, i, buf = [], 0, ""
    while i < len(text):
        ch = text[i]
        if ch in "^_" and i + 1 < len(text) and text[i + 1] not in " ^_":
            kind = "sup" if ch == "^" else "sub"
            if text[i + 1] == "(":
                depth, j = 0, i + 1
                while j < len(text):
                    if text[j] == "(":
                        depth += 1
                    elif text[j] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                inner = text[i + 2:j]
                i = j + 1
            else:
                m = re.match(r"[\w.]+", text[i + 1:])
                if not m:
                    buf += ch
                    i += 1
                    continue
                inner = m.group(0)
                i += 1 + len(inner)
            if buf:
                out.append((buf, ""))
                buf = ""
            out.append((inner, kind))
        else:
            buf += ch
            i += 1
    if buf:
        out.append((buf, ""))
    return out


def _cw(ch):
    if ch in _NARROW:
        return 0.34
    if ch in _WIDE:
        return 0.86
    if ch.isupper():
        return 0.68
    if ord(ch) > 0x2000:
        return 0.75
    return 0.57


def _tw(text, size=12, weight=400):
    w = 0.0
    for s, kind in _segments(text):
        k = 0.72 if kind else 1.0
        w += sum(_cw(c) for c in s) * k
    return w * size * (1.06 if weight >= 600 else 1.0)


def _tspans(text, size=12):
    """Escape a label, turning ^x / _x runs into raised / lowered tspans (dy-based, prints reliably)."""
    parts, cur = [], 0.0
    small = round(size * 0.72, 1)
    for s, kind in _segments(text):
        e = html.escape(s)
        want = -0.36 * size if kind == "sup" else 0.22 * size if kind == "sub" else 0.0
        dy = want - cur
        cur = want
        dys = f' dy="{_f(dy)}"' if abs(dy) > 1e-6 else ""
        fs = f' font-size="{small}"' if kind else ""
        parts.append(f"<tspan{dys}{fs}>{e}</tspan>" if (dys or fs) else e)
    return "".join(parts)


def _wrap(text, width, size=11):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and _tw(trial, size) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


def _f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


# ── canvas that tracks its own bounding box ───────────────────────────────

class _Canvas:
    def __init__(self):
        self.parts = []
        self.x0 = self.y0 = math.inf
        self.x1 = self.y1 = -math.inf

    def grow(self, x0, y0, x1, y1):
        self.x0, self.y0 = min(self.x0, x0), min(self.y0, y0)
        self.x1, self.y1 = max(self.x1, x1), max(self.y1, y1)

    def raw(self, svg, box=None):
        self.parts.append(svg)
        if box:
            self.grow(*box)

    def rect(self, x, y, w, h, fill="none", stroke="none", sw=1.2, rx=6, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.raw(f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" rx="{_f(rx)}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{o}/>', (x, y, x + w, y + h))

    def circle(self, cx, cy, r, fill="#fff", stroke=NODE_STROKE, sw=1.6, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.raw(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d}{o}/>', (cx - r, cy - r, cx + r, cy + r))

    def line(self, x1, y1, x2, y2, stroke=LINE, sw=1.5, dash=None, opacity=None, cap="round"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.raw(f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" stroke="{stroke}" '
                 f'stroke-width="{sw}" stroke-linecap="{cap}"{d}{o}/>',
                 (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def path(self, d, pts, stroke=LINE, sw=1.5, fill="none", dash=None, opacity=None):
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.raw(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
                 f'stroke-linecap="round" stroke-linejoin="round"{ds}{o}/>', (min(xs), min(ys), max(xs), max(ys)))

    def text(self, x, y, s, size=12, anchor="middle", fill=INK, weight=400, opacity=None, italic=False):
        w = _tw(s, size, weight)
        x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        o = f' opacity="{opacity}"' if opacity is not None else ""
        it = ' font-style="italic"' if italic else ""
        wt = f' font-weight="{weight}"' if weight != 400 else ""
        self.raw(f'<text x="{_f(x)}" y="{_f(y)}" font-size="{size}" text-anchor="{anchor}" '
                 f'fill="{fill}"{wt}{o}{it}>{_tspans(s, size)}</text>',
                 (x0, y - size * 0.8, x0 + w, y + size * 0.3))
        return w

    def pill(self, cx, cy, s, size=11, fill=BG, stroke="none", color=INK, weight=400, padx=5, h=None):
        w = _tw(s, size, weight) + 2 * padx
        h = h or size + 6
        self.rect(cx - w / 2, cy - h / 2, w, h, fill=fill, stroke=stroke, sw=1, rx=h / 2)
        self.text(cx, cy + size * 0.36, s, size=size, fill=color, weight=weight)
        return w

    def arrowhead(self, x, y, ang, color=LINE, size=7):
        a1, a2 = ang + math.radians(150), ang - math.radians(150)
        p = [(x, y), (x + size * math.cos(a1), y + size * math.sin(a1)),
             (x + size * math.cos(a2), y + size * math.sin(a2))]
        pts = " ".join(f"{_f(px)},{_f(py)}" for px, py in p)
        self.raw(f'<polygon points="{pts}" fill="{color}" stroke="{color}" stroke-width="1" '
                 f'stroke-linejoin="round"/>', (min(q[0] for q in p), min(q[1] for q in p),
                                                 max(q[0] for q in p), max(q[1] for q in p)))

    def cross(self, x, y, color=PALETTE["coral"][2], s=4.5):
        self.line(x - s, y - s, x + s, y + s, stroke=color, sw=2.2)
        self.line(x - s, y + s, x + s, y - s, stroke=color, sw=2.2)

    def check(self, x, y, color=PALETTE["teal"][3], s=5):
        d = f"M{_f(x - s)},{_f(y)} L{_f(x - s * 0.3)},{_f(y + s * 0.7)} L{_f(x + s)},{_f(y - s * 0.8)}"
        self.path(d, [(x - s, y - s), (x + s, y + s)], stroke=color, sw=2)

    def empty(self):
        return self.x0 == math.inf

    def finish(self, pad=8):
        if self.empty():
            self.grow(0, 0, 10, 10)
        w = self.x1 - self.x0 + 2 * pad
        h = self.y1 - self.y0 + 2 * pad
        body = f'<g transform="translate({_f(pad - self.x0)},{_f(pad - self.y0)})">' + "".join(self.parts) + "</g>"
        return math.ceil(w), math.ceil(h), body


# ── shared node drawing ───────────────────────────────────────────────────

def _node_dims(label, r=15, shape=None, size=12):
    lines = str(label).split("\n")
    tw = max(_tw(s, size, 600) for s in lines)
    if shape == "box" or len(lines) > 1 or tw > 2 * r - 6:
        return "box", max(tw + 18, 2 * r) / 2, (size + 13 + (len(lines) - 1) * (size + 3)) / 2
    return "circle", r, r


def _draw_node(cv, x, y, n, r=15):
    label = str(n.get("label", n.get("id", "")))
    shape, hw, hh = _node_dims(label, r, n.get("shape"))
    light, mid, line, ink = _pal(n.get("color"), "gray")
    if n.get("color"):
        fill, stroke, tc, sw = light, mid, ink, 1.6
    else:
        fill, stroke, tc, sw = "#ffffff", NODE_STROKE, INK, 1.6
    if n.get("highlight"):
        fill, stroke, tc, sw = mid, line, ink, 2.2
        if not n.get("color"):
            fill, stroke, tc = PALETTE["teal"][1], PALETTE["teal"][2], PALETTE["teal"][3]
    op = 0.38 if n.get("faded") else None
    dash = "3 3" if n.get("faded") else None
    if shape == "circle":
        cv.circle(x, y, r, fill=fill, stroke=stroke, sw=sw, opacity=op, dash=dash)
    else:
        cv.rect(x - hw, y - hh, 2 * hw, 2 * hh, fill=fill, stroke=stroke, sw=sw, rx=min(hh, 11), opacity=op, dash=dash)
    lines = label.split("\n")
    y0 = y - (len(lines) - 1) * 7.5 + 4.3
    for i, s in enumerate(lines):
        cv.text(x, y0 + i * 15, s, size=12, fill=tc, weight=600, opacity=op)
    note = n.get("note")
    if note not in (None, ""):
        pos = n.get("note_pos", "above")
        nl, nm, _, nk = _pal(n.get("note_color") or n.get("color") or "yellow")
        nw = _tw(note, 10.5) + 10
        if pos == "below":
            cx, cy = x, y + hh + 11
        elif pos == "left":
            cx, cy = x - hw - 5 - nw / 2, y
        elif pos == "right":
            cx, cy = x + hw + 5 + nw / 2, y
        else:
            cx, cy = x, y - hh - 11
        cv.pill(cx, cy, note, size=10.5, fill=nl, stroke=nm, color=nk)
    return shape, hw, hh


def _boundary(shape, hw, hh, cx, cy, ux, uy, extra=0.0):
    """Point on a node's outline in unit direction (ux, uy)."""
    if shape == "circle":
        return cx + ux * (hw + extra), cy + uy * (hw + extra)
    t = min(hw / abs(ux) if abs(ux) > 1e-9 else math.inf, hh / abs(uy) if abs(uy) > 1e-9 else math.inf)
    return cx + ux * (t + extra), cy + uy * (t + extra)


def _edge_style(e, default_color=None):
    color = e.get("color") or default_color
    if e.get("highlight"):
        stroke = _pal(color or "teal")[2]
        # keep the dash on highlighted edges (e.g. a backward "undo" residual edge on the path)
        return stroke, 3.0, ("6 4" if e.get("dashed") else None), None
    if e.get("faded"):
        return LINE, 1.3, "3 4", 0.55
    stroke = _pal(color)[2] if color else "#A99E92"
    return stroke, 1.6, ("5 4" if e.get("dashed") else None), None


def _draw_edge(cv, a, b, ga, gb, e, directed, bend=0.0):
    """a, b = centers; ga, gb = (shape, hw, hh)."""
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    px, py = -dy / L, dx / L
    cx, cy = (x1 + x2) / 2 + px * bend * L, (y1 + y2) / 2 + py * bend * L
    # start / end on node outlines, aimed at the control point
    sx, sy = cx - x1, cy - y1
    sl = math.hypot(sx, sy) or 1
    s = _boundary(*ga, x1, y1, sx / sl, sy / sl, 1)
    ex, ey = cx - x2, cy - y2
    el = math.hypot(ex, ey) or 1
    t_end = _boundary(*gb, x2, y2, ex / el, ey / el, 2 if directed else 1)
    stroke, sw, dash, op = _edge_style(e)
    end = t_end
    if directed:
        ang = math.atan2(t_end[1] - cy, t_end[0] - cx)
        hl = 8 if sw > 2 else 7
        end = (t_end[0] - math.cos(ang) * hl * 0.8, t_end[1] - math.sin(ang) * hl * 0.8)
    d = f"M{_f(s[0])},{_f(s[1])} Q{_f(cx)},{_f(cy)} {_f(end[0])},{_f(end[1])}"
    cv.path(d, [s, (cx, cy), end], stroke=stroke, sw=sw, dash=dash, opacity=op)
    if directed:
        cv.arrowhead(t_end[0], t_end[1], ang, color=stroke, size=9 if sw > 2 else 7.5)
    t = e.get("label_pos", 0.5)
    lx = (1 - t) ** 2 * s[0] + 2 * (1 - t) * t * cx + t * t * t_end[0]
    ly = (1 - t) ** 2 * s[1] + 2 * (1 - t) * t * cy + t * t * t_end[1]
    off = e.get("label_offset", 0)
    lx, ly = lx + px * off, ly + py * off
    label = e.get("label")
    mark = e.get("mark")
    if label not in (None, ""):
        if e.get("highlight"):
            fill, st, col = _pal(e.get("color") or "teal")[0], _pal(e.get("color") or "teal")[2], _pal(e.get("color") or "teal")[3]
        else:
            fill, st, col = BG, "#E6DDD1", INK
        w = _tw(label, 11, 600) + 10
        if mark == "x":
            w += 12
        cv.rect(lx - w / 2, ly - 8.5, w, 17, fill=fill, stroke=st, sw=1, rx=8.5,
                opacity=0.6 if e.get("faded") else None)
        tx = lx - (6 if mark == "x" else 0)
        cv.text(tx, ly + 4, label, size=11, weight=600, fill=col, opacity=0.6 if e.get("faded") else None)
        if mark == "x":
            cv.cross(lx + w / 2 - 9, ly, s=3.2)
    elif mark == "x":
        cv.circle(lx, ly, 7, fill=BG, stroke=PALETTE["coral"][1], sw=1)
        cv.cross(lx, ly, s=3.2)


# ── type: graph ───────────────────────────────────────────────────────────

def _graph(spec, cv):
    W, H = spec.get("width", 400), spec.get("height", 160)
    r = spec.get("node_radius", 15)
    nodes = spec.get("nodes", [])
    n = len(nodes)
    pos = {}
    if spec.get("layers"):
        layers = spec["layers"]
        for li, layer in enumerate(layers):
            for k, nid in enumerate(layer):
                pos[nid] = ((li + 0.5) / len(layers), (k + 0.5) / len(layer))
    for i, nd in enumerate(nodes):
        if "x" in nd and "y" in nd:
            pos[nd["id"]] = (nd["x"], nd["y"])
        elif nd["id"] not in pos:
            if spec.get("layout") == "row":
                pos[nd["id"]] = ((i + 0.5) / n, 0.5)
            else:
                a = -math.pi / 2 + 2 * math.pi * i / max(n, 1)
                pos[nd["id"]] = (0.5 + 0.42 * math.cos(a), 0.5 + 0.42 * math.sin(a))
    P = {k: (x * W, y * H) for k, (x, y) in pos.items()}
    byid = {nd["id"]: nd for nd in nodes}
    geo = {nid: _node_dims(byid[nid].get("label", nid), r, byid[nid].get("shape"))[0:3] for nid in byid}

    for b in spec.get("bands", []):
        bl, bm, _, bk = _pal(b.get("color"), "blue")
        bw = b.get("width", 56)
        bx = b["x"] * W
        cv.rect(bx - bw / 2, -12, bw, H + 24, fill=bl, stroke="none", rx=14, opacity=0.75)
        cv.text(bx, -20, b.get("label", ""), size=10.5, fill=bk, weight=600)

    for g in spec.get("groups", []):
        gl, gm, gline, gk = _pal(g.get("color"), "yellow")
        xs0, ys0, xs1, ys1 = [], [], [], []
        for nid in g["nodes"]:
            x, y = P[nid]
            _, hw, hh = geo[nid]
            xs0.append(x - hw); xs1.append(x + hw); ys0.append(y - hh); ys1.append(y + hh)
        p = g.get("pad", 10)
        x0, y0, x1, y1 = min(xs0) - p, min(ys0) - p, max(xs1) + p, max(ys1) + p
        cv.rect(x0, y0, x1 - x0, y1 - y0, fill=gl, stroke=gline, sw=1.4, rx=16, dash="5 4", opacity=0.9)
        if g.get("label"):
            pos_ = g.get("label_pos", "above")
            if pos_ == "below":
                cv.text((x0 + x1) / 2, y1 + 13, g["label"], size=10.5, fill=gk, weight=600)
            else:
                cv.text((x0 + x1) / 2, y0 - 5, g["label"], size=10.5, fill=gk, weight=600)

    edges = spec.get("edges", [])
    pairs = {(e["from"], e["to"]) for e in edges}
    for e in edges:
        directed = e.get("directed", spec.get("directed", False))
        bend = e.get("bend")
        if bend is None:
            bend = 0.16 if (e["to"], e["from"]) in pairs and directed else 0.0
        _draw_edge(cv, P[e["from"]], P[e["to"]], geo[e["from"]], geo[e["to"]], e, directed, bend)

    for nd in nodes:
        x, y = P[nd["id"]]
        _draw_node(cv, x, y, nd, r)


# ── type: bipartite ───────────────────────────────────────────────────────

def _items(lst):
    return [x if isinstance(x, dict) else {"id": x} for x in lst]


def _bipartite(spec, cv):
    left, right = _items(spec.get("left", [])), _items(spec.get("right", []))
    gap = spec.get("row_gap", 36)
    span = spec.get("span", 150)
    r = spec.get("node_radius", 15)
    rows = max(len(left), len(right))
    def ys(k):
        off = (rows - k) * gap / 2
        return [off + i * gap for i in range(k)]
    P, geo = {}, {}
    for nd, y in zip(left, ys(len(left))):
        P[("L", nd["id"])] = (0, y)
    for nd, y in zip(right, ys(len(right))):
        P[("R", nd["id"])] = (span, y)
    for nd in left:
        geo[("L", nd["id"])] = _node_dims(nd.get("label", nd["id"]), r)
    for nd in right:
        geo[("R", nd["id"])] = _node_dims(nd.get("label", nd["id"]), r)
    top = -r - 12
    if spec.get("left_title"):
        cv.text(0, top, spec["left_title"], size=10.5, fill=MUTED, weight=600)
    if spec.get("right_title"):
        cv.text(span, top, spec["right_title"], size=10.5, fill=MUTED, weight=600)
    for e in spec.get("edges", []):
        a, b = P[("L", e["from"])], P[("R", e["to"])]
        ga, gb = geo[("L", e["from"])], geo[("R", e["to"])]
        style = e.get("style", "plain")
        color = e.get("color")
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        s = _boundary(*ga, a[0], a[1], ux, uy, 1)
        t = _boundary(*gb, b[0], b[1], -ux, -uy, 1)
        if style == "match":
            stroke = _pal(color or "teal")[2]
            cv.line(*s, *t, stroke=stroke, sw=3.2)
        elif style == "propose":
            stroke = _pal(color)[2] if color else "#A99E92"
            t2 = _boundary(*gb, b[0], b[1], -ux, -uy, 2)
            cv.line(s[0], s[1], t2[0] - ux * 6, t2[1] - uy * 6, stroke=stroke, sw=1.6)
            cv.arrowhead(t2[0], t2[1], math.atan2(uy, ux), color=stroke)
        elif style == "reject":
            stroke = PALETTE["coral"][2]
            cv.line(*s, *t, stroke=stroke, sw=1.6, dash="4 4")
            mx, my = s[0] + (t[0] - s[0]) * 0.62, s[1] + (t[1] - s[1]) * 0.62
            cv.circle(mx, my, 7, fill=BG, stroke=PALETTE["coral"][1], sw=1)
            cv.cross(mx, my, s=3.2)
        elif style == "faded":
            cv.line(*s, *t, stroke=LINE, sw=1.2, dash="3 4", opacity=0.6)
        else:
            stroke = _pal(color)[2] if color else "#A99E92"
            cv.line(*s, *t, stroke=stroke, sw=1.6, dash="5 4" if e.get("dashed") else None)
        if e.get("label"):
            cv.pill((s[0] + t[0]) / 2, (s[1] + t[1]) / 2, e["label"], size=10.5, fill=BG, stroke="#E6DDD1")
    for side, lst in (("L", left), ("R", right)):
        default = spec.get("left_color", "blue") if side == "L" else spec.get("right_color", "pink")
        for nd in lst:
            x, y = P[(side, nd["id"])]
            d = dict(nd)
            d.setdefault("color", default)
            note = d.pop("note", None)
            _draw_node(cv, x, y, d, r)
            if note:
                _, hw, _ = geo[(side, nd["id"])]
                if side == "L":
                    cv.text(x - hw - 8, y + 4, note, size=11, anchor="end", fill=MUTED)
                else:
                    cv.text(x + hw + 8, y + 4, note, size=11, anchor="start", fill=MUTED)


# ── type: intervals ───────────────────────────────────────────────────────

def _intervals(spec, cv):
    items = spec.get("items", [])
    lo = spec.get("min", min((i["start"] for i in items), default=0))
    hi = spec.get("max", max((i["end"] for i in items), default=10))
    W = spec.get("width", 420)
    u = W / (hi - lo)
    rh = spec.get("row_height", 19)
    bh = spec.get("bar_height", 12)
    X = lambda v: (v - lo) * u
    gut = max((_tw(i.get("label", ""), 11.5, 600) for i in items), default=0) + 10
    bottom = len(items) * rh
    # grid ticks
    step = spec.get("tick_step", 1)
    v = lo
    while v <= hi + 1e-9:
        cv.line(X(v), -4, X(v), bottom, stroke="#EFE7DC", sw=1)
        v += step
    for mk in spec.get("markers", []):
        ml, mm, mline, mk_ = _pal(mk.get("color"), "coral")
        cv.line(X(mk["at"]), -6, X(mk["at"]), bottom + 2, stroke=mline, sw=1.6, dash="4 3")
        if mk.get("label"):
            cv.pill(X(mk["at"]), -14, mk["label"], size=10, fill=ml, stroke=mm, color=mk_)
    for k, it in enumerate(items):
        y = k * rh + (rh - bh) / 2
        state = it.get("state", "plain")
        light, mid, line, ink = _pal(it.get("color"), "teal" if state == "chosen" else "blue")
        x0, x1 = X(it["start"]), X(it["end"])
        lab_op = None
        if state == "chosen":
            cv.rect(x0, y, x1 - x0, bh, fill=mid, stroke=line, sw=1.6, rx=bh / 2)
        elif state == "skipped":
            cv.rect(x0, y, x1 - x0, bh, fill="#ffffff", stroke=LINE, sw=1.2, rx=bh / 2, dash="4 3")
            lab_op = 0.55
        elif state == "faded":
            cv.rect(x0, y, x1 - x0, bh, fill=PALETTE["gray"][0], stroke=PALETTE["gray"][1], sw=1, rx=bh / 2, opacity=0.6)
            lab_op = 0.45
        else:
            cv.rect(x0, y, x1 - x0, bh, fill=light, stroke=mid, sw=1.4, rx=bh / 2)
        cv.text(-8, y + bh / 2 + 4, it.get("label", ""), size=11.5, anchor="end",
                fill=ink if state == "chosen" else INK, weight=600, opacity=lab_op)
        if state == "chosen":
            cv.check(x1 + 9, y + bh / 2, color=line)
        if it.get("note"):
            nx = x1 + (22 if state == "chosen" else 7)
            cv.text(nx, y + bh / 2 + 4, it["note"], size=10.5, anchor="start", fill=MUTED, opacity=lab_op)
    # axis
    ay = bottom + 6
    cv.line(0, ay, W, ay, stroke="#A99E92", sw=1.3)
    v = lo
    while v <= hi + 1e-9:
        cv.line(X(v), ay, X(v), ay + 4, stroke="#A99E92", sw=1.2)
        cv.text(X(v), ay + 15, _f(v), size=10, fill=MUTED)
        v += step
    cv.grow(-gut, 0, 0, 0)


# ── type: array ───────────────────────────────────────────────────────────

def _array(spec, cv):
    rows = spec.get("rows") or [spec]
    cwmin = spec.get("cell_width", 34)
    ch = spec.get("cell_height", 30)
    allcells = [c for r_ in rows for c in r_.get("cells", [])]
    cw = max([cwmin] + [_tw("" if c is None else c, 13, 600) + 14 for c in allcells])
    gut = max([_tw(r_.get("label", ""), 11, 600) for r_ in rows] + [0])
    gut = gut + 12 if gut else 0
    y = 0
    for r_ in rows:
        has_ranges = bool(r_.get("ranges"))
        idx = r_.get("index", spec.get("index", False))
        top = y + (22 if has_ranges else 0) + (14 if idx else 0)
        off = r_.get("offset", 0)
        hl = set(r_.get("highlight", []))
        colors = {int(k): v for k, v in r_.get("colors", {}).items()}
        faded = set(r_.get("faded", []))
        hcolor = r_.get("highlight_color", spec.get("highlight_color", "yellow"))
        if r_.get("label"):
            cv.text(-12, top + ch / 2 + 4, r_["label"], size=11, anchor="end", fill=MUTED, weight=600)
        X = lambda i: (i + off) * (cw + 4)
        for i, c in enumerate(r_.get("cells", [])):
            x = X(i)
            blank = c is None or c == ""
            op = 0.4 if i in faded else None
            if i in hl:
                l_, m_, ln_, k_ = _pal(hcolor)
                cv.rect(x, top, cw, ch, fill=m_, stroke=ln_, sw=1.8, rx=7, opacity=op)
                tc = k_
            elif i in colors:
                l_, m_, ln_, k_ = _pal(colors[i])
                cv.rect(x, top, cw, ch, fill=l_, stroke=m_, sw=1.5, rx=7, opacity=op)
                tc = k_
            elif blank:
                cv.rect(x, top, cw, ch, fill="#ffffff", stroke="#CFC4B6", sw=1.2, rx=7, dash="3 3", opacity=op)
                tc = INK
            else:
                cv.rect(x, top, cw, ch, fill="#ffffff", stroke=NODE_STROKE, sw=1.4, rx=7, opacity=op)
                tc = INK
            if not blank:
                cv.text(x + cw / 2, top + ch / 2 + 4.5, str(c), size=13, fill=tc, weight=600, opacity=op)
            if idx:
                si = r_.get("start_index", spec.get("start_index", 0))
                cv.text(x + cw / 2, top - 5, str(i + si), size=9.5, fill=MUTED)
        for rg in r_.get("ranges", []):
            l_, m_, ln_, k_ = _pal(rg.get("color"), "lavender")
            x0, x1 = X(rg["from"]) + 2, X(rg["to"]) + cw - 2
            by = top - (14 if idx else 0) - 6
            d = f"M{_f(x0)},{_f(by + 4)} L{_f(x0)},{_f(by)} L{_f(x1)},{_f(by)} L{_f(x1)},{_f(by + 4)}"
            cv.path(d, [(x0, by), (x1, by + 4)], stroke=ln_, sw=1.6)
            if rg.get("label"):
                cv.text((x0 + x1) / 2, by - 4, rg["label"], size=10.5, fill=k_, weight=600)
        bottom = top + ch
        ptrs = r_.get("pointers", [])
        if ptrs:
            # put each label on the first level where it doesn't collide with another label
            levels = []  # list of [(x0, x1), ...] per level
            placed = []
            for p in ptrs:
                x = X(p["at"]) + cw / 2
                w = _tw(p["label"], 10.5) + 10
                lv = 0
                while lv < len(levels) and any(not (x + w / 2 + 4 < a or x - w / 2 - 4 > b) for a, b in levels[lv]):
                    lv += 1
                if lv == len(levels):
                    levels.append([])
                levels[lv].append((x - w / 2, x + w / 2))
                placed.append((p, x, lv))
            for p, x, lv in placed:
                l_, m_, ln_, k_ = _pal(p.get("color"), "pink")
                ly = bottom + 22 + lv * 19
                cv.line(x, ly - 9, x, bottom + 6, stroke=ln_, sw=1.6)
                cv.arrowhead(x, bottom + 2, -math.pi / 2, color=ln_, size=6)
            for p, x, lv in placed:
                l_, m_, ln_, k_ = _pal(p.get("color"), "pink")
                cv.pill(x, bottom + 22 + lv * 19, p["label"], size=10.5, fill=l_, stroke=m_, color=k_)
            bottom += 22 + 19 * len(levels) - 6
        y = bottom + 14
    if gut:
        cv.grow(-gut, 0, 0, 0)


# ── type: tree ────────────────────────────────────────────────────────────

def _tree(spec, cv):
    root = spec["root"]
    gap = spec.get("sibling_gap", 10)
    lg = spec.get("level_gap", 48)
    cursor = [0.0]
    placed = []

    def dims(nd):
        lab = str(nd.get("label", ""))
        if lab in ("...", "…", "⋯") and not nd.get("children"):
            return "dots", 12, 8
        return _node_dims(lab, 15, nd.get("shape"))

    def lay(nd, depth):
        g = dims(nd)
        kids = nd.get("children", [])
        if kids:
            xs = [lay(k, depth + 1) for k in kids]
            x = (xs[0] + xs[-1]) / 2
            # keep a wide parent from hanging over the previous subtree
        else:
            x = cursor[0] + g[1]
            cursor[0] += 2 * g[1] + gap
        nd["_x"], nd["_y"], nd["_g"], nd["_d"] = x, depth * lg, g, depth
        placed.append(nd)
        return x

    lay(root, 0)
    for nd in placed:
        for k in nd.get("children", []):
            (s0, hw, hh), (s1, khw, khh) = nd["_g"], k["_g"]
            cv.line(nd["_x"], nd["_y"] + hh, k["_x"], k["_y"] - khh + (4 if s1 == "dots" else 0),
                    stroke="#B9AFA3", sw=1.4, dash="2 3" if s1 == "dots" else None)
    maxd = max(nd["_d"] for nd in placed)
    for nd in placed:
        if nd["_g"][0] == "dots":
            cv.text(nd["_x"], nd["_y"] + 4, "⋯", size=14, fill=MUTED, weight=600)
        else:
            _draw_node(cv, nd["_x"], nd["_y"], nd)
    labels = spec.get("level_labels", [])
    if labels:
        right = max(nd["_x"] + nd["_g"][1] for nd in placed)
        lx = right + 26
        for d, lab in enumerate(labels[:maxd + 1]):
            if lab in (None, ""):
                continue
            rowr = max(nd["_x"] + nd["_g"][1] for nd in placed if nd["_d"] == d)
            cv.line(rowr + 6, d * lg, lx - 6, d * lg, stroke="#D9CFC2", sw=1.2, dash="1 4")
            l_, m_, ln_, k_ = _pal(spec.get("level_color"), "lavender")
            w = _tw(lab, 11, 600) + 12
            cv.rect(lx, d * lg - 9, w, 18, fill=l_, stroke=m_, sw=1, rx=9)
            cv.text(lx + w / 2, d * lg + 4, lab, size=11, fill=k_, weight=600)
        if spec.get("level_title"):
            cv.text(lx, -lg * 0 - 24, spec["level_title"], size=10, anchor="start", fill=MUTED, weight=600)
    for nd in placed:
        for k in ("_x", "_y", "_g", "_d"):
            nd.pop(k, None)


# ── type: table ───────────────────────────────────────────────────────────

def _table(spec, cv):
    cells = spec.get("cells", [])
    rh_ = spec.get("row_headers", [])
    chd = spec.get("col_headers", [])
    ncols = max([len(r) for r in cells] + [len(chd)])
    cwmin, ch = spec.get("cell_width", 34), spec.get("cell_height", 26)
    widths = []
    for c in range(ncols):
        w = cwmin
        for r in cells:
            if c < len(r) and r[c] not in (None, ""):
                w = max(w, _tw(r[c], 12, 600) + 14)
        if c < len(chd):
            w = max(w, _tw(chd[c], 10.5, 600) + 10)
        widths.append(w)
    if spec.get("uniform", True):
        widths = [max(widths)] * ncols
    hw = max([_tw(h, 11, 600) + 14 for h in rh_] + [_tw(spec.get("corner", ""), 10, 600) + 10] + [0]) if (rh_ or spec.get("corner")) else 0
    xs = [hw]
    for w in widths:
        xs.append(xs[-1] + w)
    top = 20 if chd else 0
    hl = {tuple(p) for p in spec.get("highlight", [])}
    fd = {tuple(p) for p in spec.get("faded", [])}
    colors = {tuple(int(v) for v in k.split(",")): c for k, c in spec.get("colors", {}).items()}
    hcolor = spec.get("highlight_color", "yellow")
    if spec.get("corner"):
        cv.text(hw - 8, 13, spec["corner"], size=10, anchor="end", fill=MUTED, italic=True)
    for c, h in enumerate(chd):
        cv.text(xs[c] + widths[c] / 2, 13, h, size=10.5, fill=MUTED, weight=600)
    later = []  # cell text goes on top of the dependency arrows
    nrows = len(cells)
    for r, row in enumerate(cells):
        y = top + r * ch
        if r < len(rh_):
            cv.text(hw - 8, y + ch / 2 + 4, rh_[r], size=11, anchor="end", fill=INK, weight=600)
        for c in range(ncols):
            v = row[c] if c < len(row) else None
            x = xs[c]
            blank = v is None or v == ""
            op = 0.4 if (r, c) in fd else None
            if (r, c) in hl:
                l_, m_, ln_, k_ = _pal(hcolor)
                fill, stroke, tc, sw, dash = m_, ln_, k_, 1.8, None
            elif (r, c) in colors:
                l_, m_, ln_, k_ = _pal(colors[(r, c)])
                fill, stroke, tc, sw, dash = l_, m_, k_, 1.3, None
            elif blank:
                fill, stroke, tc, sw, dash = "#ffffff", "#D8CEC1", INK, 1.1, "3 3"
            else:
                fill, stroke, tc, sw, dash = "#ffffff", "#D8CEC1", INK, 1.1, None
            cv.rect(x + 1.5, y + 1.5, widths[c] - 3, ch - 3, fill=fill, stroke=stroke, sw=sw, rx=5, dash=dash, opacity=op)
            if not blank:
                later.append((x + widths[c] / 2, y + ch / 2 + 4.3, str(v), tc, op))
    arrows = spec.get("arrows", [])
    into = {}
    for a in arrows:
        into.setdefault(tuple(a["to"]), []).append(a)
    for a in arrows:
        (r0, c0), (r1, c1) = a["from"], a["to"]
        sib = into[(r1, c1)]
        spread = (sib.index(a) - (len(sib) - 1) / 2) * 9
        stroke = _pal(a.get("color"), "pink")[2]
        cx0, cx1 = xs[c0] + widths[c0] / 2, xs[c1] + widths[c1] / 2
        cy0, cy1 = top + r0 * ch + ch / 2, top + r1 * ch + ch / 2
        if r0 == r1:
            # arc outside the row: below the last row, otherwise above
            below = a.get("side", "below" if r0 == nrows - 1 else "above") == "below"
            sgn = 1 if below else -1
            edge = cy0 + sgn * (ch / 2 - 1.5)
            sx, sy = cx0, edge
            ex, ey = cx1 + spread, edge
            cx, cy = (sx + ex) / 2, edge + sgn * (12 + 7 * abs(c1 - c0))
        elif c0 == c1:
            # hook around the side of the column
            right = a.get("side", "right" if c0 == ncols - 1 else "left") == "right"
            sgn = 1 if right else -1
            edge = cx0 + sgn * (widths[c0] / 2 - 1.5)
            sx, sy = edge, cy0
            ex, ey = edge, cy1 + spread
            cx, cy = edge + sgn * (14 + 5 * abs(r1 - r0)), (sy + ey) / 2
        else:
            dx, dy = cx1 - cx0, cy1 - cy0
            L = math.hypot(dx, dy) or 1
            ux, uy = dx / L, dy / L
            bend = a.get("bend", 0.15)
            sx, sy = _boundary("box", widths[c0] / 2 - 6, ch / 2 - 6, cx0, cy0, ux, uy)
            ex, ey = _boundary("box", widths[c1] / 2 - 3, ch / 2 - 3, cx1, cy1, -ux, -uy)
            cx, cy = (sx + ex) / 2 - uy * bend * L, (sy + ey) / 2 + ux * bend * L
        ang = math.atan2(ey - cy, ex - cx)
        e2 = (ex - math.cos(ang) * 5, ey - math.sin(ang) * 5)
        cv.path(f"M{_f(sx)},{_f(sy)} Q{_f(cx)},{_f(cy)} {_f(e2[0])},{_f(e2[1])}",
                [(sx, sy), ((sx + 2 * cx + ex) / 4, (sy + 2 * cy + ey) / 4), e2], stroke=stroke, sw=1.8)
        cv.arrowhead(ex, ey, ang, color=stroke, size=7)
    for x, y, v, tc, op in later:
        cv.text(x, y, v, size=12, fill=tc, weight=600, opacity=op)


# ── type: numberline ──────────────────────────────────────────────────────

def _numberline(spec, cv):
    lo, hi = spec.get("min", 0), spec.get("max", 10)
    W = spec.get("width", 420)
    u = W / (hi - lo)
    X = lambda v: (v - lo) * u
    step = spec.get("tick_step", 1)
    cv.line(-6, 0, W + 6, 0, stroke="#A99E92", sw=1.5)
    v = lo
    while v <= hi + 1e-9:
        cv.line(X(v), -4, X(v), 4, stroke="#A99E92", sw=1.2)
        if spec.get("tick_labels", True):
            cv.text(X(v), 18, _f(v), size=10, fill=MUTED)
        v += step
    for rg in spec.get("ranges", []):
        l_, m_, ln_, k_ = _pal(rg.get("color"), "teal")
        row = rg.get("row", 0)
        y = -30 - row * 22
        a, b = max(rg["from"], lo), min(rg["to"], hi)
        cv.rect(X(a), y - 6, X(b) - X(a), 12, fill=l_, stroke=m_, sw=1.2, rx=6)
        cv.line(X(a), y + 6, X(a), -4, stroke=m_, sw=1, dash="2 3")
        cv.line(X(b), y + 6, X(b), -4, stroke=m_, sw=1, dash="2 3")
        if rg.get("label"):
            lab = rg["label"]
            if _tw(lab, 10, 600) + 8 < X(b) - X(a):
                cv.text((X(a) + X(b)) / 2, y + 3.5, lab, size=10, fill=k_, weight=600)
            else:
                cv.text((X(a) + X(b)) / 2, y - 9, lab, size=10, fill=k_, weight=600)
    for hp in spec.get("hops", []):
        a, b = X(hp["from"]), X(hp["to"])
        h = min(46, max(14, abs(b - a) * 0.45))
        mx = (a + b) / 2
        stroke = _pal(hp.get("color"), "lavender")[2]
        end_ang = math.atan2(0 - (-h), b - mx)
        ex = b - math.cos(end_ang) * 5
        ey = -7 - math.sin(end_ang) * 5
        cv.path(f"M{_f(a)},-7 Q{_f(mx)},{_f(-7 - 2 * h)} {_f(ex)},{_f(ey)}", [(a, -7), (mx, -7 - h), (b, -7)],
                stroke=stroke, sw=1.7)
        cv.arrowhead(b, -6, end_ang, color=stroke, size=6.5)
        if hp.get("label"):
            cv.text(mx, -7 - h - 5, hp["label"], size=10, fill=_pal(hp.get("color"), "lavender")[3], weight=600)
    for p in spec.get("points", []):
        st = p.get("state", "plain")
        l_, m_, ln_, k_ = _pal(p.get("color"), "pink" if st == "center" else "blue")
        x = X(p["at"])
        if st == "center":
            cv.circle(x, 0, 8.5, fill=m_, stroke=ln_, sw=2)
            cv.circle(x, 0, 2.5, fill=ln_, stroke=ln_, sw=0.5)
        elif st == "faded":
            cv.circle(x, 0, 5, fill="#fff", stroke=LINE, sw=1.3, opacity=0.6)
        else:
            cv.circle(x, 0, 6, fill=l_, stroke=ln_, sw=1.8)
        if p.get("label"):
            cv.text(x, -14 if not spec.get("ranges") else 34, p["label"], size=10.5, fill=k_, weight=600)


# ── type: ladder ──────────────────────────────────────────────────────────

def _ladder(spec, cv):
    steps = spec.get("steps", [])
    notes = spec.get("notes", [])
    sh = spec.get("step_height", 20)
    cols = ["blue", "teal", "yellow", "pink", "lavender", "coral"]
    widths = [max(_tw(s, 12.5, 600) + 22, _tw(notes[i] if i < len(notes) else "", 9.5) + 10, 64)
              for i, s in enumerate(steps)]
    x = 0.0
    n = len(steps)
    for i, s in enumerate(steps):
        w = widths[i]
        top = -(i + 1) * sh - 22
        blank = s in (None, "")
        l_, m_, ln_, k_ = _pal(cols[i % len(cols)])
        if blank:
            cv.rect(x, top, w - 4, -top, fill="#ffffff", stroke="#CFC4B6", sw=1.2, rx=8, dash="4 3")
        else:
            cv.rect(x, top, w - 4, -top, fill=l_, stroke=m_, sw=1.4, rx=8)
            cv.text(x + (w - 4) / 2, top + 16, s, size=12.5, fill=k_, weight=600)
        if i < len(notes) and notes[i]:
            cv.text(x + (w - 4) / 2, -5, notes[i], size=9.5, fill=MUTED)
        x += w
    yb = 10
    cv.line(0, yb, x - 10, yb, stroke="#A99E92", sw=1.4)
    cv.arrowhead(x - 4, yb, 0, color="#A99E92", size=7)
    cv.text(0, yb + 15, spec.get("left_label", "slower"), size=10.5, anchor="start", fill=MUTED, weight=600)
    cv.text(x - 4, yb + 15, spec.get("right_label", "faster"), size=10.5, anchor="end", fill=MUTED, weight=600)
    pool = spec.get("pool")
    if pool:
        py = -(n + 1) * sh - 30
        px = 0.0
        if spec.get("pool_label", "sort these:"):
            px += cv.text(0, py + 4, spec.get("pool_label", "sort these:"), size=10.5, anchor="start", fill=MUTED, weight=600) + 8
        for i, s in enumerate(pool):
            l_, m_, ln_, k_ = _pal(cols[i % len(cols)])
            w = _tw(s, 12, 600) + 14
            cv.rect(px, py - 10, w, 22, fill=l_, stroke=m_, sw=1.2, rx=11)
            cv.text(px + w / 2, py + 5, s, size=12, fill=k_, weight=600)
            px += w + 6


# ── type: curves (with a tiny safe expression parser) ─────────────────────

_TOK = re.compile(r"\s*(?:(\d+\.?\d*|\.\d+)|([A-Za-z_]\w*)|(.))")
_FUNCS = {"log": lambda v: math.log2(v), "log2": math.log2, "ln": math.log, "sqrt": math.sqrt, "exp": math.exp}


def _parse(expr):
    toks = []
    for num, name, op in _TOK.findall(expr):
        toks.append(("num", float(num)) if num else ("name", name) if name else ("op", op))
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else ("end", None)

    def take():
        t = peek()
        pos[0] += 1
        return t

    def expr_():
        node = term()
        while peek() in (("op", "+"), ("op", "-")):
            op = take()[1]
            rhs = term()
            node = (op, node, rhs)
        return node

    def term():
        node = unary()
        while peek() in (("op", "*"), ("op", "/")):
            op = take()[1]
            rhs = unary()
            node = (op, node, rhs)
        return node

    def unary():
        if peek() == ("op", "-"):
            take()
            return ("neg", unary())
        return power()

    def power():
        base = atom()
        if peek() == ("op", "^"):
            take()
            return ("^", base, unary())
        return base

    def atom():
        kind, val = take()
        if kind == "num":
            return ("num", val)
        if kind == "name":
            if val in _FUNCS:
                if peek() == ("op", "("):
                    take()
                    arg = expr_()
                    take()
                else:
                    arg = power()
                return ("fn", val, arg)
            return ("var", val)
        if (kind, val) == ("op", "("):
            node = expr_()
            take()
            return node
        raise ValueError(f"bad expression: {expr}")

    tree = expr_()

    def ev(nd, n):
        k = nd[0]
        if k == "num":
            return nd[1]
        if k == "var":
            return n
        if k == "neg":
            return -ev(nd[1], n)
        if k == "fn":
            return _FUNCS[nd[1]](ev(nd[2], n))
        a, b = ev(nd[1], n), ev(nd[2], n)
        # Only compute the operator this node uses (a dict of all five would also
        # evaluate a ** b for a plain subtraction and overflow on big values).
        if k == "+":
            return a + b
        if k == "-":
            return a - b
        if k == "*":
            return a * b
        if k == "/":
            return a / b
        return a ** b

    return lambda n: ev(tree, n)


def _curves(spec, cv):
    W, H = spec.get("width", 380), spec.get("height", 150)
    x0, x1 = spec.get("x_min", 0), spec.get("x_max", 10)
    ymax = spec["y_max"]
    X = lambda v: (v - x0) / (x1 - x0) * W
    Y = lambda v: H - v / ymax * H
    for mk in spec.get("markers", []):
        if mk.get("shade"):
            cv.rect(X(mk["x"]), 0, W - X(mk["x"]), H, fill=PALETTE["yellow"][0], rx=0, opacity=0.8)
    cv.line(0, H, W + 6, H, stroke="#A99E92", sw=1.4)
    cv.line(0, H, 0, -6, stroke="#A99E92", sw=1.4)
    cv.arrowhead(W + 10, H, 0, color="#A99E92", size=6)
    cv.arrowhead(0, -10, -math.pi / 2, color="#A99E92", size=6)
    if spec.get("x_label"):
        cv.text(W + 16, H + 15, spec["x_label"], size=11, anchor="start", fill=MUTED, weight=600)
    if spec.get("y_label"):
        cv.text(6, -6, spec["y_label"], size=10.5, anchor="start", fill=MUTED, weight=600)
    for t in spec.get("x_ticks", []):
        cv.line(X(t), H, X(t), H + 4, stroke="#A99E92", sw=1.2)
        cv.text(X(t), H + 15, _f(t), size=10, fill=MUTED)
    for mk in spec.get("markers", []):
        cv.line(X(mk["x"]), H, X(mk["x"]), 0, stroke=PALETTE["yellow"][2], sw=1.4, dash="4 3")
        if mk.get("label"):
            cv.pill(X(mk["x"]), H + 30, mk["label"], size=10, fill=PALETTE["yellow"][0], stroke=PALETTE["yellow"][1],
                    color=PALETTE["yellow"][3])
    right_labels, top_labels = [], []
    defaults = ["blue", "teal", "yellow", "pink", "lavender", "coral"]
    for si, s in enumerate(spec.get("series", [])):
        fn = _parse(s["expr"])
        color = _pal(s.get("color") or defaults[si % len(defaults)])[2]
        pts, exit_top = [], None
        N = 160
        prev = None
        for k in range(N + 1):
            xv = x0 + (x1 - x0) * k / N
            try:
                yv = fn(xv)
            except (ValueError, ZeroDivisionError, OverflowError):
                prev = None
                continue
            if yv > ymax:
                if prev is not None:
                    px_, py_ = prev
                    t = (ymax - py_) / (yv - py_)
                    pts.append((X(px_ + (xv - px_) * t), Y(ymax)))
                exit_top = pts[-1] if pts else None
                break
            if yv < 0:
                prev = (xv, yv)
                continue
            pts.append((X(xv), Y(yv)))
            prev = (xv, yv)
        if len(pts) < 2:
            continue
        d = "M" + " L".join(f"{_f(a)},{_f(b)}" for a, b in pts)
        cv.path(d, pts, stroke=color, sw=2.3, dash="6 4" if s.get("dashed") else None)
        if exit_top:
            top_labels.append([exit_top[0], s["label"], color])
        else:
            right_labels.append([pts[-1][1], s["label"], color])
    right_labels.sort()
    for i in range(1, len(right_labels)):
        right_labels[i][0] = max(right_labels[i][0], right_labels[i - 1][0] + 14)
    # keep them above the x axis (and its label), pushing the stack upward if needed
    if right_labels and right_labels[-1][0] > H - 12:
        right_labels[-1][0] = H - 12
        for i in range(len(right_labels) - 2, -1, -1):
            right_labels[i][0] = min(right_labels[i][0], right_labels[i + 1][0] - 14)
    for y, lab, color in right_labels:
        cv.text(W + 8, y + 4, lab, size=11, anchor="start", fill=color, weight=600)
    top_labels.sort()
    last = -math.inf
    for item in top_labels:
        x, lab, color = item
        w = _tw(lab, 11, 600)
        x = max(x, last + w / 2 + 6)
        last = x + w / 2
        cv.text(x, -8, lab, size=11, fill=color, weight=600)


# ── type: stacks ──────────────────────────────────────────────────────────

def _stacks(spec, cv):
    rows = spec.get("rows", [])
    mx = spec.get("max") or max(sum(i["size"] for i in r["items"]) for r in rows)
    W = spec.get("width", 360)
    u = W / mx
    bh, gap = 24, 12
    cols = ["blue", "yellow", "pink", "teal", "lavender", "coral"]
    queue = spec.get("queue")
    y = 0
    if queue:
        x = 0.0
        lab = spec.get("queue_label", "jobs:")
        x += cv.text(0, 4, lab, size=10.5, anchor="start", fill=MUTED, weight=600) + 8
        for q in queue:
            w = max(_tw(str(q), 12, 600) + 14, 24)
            cv.rect(x, -10, w, 20, fill=PALETTE["gray"][0], stroke=PALETTE["gray"][1], sw=1.2, rx=6)
            cv.text(x + w / 2, 4.5, str(q), size=12, weight=600)
            x += w + 5
        y = 26
    top = y
    for r in rows:
        cv.text(-10, y + bh / 2 + 4, r.get("label", ""), size=11.5, anchor="end", fill=INK, weight=600)
        cv.rect(0, y, W, bh, fill="#ffffff", stroke="#E3D9CC", sw=1, rx=7, dash="2 3")
        x = 0.0
        for k, it in enumerate(r.get("items", [])):
            w = it["size"] * u
            l_, m_, ln_, k_ = _pal(it.get("color") or cols[k % len(cols)])
            cv.rect(x + 1, y + 1, w - 2, bh - 2, fill=l_, stroke=m_, sw=1.4, rx=6)
            lab = it.get("label", _f(it["size"]))
            if _tw(lab, 11.5, 600) < w - 4:
                cv.text(x + w / 2, y + bh / 2 + 4, lab, size=11.5, fill=k_, weight=600)
            x += w
        if spec.get("show_totals", True) and r.get("items"):
            tot = sum(i["size"] for i in r["items"])
            cv.text(W + 8, y + bh / 2 + 4, f"= {_f(tot)}", size=11.5, anchor="start", fill=INK, weight=600)
        y += bh + gap
    bottom = y - gap
    for ln in spec.get("lines", []):
        l_, m_, ln_, k_ = _pal(ln.get("color"), "coral")
        x = ln["at"] * u
        cv.line(x, top - 6, x, bottom + 6, stroke=ln_, sw=1.6, dash="4 3")
        if ln.get("label"):
            cv.pill(x, bottom + 17, ln["label"], size=10, fill=l_, stroke=m_, color=k_)


# ── type: strip ───────────────────────────────────────────────────────────

def _strip(spec, cv):
    panels = spec.get("panels", [])
    if not panels:
        return
    k = spec.get("columns") or min(len(panels), 4)
    gap = spec.get("gap", 10)
    total = min(spec.get("width", MAX_W - 16), MAX_W - 16)
    colw = (total - gap * (k - 1)) / k
    drawn = [_draw(p["visual"], pad=6) for p in panels]
    s = min([1.0] + [(colw - 8) / w for w, h, b in drawn])
    cellw = min(colw, max(w * s for w, h, b in drawn) + 8)
    numbered = spec.get("numbered", True)
    y = 0.0
    for start in range(0, len(panels), k):
        row = list(range(start, min(start + k, len(panels))))
        cap_lines = []
        for i in row:
            cap = panels[i].get("caption", "")
            cap_lines.append(_wrap(cap, cellw - (24 if numbered else 10), 10.5) if cap else [])
        ph = max(drawn[i][1] * s for i in row)
        caph = max(len(c) for c in cap_lines) * 13 + (8 if any(cap_lines) else 0)
        for j, i in enumerate(row):
            x = j * (cellw + gap)
            w, h, body = drawn[i]
            cv.rect(x, y, cellw, ph + caph + 8, fill="#ffffff", stroke="#EADFD2", sw=1.1, rx=10)
            ox = x + (cellw - w * s) / 2
            oy = y + 4 + (ph - h * s) / 2
            cv.raw(f'<g transform="translate({_f(ox)},{_f(oy)}) scale({s:.3f})">{body}</g>',
                   (ox, oy, ox + w * s, oy + h * s))
            cy = y + ph + 8
            lines = cap_lines[j]
            tx = x + 8
            if numbered and lines:
                cv.circle(x + 14, cy + 6, 7.5, fill=PALETTE["yellow"][1], stroke=PALETTE["yellow"][2], sw=1)
                cv.text(x + 14, cy + 9.5, str(i + 1), size=9.5, fill=PALETTE["yellow"][3], weight=700)
                tx = x + 26
            for li, ln in enumerate(lines):
                cv.text(tx, cy + 10 + li * 13, ln, size=10.5, anchor="start", fill=INK)
        y += ph + caph + 8 + gap


# ── dispatch ──────────────────────────────────────────────────────────────

_TYPES = {
    "graph": _graph, "bipartite": _bipartite, "matching": _bipartite, "intervals": _intervals,
    "array": _array, "tree": _tree, "table": _table, "numberline": _numberline, "ladder": _ladder,
    "curves": _curves, "stacks": _stacks, "strip": _strip, "steps": _strip,
}


def _draw(spec, pad=8):
    cv = _Canvas()
    fn = _TYPES.get(spec.get("type"))
    if fn is None:
        raise ValueError(f"unknown visual type: {spec.get('type')!r}")
    fn(spec, cv)
    if spec.get("legend") or spec.get("caption"):
        base = (cv.y1 if not cv.empty() else 0) + 16
        x0 = cv.x0 if not cv.empty() else 0
        if spec.get("legend"):
            x = x0
            for item in spec["legend"]:
                l_, m_, ln_, k_ = _pal(item.get("color"), "gray")
                kind = item.get("kind", "node")
                if kind == "edge":
                    cv.line(x, base, x + 18, base, stroke=ln_, sw=3)
                    x += 24
                elif kind == "dash":
                    cv.line(x, base, x + 18, base, stroke=ln_, sw=1.6, dash="4 3")
                    x += 24
                else:
                    cv.circle(x + 6, base, 6, fill=m_, stroke=ln_, sw=1.4)
                    x += 16
                x += cv.text(x, base + 4, item["label"], size=10.5, anchor="start", fill=MUTED) + 14
            base += 18
        if spec.get("caption"):
            cx = (cv.x0 + cv.x1) / 2
            for i, ln in enumerate(_wrap(spec["caption"], max(cv.x1 - cv.x0, 200), 11)):
                cv.text(cx, base + 2 + i * 14, ln, size=11, fill=MUTED, italic=True)
    return cv.finish(pad)


def render(spec: dict) -> str:
    """Render a visual spec (see module docstring) to an inline <svg> string."""
    if not spec:
        return ""
    w, h, body = _draw(spec)
    label = html.escape(spec.get("alt") or spec.get("caption") or spec.get("type", "diagram"), quote=True)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="cs311-visual" viewBox="0 0 {w} {h}" '
            f'width="100%" style="max-width:{w}px;height:auto;display:block;margin:4px auto;" '
            f'font-family=\'{FONT}\' role="img" aria-label="{label}">'
            f'<rect x="0" y="0" width="{w}" height="{h}" rx="12" fill="{BG}"/>{body}</svg>')


def render_walkthrough(frames: list, **opts) -> str:
    """Render a list of {"caption", "visual"} frames as one strip of panels."""
    if not frames:
        return ""
    return render({"type": "strip", "panels": frames, **opts})


def size_of(spec: dict) -> tuple[int, int]:
    """Natural (width, height) in px of a rendered spec (handy for layout checks)."""
    w, h, _ = _draw(spec)
    return w, h


if __name__ == "__main__":
    demo = {"type": "graph", "directed": True,
            "nodes": [{"id": "s", "x": 0.05, "y": 0.5}, {"id": "a", "x": 0.5, "y": 0.1},
                      {"id": "b", "x": 0.5, "y": 0.9}, {"id": "t", "x": 0.95, "y": 0.5}],
            "edges": [{"from": "s", "to": "a", "label": "4"}, {"from": "s", "to": "b", "label": "1"},
                      {"from": "b", "to": "a", "label": "2"}, {"from": "a", "to": "t", "label": "1"},
                      {"from": "b", "to": "t", "label": "5"}]}
    print(render(demo))
