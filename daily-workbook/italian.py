#!/usr/bin/env python3
"""Italian for the daily workbook: one printed day of "Tutt* a tavola!" at a time.

The course is the user's Quaderno (Volume 1, chapters 1-6), extracted into
italian_course.json by extract_italian_course.py. It splits into days of whole
sections the way the earlier printed days did: in order, up to 5 sections and
18 exercises a day (about 60-90 minutes). Each day prints its lessons and
exercises, a "Before you stop" box, a chapter review when the day finishes a
chapter, and a Vocabolario page with that day's words. The answer key is
separate (answer_pages) so the workbook can print it at the very back.

Progress lives in italian_progress.json: {"by_date": {"YYYY-MM-DD": day_number}}.
Set ITALIAN_PROGRESS_FILE (or italian.PROGRESS_FILE) to use another file.

    python3 italian.py                 # today's day (doesn't mark anything)
    python3 italian.py plan            # how the course splits into days
    python3 italian.py status          # which days have been printed
    python3 italian.py preview 3 out.html   # a standalone page for day 3

Content adapted from Tutt* a tavola! Volume 1 by Stacy Giufre and Melina
Masterson, CC BY-NC 4.0. Standard library only.
"""
from __future__ import annotations

import html
import json
import math
import os
import re
import sys
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
COURSE_FILE = HERE / "italian_course.json"
PROGRESS_FILE = Path(os.environ.get("ITALIAN_PROGRESS_FILE") or HERE / "italian_progress.json")

MAX_SECTIONS_PER_DAY = 5
MAX_EXERCISES_PER_DAY = 18
# A day only reaches into the next chapter while it is still short.
NEW_CHAPTER_BELOW = 15
MINUTES = "60–90"
ATTRIBUTION_HTML = ("Adapted from <i>Tutt* a tavola!</i> Volume 1 by Stacy Giufre and Melina Masterson, "
                    "CC BY-NC 4.0")
ATTRIBUTION = re.sub(r"</?i>", "", ATTRIBUTION_HTML)
SAY_ALOUD = "Short on time? Say your answer aloud instead."
WEEKDAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


# ── Course and day plan ──────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _load_course(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_course() -> dict:
    return _load_course(str(COURSE_FILE))


def _sections(course: dict) -> list[dict]:
    out = []
    for ch in course["chapters"]:
        for s in ch["sections"]:
            out.append({**s, "chapter": ch["number"], "chapter_id": ch["id"]})
    return out


def plan_days(course: dict | None = None) -> list[dict]:
    """Split the course into days of whole sections, in order.

    A day takes sections until the next one would push it past
    MAX_EXERCISES_PER_DAY exercises or MAX_SECTIONS_PER_DAY sections. It
    starts a new chapter only while it has fewer than NEW_CHAPTER_BELOW.
    """
    course = course or load_course()
    secs = _sections(course)
    days: list[list[dict]] = []
    cur: list[dict] = []
    n_ex = 0
    for s in secs:
        k = len(s["exercises"])
        if cur and (n_ex + k > MAX_EXERCISES_PER_DAY or len(cur) >= MAX_SECTIONS_PER_DAY
                    or (s["chapter"] != cur[-1]["chapter"] and n_ex >= NEW_CHAPTER_BELOW)):
            days.append(cur)
            cur, n_ex = [], 0
        cur.append(s)
        n_ex += k
    if cur:
        days.append(cur)

    last_day_of_chapter = {}
    for i, d in enumerate(days, 1):
        for s in d:
            last_day_of_chapter[s["chapter"]] = i

    plan = [{"day": i, "section_ids": [s["id"] for s in d],
             "exercise_count": sum(len(s["exercises"]) for s in d),
             "finishes_chapters": [c for c, last in last_day_of_chapter.items() if last == i],
             "vocab": []} for i, d in enumerate(days, 1)]
    _assign_vocab(course, days, plan, last_day_of_chapter)
    return plan


def _plain(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def _section_text(s: dict) -> str:
    return _plain(json.dumps({"l": s["lesson"], "a": s.get("after"), "e": s["exercises"]}, ensure_ascii=False)).lower()


def _vocab_keys(item: str) -> list[str]:
    """Searchable forms of a vocabulary entry: 'capire (-isc)' -> ['capire']."""
    base = re.sub(r"\s*\(.*?\)", "", item).strip().lower()
    keys = []
    for alt in re.split(r"\s*/\s*", base):
        alt = re.sub(r"^(il|lo|la|l’|l'|i|gli|le)\s+", "", alt.strip(" ?.!…"))
        if len(alt) >= 2:
            keys.append(alt)
    return keys


def _assign_vocab(course: dict, days: list[list[dict]], plan: list[dict], last_day: dict) -> None:
    """Each chapter vocabulary group goes to the day whose sections use most of its words."""
    for ch in course["chapters"]:
        texts = {}
        for i, d in enumerate(days, 1):
            t = " ".join(_section_text(s) for s in d if s["chapter"] == ch["number"])
            if t:
                texts[i] = t
        for gi, g in enumerate(ch["vocab"]):
            scores = {}
            for i, t in texts.items():
                scores[i] = sum(1 for it in g["items"]
                                if any(re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t) for k in _vocab_keys(it["it"])))
            best = max(scores.values()) if scores else 0
            target = min(i for i, v in scores.items() if v == best) if best else last_day[ch["number"]]
            plan[target - 1]["vocab"].append([ch["number"], gi])


# ── Progress ─────────────────────────────────────────────────────────────────

def _progress_path() -> Path:
    return Path(PROGRESS_FILE)


def load_progress() -> dict:
    try:
        p = json.loads(_progress_path().read_text(encoding="utf-8"))
        p.setdefault("by_date", {})
        return p
    except (FileNotFoundError, json.JSONDecodeError):
        return {"by_date": {}}


def save_progress(p: dict) -> None:
    _progress_path().write_text(json.dumps(p, indent=2) + "\n", encoding="utf-8")


def daily_set(day: date | None = None, mark: bool = True) -> dict:
    """The next unprinted day of the course (the same one when rerun on the same date).

    Returns {"done": True, ...} once every day has been printed.
    """
    day = day or date.today()
    key = day.isoformat()
    course = load_course()
    plan = plan_days(course)
    progress = load_progress()
    by_date = progress["by_date"]

    n = by_date.get(key)
    if not isinstance(n, int) or not 1 <= n <= len(plan):
        done = {v for v in by_date.values() if isinstance(v, int)}
        n = next((p["day"] for p in plan if p["day"] not in done), None)
        if n is None:
            return {"done": True, "date": key, "day": None, "total_days": len(plan),
                    "title": course["title"], "attribution": ATTRIBUTION}
        if mark:
            by_date[key] = n
            save_progress(progress)
    return day_set_for(n, day, course, plan)


def day_set_for(n: int, day: date | None = None, course: dict | None = None, plan: list | None = None) -> dict:
    """Everything render() needs for day n (1-based), without touching progress."""
    course = course or load_course()
    plan = plan or plan_days(course)
    day = day or date.today()
    p = plan[n - 1]
    by_id = {s["id"]: s for s in _sections(course)}
    sections = [by_id[i] for i in p["section_ids"]]
    chapters = {c["number"]: c for c in course["chapters"]}
    vocab = [{"chapter": c, "group": chapters[c]["vocab"][gi]["group"], "items": chapters[c]["vocab"][gi]["items"]}
             for c, gi in p["vocab"]]
    review = [{"chapter": c, "title": chapters[c]["title"], "goals": chapters[c]["goals"]}
              for c in p["finishes_chapters"]]
    return {
        "done": False,
        "date": day.isoformat(),
        "day": n,
        "total_days": len(plan),
        "title": course["title"],
        "subtitle": _day_subtitle(sections),
        "section_ids": p["section_ids"],
        "sections": sections,
        "exercise_count": p["exercise_count"],
        "minutes": MINUTES,
        "vocab": vocab,
        "review": review,
        "attribution": ATTRIBUTION,
    }


def _day_subtitle(sections: list[dict]) -> str:
    parts = []
    for s in sections:
        sub = _plain(s["subtitle"]).strip()
        sub = re.split(r"[:(]", sub)[0].strip()
        if sub.lower().startswith(("let’s listen", "let’s watch")):
            sub = "a " + ("song" if "listen" in sub.lower() else "film clip")
        if sub and sub not in parts:
            parts.append(sub)
    out = " · ".join(parts)
    return out[:1].upper() + out[1:]


# ── HTML helpers and height estimates ────────────────────────────────────────
# Pages are packed by estimated height so each fragment fits one printed
# sheet (8 x 10.5 in at print size, inside the workbook's frame). Heights are
# in CSS px at print size; the estimates err on the tall side.

CONTENT_W = 650          # px of text width inside the frame when printed
PAGE_BUDGET = 868        # px of content per sheet (footer excluded)
CW = 5.75                # average char width at 12.5px (Avenir)
LH = 18.5                # line height at 12.5px


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def _len(s: str) -> int:
    return len(_plain(s))


def _lines(chars: float, width: float, cw: float = CW) -> int:
    return max(1, math.ceil(chars * cw / max(width, 40)))


def text_h(s: str, width: float = CONTENT_W, lh: float = LH, cw: float = CW) -> float:
    lines = sum(_lines(len(_plain(part)), width, cw) for part in re.split(r"<br\s*/?>|\n", s))
    return lines * lh


def chip_w(text: str, cw: float = 6.1) -> float:
    return len(_plain(text)) * cw + 24


def flow_h(widths: list[float], width: float, row_h: float) -> float:
    """Height of inline boxes wrapping inside width."""
    rows, x = 1, 0.0
    for w in widths:
        if x and x + w > width:
            rows += 1
            x = 0.0
        x += w
    return rows * row_h


class Unit:
    """One piece of a page. Lesson units are wrapped together in the soft box."""
    __slots__ = ("html", "h", "lesson", "keep")

    def __init__(self, html_: str, h: float, lesson: str | None = None, keep: bool = False):
        self.html, self.h, self.lesson, self.keep = html_, h, lesson, keep


_DEBUG_UNITS = bool(os.environ.get("ITALIAN_DEBUG_UNITS"))
LESSON_OVERHEAD = 46     # box padding/border + LEZIONE label + bottom margin


def pack(units: list[Unit], budget: float = PAGE_BUDGET) -> list[list[Unit]]:
    pages: list[list[Unit]] = [[]]
    used = 0.0
    prev_lesson = None
    for i, u in enumerate(units):
        if u.html == "<!--pagebreak-->":
            if pages[-1]:
                pages.append([])
                used, prev_lesson = 0.0, None
            continue
        need = u.h + (LESSON_OVERHEAD if u.lesson and u.lesson != prev_lesson else 0)
        extra = 0.0
        j = i
        while units[j].keep and j + 1 < len(units):   # keep headers with what follows
            nxt = units[j + 1]
            extra += (nxt.h if nxt.h <= 320 else 140) + (LESSON_OVERHEAD if nxt.lesson and nxt.lesson != (units[j].lesson or prev_lesson) else 0)
            if not nxt.keep:
                break
            j += 1
        if pages[-1] and used + need + extra > budget:
            pages.append([])
            used, prev_lesson = 0.0, None
            need = u.h + (LESSON_OVERHEAD if u.lesson else 0)
        pages[-1].append(u)
        used += need
        prev_lesson = u.lesson
    return [p for p in pages if p]


def page_html(units: list[Unit], footer: str) -> str:
    out = []
    open_lesson = None
    for u in units:
        if u.lesson != open_lesson:
            if open_lesson:
                out.append("</div>")
            if u.lesson:
                out.append('<div class="it-lesson"><div class="it-lesson-label">Lezione</div>')
            open_lesson = u.lesson
        out.append(f'<div class="it-u" data-est="{u.h:.0f}">{u.html}</div>' if _DEBUG_UNITS else u.html)
    if open_lesson:
        out.append("</div>")
    return ('<div class="page flow"><div class="frame">'
            f'<div class="it-sheet">{"".join(out)}</div>'
            f'<div class="it-foot">{footer}</div>'
            '</div></div>')


def section_title(label: str, title: str, bubble: str) -> str:
    """Same markup as the workbook's section_title() (title/bubble may hold inline HTML)."""
    b = f' <span class="bubble">{bubble}</span>' if bubble else ""
    return (f'<div class="section-head"><div class="section-label">{esc(label)}</div>'
            f'<div class="section-title">{title}{b}</div></div>')


def write_lines(n: int) -> str:
    return '<div class="it-lines">' + '<div class="it-line"></div>' * n + "</div>"


def write_lines_h(n: int) -> float:
    return n * 30 + 4


def blank(answers: list[str] | None = None, min_w: int = 60) -> str:
    longest = max((len(a) for a in (answers or [])[:2]), default=6)
    w = max(min_w, min(300, int(longest * 8.5 + 30)))
    return f'<span class="it-blank" style="width:{w}px"></span>'


def blank_w(answers: list[str] | None = None, min_w: int = 60) -> int:
    longest = max((len(a) for a in (answers or [])[:2]), default=6)
    return max(min_w, min(300, int(longest * 8.5 + 30)))


def opt_chips(options: list[str]) -> str:
    return "".join(f'<span class="chip it-opt">{esc(o)}</span>' for o in options)


def clock_svg(h: int, m: int, size: int = 78) -> str:
    hr, mn = ((h % 12) + m / 60) * 30, m * 6
    ticks = "".join(
        f'<line x1="50" y1="6" x2="50" y2="{13 if i % 15 == 0 else 10}" stroke="#8a7a6f" '
        f'stroke-width="{2.4 if i % 15 == 0 else 1.2}" transform="rotate({i * 6} 50 50)"/>'
        for i in range(0, 60, 5))
    nums = "".join(f'<text x="{x}" y="{y}" font-size="11" text-anchor="middle" dominant-baseline="central" '
                   f'fill="#6b5a50" font-family="Avenir, Helvetica, Arial, sans-serif">{n}</text>'
                   for n, x, y in [(12, 50, 21), (3, 79, 50), (6, 50, 79), (9, 21, 50)])
    return (f'<svg class="it-clock" viewBox="0 0 100 100" width="{size}" height="{size}" role="img" '
            f'aria-label="clock">'
            f'<circle cx="50" cy="50" r="46" fill="#fff" stroke="#4b3a35" stroke-width="3"/>{ticks}{nums}'
            f'<line x1="50" y1="50" x2="50" y2="28" stroke="#4b3a35" stroke-width="5" stroke-linecap="round" '
            f'transform="rotate({hr:.1f} 50 50)"/>'
            f'<line x1="50" y1="50" x2="50" y2="14" stroke="#E56D5C" stroke-width="3" stroke-linecap="round" '
            f'transform="rotate({mn} 50 50)"/>'
            f'<circle cx="50" cy="50" r="3.5" fill="#4b3a35"/></svg>')


# ── Lesson blocks ────────────────────────────────────────────────────────────

def block_html(b: dict, width: float = CONTENT_W) -> tuple[str, float]:
    t = b["type"]
    if t == "p":
        return f'<p class="it-p">{b["html"]}</p>', text_h(b["html"], width) + 6
    if t == "heading":
        return f'<div class="it-h">{b["html"]}</div>', text_h(b["html"], width, 19, 7.2) + 9
    if t == "reading":
        return f'<div class="it-reading">{b["html"]}</div>', text_h(b["html"], width - 28) + 26
    if t == "list":
        items = "".join(f"<li>{x}</li>" for x in b["items"])
        tag = "ol" if b.get("ordered") else "ul"
        return (f'<{tag} class="it-ul">{items}</{tag}>',
                sum(text_h(x, width - 22) + 2 for x in b["items"]) + 6)
    if t == "table":
        return table_html(b, width)
    if t == "chips":
        chips = "".join(
            f'<span class="chip it-vchip">{c["it"]}' + (f'<span class="it-en"> · {c["en"]}</span>' if c["en"] else "")
            + "</span>" for c in b["items"])
        widths = [chip_w(c["it"] + (" · " + c["en"] if c["en"] else "")) + 4 for c in b["items"]]
        return f'<div class="it-chips">{chips}</div>', flow_h(widths, width, 25) + 6
    if t == "note":
        inner, h = blocks_html(b["blocks"], width - 28)
        kind = "it-note-tip" if b.get("kind") == "tip" else ""
        return (f'<div class="it-note {kind}"><div class="it-note-t">{esc(b["title"])}</div>{inner}</div>',
                h + 40)
    if t == "columns":
        cols = b["columns"]
        ncol = 2 if len(cols) != 3 else 3
        w = (width - 18 * (ncol - 1)) / ncol
        rendered = [blocks_html(c, w) for c in cols]
        # grid rows: max height of each row of ncol columns
        h = 0.0
        for r in range(0, len(rendered), ncol):
            h += max(x[1] for x in rendered[r:r + ncol]) + 6
        inner = "".join(f'<div class="it-col">{x[0]}</div>' for x in rendered)
        return f'<div class="it-cols it-cols-{ncol}">{inner}</div>', h
    if t == "dialog":
        lines = "".join(f"<div>{x}</div>" for x in b["lines"])
        return f'<div class="it-dialog">{lines}</div>', sum(text_h(x, width - 12) + 3 for x in b["lines"]) + 8
    if t == "letters":
        tiles = "".join(f'<span class="it-tile"><b>{esc(x["letter"].upper())}{esc(x["letter"])}</b>'
                        f'<span>{esc(x["name"])}</span></span>' for x in b["items"])
        per_row = 7
        return f'<div class="it-tiles">{tiles}</div>', math.ceil(len(b["items"]) / per_row) * 50 + 8
    if t == "numbers":
        cells = "".join(f'<span class="it-num"><b>{x["n"]}</b> {esc(x["word"])}</span>' for x in b["items"])
        return f'<div class="it-nums">{cells}</div>', math.ceil(len(b["items"]) / 5) * 22 + 8
    if t == "clocks":
        cells = "".join(f'<div class="it-clockcell">{clock_svg(x["h"], x["m"], 70)}'
                        f'<div class="it-clock-time">{x["h"]}:{x["m"]:02d}</div>'
                        f'<div class="it-clock-cap">{esc(x["label"])}</div></div>' for x in b["items"])
        rows = math.ceil(len(b["items"]) / 6)
        return f'<div class="it-clockrow">{cells}</div>', rows * 140 + 6
    if t == "story":
        title = f'<div class="it-h">{b["title"]}</div>' if b.get("title") else ""
        cards = "".join(f'<div class="it-frame"><b>{i}</b> {x["it"]}<div class="it-en">{x["en"]}</div></div>'
                        for i, x in enumerate(b["lines"], 1))
        w = (width - 16) / 3 - 18
        h = 0.0
        for r in range(0, len(b["lines"]), 3):
            row = b["lines"][r:r + 3]
            h += max(text_h(x["it"], w, 17.5, 6.4) + text_h(x["en"], w, 15, 5.6) for x in row) + 24
        return f'{title}<div class="it-story">{cards}</div>', h + (28 if title else 0) + 4
    return "", 0


def blocks_html(blocks: list[dict], width: float = CONTENT_W) -> tuple[str, float]:
    out, h = [], 0.0
    for b in blocks:
        x, bh = block_html(b, width)
        out.append(x)
        h += bh
    return "".join(out), h


def table_html(b: dict, width: float) -> tuple[str, float]:
    agenda = b.get("variant") == "agenda"
    head = b.get("head")

    def cell(c, tag):
        if isinstance(c, dict):
            attrs = "".join(f' {k}="{c[k]}"' for k in ("rowspan", "colspan") if c.get(k))
            return f"<{tag}{attrs}>{c['html']}</{tag}>"
        return f"<{tag}>{c}</{tag}>"

    ncols = max([len(head or [])] + [len(r) for r in b["rows"]]) or 1
    col_w = width / ncols
    rows_h = 0.0
    for r in b["rows"]:
        cw_, lh = (5.4, 14.5) if agenda else (CW, 17.5)
        rows_h += max(text_h(c["html"] if isinstance(c, dict) else c, col_w - 10, lh, cw_) for c in r) + 9
    thead = ("<tr>" + "".join(cell(c, "th") for c in head) + "</tr>") if head else ""
    body = "".join("<tr>" + "".join(cell(c, "td") for c in r) + "</tr>" for r in b["rows"])
    cls = "it-table it-agenda" if agenda else "it-table"
    return f'<table class="{cls}">{thead}{body}</table>', rows_h + (26 if head else 0) + 10


# ── Exercises ────────────────────────────────────────────────────────────────

def _fill_items_answers(ex: dict) -> list[list[list[str]]]:
    return [[p["blank"] for p in it["parts"] if isinstance(p, dict)] for it in ex["items"]]


def _weekday_answer(a: str, day: date) -> str:
    m = re.fullmatch(r"@weekday\+(\d+)", a)
    if not m:
        return a
    return WEEKDAYS_IT[(day.weekday() + int(m.group(1))) % 7]


def exercise_units(ex: dict, letter: str, day: date) -> list[Unit]:
    t = ex["type"]
    say_aloud = t == "open"
    head = (f'<div class="it-ex-head"><span class="it-letter">{letter}</span>'
            f'<div><div class="it-ex-title">{ex["title"]}</div>'
            f'<div class="it-ex-instr">{ex["instructions"]}</div></div></div>')
    head_h = 22 + text_h(ex["instructions"], CONTENT_W - 34, 16.5, 5.8) + 8
    if say_aloud:
        head += f'<div class="it-say">{SAY_ALOUD}</div>'
        head_h += 18
    units = []
    intro_html, intro_h = blocks_html(ex.get("intro", []), CONTENT_W)
    if intro_html:
        head += f'<div class="it-intro">{intro_html}</div>'
        head_h += intro_h + 6
    units.append(Unit(head, head_h, keep=True))

    def item(n, body, h):
        return Unit(f'<div class="it-item"><span class="it-n">{n}.</span><div class="it-body">{body}</div></div>', h)

    if t == "choice":
        rendered = []
        for n, it in enumerate(ex["items"], 1):
            q = it["prompt"]
            has_blank = "___" in q
            q = q.replace("___", blank(None, 80), 1).replace("___", blank(None, 80))
            w = _len(it["prompt"]) * CW + (80 if has_blank else 0) + 8 + sum(chip_w(o) + 4 for o in it["options"])
            rendered.append((n, f'<span class="it-q">{q}</span> <span class="it-opts">{opt_chips(it["options"])}</span>', w))
        half = (CONTENT_W - 31) / 2 - 40
        if len(rendered) >= 4 and max(w for _, _, w in rendered) <= half:
            # short items: two columns, numbered down the first column then the second
            rows = math.ceil(len(rendered) / 2)
            cells = "".join(f'<div class="it-item"><span class="it-n">{n}.</span><div class="it-body">{b}</div></div>'
                            for n, b, _ in rendered)
            units.append(Unit(f'<div class="it-2col" style="grid-template-rows:repeat({rows}, auto)">{cells}</div>',
                              rows * 32 + 4))
        else:
            for n, b, w in rendered:
                lines = math.ceil(w / (CONTENT_W - 26))
                units.append(item(n, b, lines * 25 + 7))
        if ex.get("board"):
            cells = "".join(f'<div class="it-tris-cell">{i}</div>' for i in range(1, 10))
            units.append(Unit(f'<div class="it-tris"><div class="it-tris-board">{cells}</div>'
                              f'<div class="it-ex-instr">Your board: mark X or O in each square after checking.</div></div>',
                              150))
    elif t == "fill":
        if ex.get("paragraph"):
            num = 0
            for it in ex["items"]:
                parts = []
                chars = 0
                blanks_w = 0
                for p in it["parts"]:
                    if isinstance(p, dict):
                        num += 1
                        parts.append(f'<sup class="it-sup">{num}</sup>{blank(p["blank"], 70)}')
                        blanks_w += blank_w(p["blank"], 70) + 10
                    else:
                        parts.append(p)
                        chars += _len(p)
                body = "".join(parts)
                nbr = body.count("<br>")
                lines = math.ceil((chars * CW + blanks_w) / (CONTENT_W - 40)) + nbr
                units.append(Unit(f'<div class="it-para">{body}</div>', lines * 31 + 22))
        else:
            for n, it in enumerate(ex["items"], 1):
                parts, w = [], 0.0
                for i, p in enumerate(it["parts"]):
                    if isinstance(p, dict):
                        ans = [_weekday_answer(a, day) for a in p["blank"]]
                        parts.append(blank(ans))
                        w += blank_w(ans) + 8
                    else:
                        txt = p
                        nxt_blank = i + 1 < len(it["parts"]) and isinstance(it["parts"][i + 1], dict)
                        prev_blank = i > 0 and isinstance(it["parts"][i - 1], dict)
                        if nxt_blank and not txt.endswith((" ", "’", "'")) and not re.search(r"\w$", txt):
                            txt = txt + " "
                        elif nxt_blank and len(it["parts"]) == 2 and i == 0:
                            txt = txt + " "
                        if prev_blank and not txt.startswith((" ", ",", ".", "?", "!", ")", ";", ":")):
                            txt = " " + txt
                        parts.append(txt)
                        w += _len(p) * CW
                lines = math.ceil(w / (CONTENT_W - 26))
                units.append(item(n, "".join(parts), lines * 30 + 6))
    elif t == "open":
        nlines = 5 if len(ex["prompts"]) == 1 else 4 if len(ex["prompts"]) == 2 else 2
        for p in ex["prompts"]:
            units.append(Unit(f'<div class="it-prompt">{p}</div>{write_lines(nlines)}',
                              text_h(p, CONTENT_W, 18, 6.9) + 6 + write_lines_h(nlines) + 6))
    elif t == "conjugation":
        heads = "".join(f"<th><i>{esc(v['infinitive'])}</i></th>" for v in ex["verbs"])
        rows = ""
        for r, person in enumerate(ex["persons"]):
            cells = "".join(
                f'<td class="it-given">{esc(v["forms"][r])}</td>' if r in v.get("given", []) else "<td></td>"
                for v in ex["verbs"])
            rows += f'<tr><td class="it-person">{esc(person)}</td>{cells}</tr>'
        units.append(Unit(f'<table class="it-conj"><tr><th></th>{heads}</tr>{rows}</table>',
                          30 + 6 * 31 + 12))
    elif t == "match":
        order = ex["right_order"]
        rows = ""
        h = 0.0
        colw = (CONTENT_W - 20) / 2
        for i, (l, _r) in enumerate(ex["pairs"]):
            right = ex["pairs"][order[i]][1]
            rows += (f'<div class="it-match-l"><span class="it-n">{i + 1}.</span><span class="it-blank" '
                     f'style="width:34px"></span> {l}</div>'
                     f'<div class="it-match-r"><b>{chr(65 + i)}</b> {right}</div>')
            h += max(text_h(l, colw - 70), text_h(right, colw - 24)) + 14
        units.append(Unit(f'<div class="it-match">{rows}</div>', h + 6))
    elif t == "checklist":
        lis = "".join(f'<li><span class="it-box"></span>{esc(x)}</li>' for x in ex["items"])
        colw = (CONTENT_W - 20) / 2
        half = math.ceil(len(ex["items"]) / 2)
        h = max(sum(text_h(esc(x), colw - 24) + 5 for x in ex["items"][:half]),
                sum(text_h(esc(x), colw - 24) + 5 for x in ex["items"][half:]))
        tally = f'<div class="it-tally">{esc(ex["tally"])}</div>' if ex.get("tally") else ""
        units.append(Unit(f'<ul class="it-check">{lis}</ul>{tally}', h + 34))
    elif t == "clock":
        items = ex["items"]
        for r in range(0, len(items), 4):
            cells = ""
            for n, x in enumerate(items[r:r + 4], r + 1):
                cells += (f'<div class="it-clockq"><div class="it-clockq-n">{n}</div>{clock_svg(x["h"], x["m"], 76)}'
                          f'<div class="it-clock-cap">{esc(x["part"])}</div><div class="it-line"></div></div>')
            units.append(Unit(f'<div class="it-clockgrid">{cells}</div>', 150))
    elif t == "bingo":
        rows = "".join("<tr>" + "".join(
            f'<td class="it-free">★</td>' if n == 0 else f"<td>{n}</td>" for n in row) + "</tr>"
            for row in ex["card"])
        calls = "".join(f'<li>{esc(c["word"])}</li>' for c in ex["calls"])
        units.append(Unit(f'<div class="it-bingo"><table class="it-bingo-card">{rows}</table>'
                          f'<div><div class="it-ex-instr">Numbers called, in order:</div>'
                          f'<ol class="it-calls">{calls}</ol></div></div>', 5 * 40 + 34))
    return units


# ── Answers ──────────────────────────────────────────────────────────────────

def _show_alts(alts: list[str], keep: int = 2) -> str:
    shown: list[str] = []
    for a in alts:
        if any(s.endswith(" " + a) or s == a for s in shown):
            continue
        shown.append(a)
    return " / ".join(esc(a) for a in shown[:keep])


def answer_html(ex: dict, label: str, day: date) -> tuple[str, float]:
    t = ex["type"]
    head = f'<div class="it-ans-h"><b>{label}</b> <i>{ex["title"]}</i></div>'
    body = ""
    if t == "choice":
        body = "  ".join(f'<b>{n}</b>&nbsp;{esc(it["answer"])}' + (f' <i>({it["why"]})</i>' if it.get("why") else "")
                         for n, it in enumerate(ex["items"], 1))
    elif t == "fill":
        blanks = _fill_items_answers(ex)
        if any("@weekday" in a for b in blanks for alts in b for a in alts):
            ans = ", ".join(_weekday_answer(alts[0], day) for b in blanks for alts in b)
            body = (f"<i>Depends on the day. Printed for {WEEKDAYS_IT[day.weekday()]} "
                    f"{day.day}/{day.month}:</i> {esc(ans)}")
        elif ex.get("paragraph"):
            flat = [alts for b in blanks for alts in b]
            body = "  ".join(f"<b>{n}</b>&nbsp;{_show_alts(a)}" for n, a in enumerate(flat, 1))
        else:
            body = "  ".join(f"<b>{n}</b>&nbsp;" + ", ".join(_show_alts(a) for a in b) for n, b in enumerate(blanks, 1))
    elif t == "open":
        ex_text = esc(ex.get("example", "")).replace("\n", "<br>")
        body = f'<i>Example answer. Yours can be different.</i><br>{ex_text}'
    elif t == "conjugation":
        body = "<br>".join(f'<b>{esc(v["infinitive"])}:</b> {esc(", ".join(v["forms"]))}' for v in ex["verbs"])
    elif t == "match":
        inv = {orig: pos for pos, orig in enumerate(ex["right_order"])}
        body = "  ".join(f"<b>{i + 1}</b>{chr(65 + inv[i])}" for i in range(len(ex["pairs"])))
    elif t == "checklist":
        body = "<i>No right answers: this one is about you.</i>"
    elif t == "clock":
        body = "  ".join(f"<b>{n}</b>&nbsp;{_show_alts(x['answers'])}" for n, x in enumerate(ex["items"], 1))
    elif t == "bingo":
        a = ex["answer"]
        body = (f"Crossed out: {', '.join(str(n) for n in a['hits'])}. "
                f"<b>Tombola!</b> on call {a['winning_call']}: {esc(a['line'])}.")
    h = 17 + text_h(body, CONTENT_W, 17, 5.0) + 8
    return f'<div class="it-ans">{head}<div class="it-ans-b">{body}</div></div>', h


# ── Pages ────────────────────────────────────────────────────────────────────

def _long_date(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}"


def _goal_as_i_can(g: str) -> str:
    g = re.sub(r"\byourself\b", "myself", g)
    g = re.sub(r"\byour\b", "my", g)
    g = re.sub(r"\byou\b", "I", g)
    return "I can " + g


def _lesson_units(sec: dict) -> list[Unit]:
    key = sec["id"]
    out = []
    blocks = []
    for b in sec["lesson"]:
        # Split big column groups into rows so a page can break between them.
        if b["type"] == "columns" and len(b["columns"]) > 2 and len(b["columns"]) != 3:
            blocks += [{"type": "columns", "columns": b["columns"][i:i + 2]} for i in range(0, len(b["columns"]), 2)]
        else:
            blocks.append(b)
    for b in blocks:
        x, h = block_html(b, CONTENT_W - 32)
        if x:
            # headings and "…:" lead-ins stay with what follows
            keep = b["type"] == "heading" or (b["type"] == "p" and _plain(b["html"]).rstrip().endswith(":"))
            out.append(Unit(x, h, lesson=key, keep=keep))
    return out


def _vocab_units(vocab: list[dict]) -> list[Unit]:
    units = [Unit(section_title("Italiano · vocabolario", "Vocabolario",
                                "cover the right side and say the English · 5 minutes"), 66)]
    colw = (CONTENT_W - 36) / 3
    for g in vocab:
        items = g["items"]
        # Long entries (phrases) get two columns, words get three.
        long_ = any(len(x["it"]) + len(x["en"]) > 34 for x in items)
        ncol = 2 if long_ else 3
        cw_ = (CONTENT_W - 18 * (ncol - 1)) / ncol
        row_hs = [max(text_h(esc(x["it"]), cw_ * 0.55, 15.5, 6.6), text_h(esc(x["en"]), cw_ * 0.45, 15.5, 6.0)) + 5
                  for x in items]
        per_col = math.ceil(len(items) / ncol)
        col_heights = [sum(row_hs[c * per_col:(c + 1) * per_col]) for c in range(ncol)]
        rows = "".join(f'<div class="it-vrow"><b>{esc(x["it"])}</b><span>{esc(x["en"])}</span></div>' for x in items)
        units.append(Unit(f'<div class="it-vgroup"><div class="it-h">{esc(g["group"])}</div>'
                          f'<div class="it-vcols it-vcols-{ncol}">{rows}</div></div>',
                          28 + max(col_heights) * 0.95 + 14, keep=False))
    return units


def lesson_units(ds: dict, day: date) -> list[Unit]:
    secs = ds["sections"]
    checks = "".join(f'<span class="it-todo"><span class="it-box"></span>{esc(s["id"])} {s["title"]}</span>'
                     for s in secs)
    checks += '<span class="it-todo"><span class="it-box"></span>5 min vocabulary</span>'
    sec_list = ", ".join(s["id"] for s in secs)
    todo_w = [chip_w(s["id"] + " " + _plain(s["title"]), 6.9) + 10 for s in secs] + [140]
    units = [Unit(
        section_title(f"Italiano · Tutt* a tavola! · day {ds['day']} of {ds['total_days']}",
                      f"Giorno {ds['day']}", esc(_long_date(day)))
        + f'<div class="it-daysub">{esc(ds["subtitle"])}</div>'
        + f'<div class="card it-today"><div><b>Today:</b> sections {esc(sec_list)} · {ds["exercise_count"]} exercises'
          f' · about {esc(ds["minutes"])} minutes</div><div class="it-todos">{checks}</div>'
          '<div class="footer-note">Read each Lezione, do its exercises, then check them with the Italian answer key '
          'at the back of the workbook. Circle the choice in multiple-choice questions.</div></div>',
        66 + 24 + 30 + flow_h(todo_w, CONTENT_W - 32, 24) + 40 + 14)]

    for s in secs:
        label = f"Italiano · capitolo {s['chapter']}"
        units.append(Unit(section_title(label, f'{esc(s["id"])} {s["title"]}', s["subtitle"]), 74, keep=True))
        units.extend(_lesson_units(s))
        for i, ex in enumerate(s["exercises"]):
            units.extend(exercise_units(ex, chr(65 + i), day))
        for b in s.get("after", []):
            x, h = block_html(b, CONTENT_W)
            units.append(Unit(x, h + 4))

    for r in ds["review"]:
        lis = "".join(f'<li><span class="it-box"></span>{esc(_goal_as_i_can(g))}</li>' for g in r["goals"])
        units.append(Unit(f'<div class="card it-review"><div class="mini-title">Ripasso: Capitolo {r["chapter"]} · '
                          f'{r["title"]}</div><div class="footer-note">Tick each one you could do without looking '
                          f'back. Anything unticked: revisit that section.</div><ul class="it-goals">{lis}</ul></div>',
                          80 + len(r["goals"]) * 24))
    units.append(Unit('<div class="card it-stop"><div class="mini-title">Before you stop</div>'
                      '<div class="footer-note">Write the two things that felt shakiest. Start tomorrow with a quick '
                      'look at them.</div><div class="it-stopline"><b>1.</b><div class="it-line"></div></div>'
                      '<div class="it-stopline"><b>2.</b><div class="it-line"></div></div></div>', 166))
    if ds["vocab"]:
        units.append(Unit("<!--pagebreak-->", 0))
        units.extend(_vocab_units(ds["vocab"]))
    return units


def answer_units(ds: dict, day: date) -> list[Unit]:
    units = [Unit(section_title(f"Italiano · day {ds['day']} · answer key", "Risposte",
                                "a missing accent is close, but still learn where it goes"), 66)]
    for s in ds["sections"]:
        for i, ex in enumerate(s["exercises"]):
            x, h = answer_html(ex, f'{s["id"]} {chr(65 + i)}', day)
            units.append(Unit(x, h))
    return units


def _done_pages() -> dict:
    page = ('<div class="page flow"><div class="frame"><div class="it-sheet">'
            + section_title("Italiano · Tutt* a tavola!", "Finito! 🎉", esc(load_course()["volume"]))
            + '<div class="card"><div class="mini-title">You’ve printed every day of the Quaderno.</div>'
              '<div class="footer-note">Review the chapter vocabularies, redo the exercises you marked as shaky, '
              'or tell Claude you’re ready for the next chapters.</div></div>'
            + f'</div><div class="it-foot">{ATTRIBUTION_HTML}</div></div></div>')
    return {"css": CSS, "lesson_pages": [page], "answer_pages": []}


def render(day_set: dict) -> dict:
    """HTML fragments for one day: {"css", "lesson_pages": [...], "answer_pages": [...]}.

    Each page is a full <div class="page flow"><div class="frame">…</div></div>
    sized to one printed sheet. Answers are only in answer_pages.
    """
    if day_set.get("done"):
        return _done_pages()
    day = datetime.strptime(day_set["date"], "%Y-%m-%d").date()
    n = day_set["day"]
    lesson = pack(lesson_units(day_set, day))
    answers = pack(answer_units(day_set, day))
    total = len(lesson)
    lesson_pages = [page_html(p, f"Italiano · Day {n} · page {i} of {total} · {ATTRIBUTION_HTML}")
                    for i, p in enumerate(lesson, 1)]
    answer_pages = [page_html(p, f"Italiano · Day {n} · answer key"
                                 + (f" {i} of {len(answers)}" if len(answers) > 1 else "")
                                 + f" · {ATTRIBUTION_HTML}")
                    for i, p in enumerate(answers, 1)]
    return {"css": CSS, "lesson_pages": lesson_pages, "answer_pages": answer_pages}


CSS = """
<style>
  /* Italian (italian.py). Sized for the workbook's printed page. */
  .page.flow .frame:has(> .it-sheet) { min-height:10.1in; position:relative; }
  .it-sheet { font-size:12.5px; line-height:1.45; color:#3E302E; padding-bottom:22px; }
  .it-foot { position:absolute; left:20px; right:20px; bottom:12px; font-size:9.5px; color:#9b8b80;
             text-align:center; line-height:1.3; }
  .it-sheet p { margin:0; }
  .it-p { margin:0 0 6px !important; }
  .it-h { font-size:13.5px; font-weight:800; color:#5b4841; margin:8px 0 4px; }
  .it-daysub { font-size:13px; color:#77665f; margin:-4px 0 10px; }
  .it-today { padding:10px 16px; }
  .it-todos { margin:6px 0 6px; }
  .it-todo { display:inline-block; margin:2px 16px 2px 0; font-size:13px; white-space:nowrap; }
  .it-box { display:inline-block; width:12px; height:12px; border:1.5px solid #8a7a6f; border-radius:3px;
            margin-right:6px; vertical-align:-1px; background:#fff; }

  .it-lesson { background:#FFF8EF; border:2px solid #F2E6D9; border-radius:16px; padding:8px 16px 8px;
               margin:0 0 12px; }
  .it-lesson-label { font-family:Menlo,Monaco,monospace; font-size:9.5px; letter-spacing:0.12em;
                     text-transform:uppercase; color:#b0877a; margin-bottom:4px; }
  .it-ul { margin:2px 0 6px; padding-left:20px; }
  .it-ul li { margin-bottom:2px; }
  .it-dialog { margin:2px 0 6px; padding-left:10px; border-left:3px solid #F4C87A; }
  .it-reading { border:1.5px solid #E8D9CB; background:#fff; border-radius:10px; padding:8px 12px; margin:4px 0 8px;
                line-height:1.5; }
  .it-note { border:1.5px dashed #E3C9B4; background:#fff; border-radius:10px; padding:6px 12px 7px; margin:6px 0 8px; }
  .it-note-tip { border-color:#B9D3E6; background:#F7FBFF; }
  .it-note-t { font-family:Menlo,Monaco,monospace; font-size:9.5px; letter-spacing:0.1em; text-transform:uppercase;
               color:#a0705f; margin-bottom:2px; }
  .it-note-tip .it-note-t { color:#4F7A9A; }
  .it-cols { display:grid; gap:0 18px; }
  .it-cols-2 { grid-template-columns:1fr 1fr; }
  .it-cols-3 { grid-template-columns:1fr 1fr 1fr; }
  .it-col .it-h:first-child { margin-top:4px; }
  .it-chips { margin:1px 0 5px; line-height:1; }
  .it-sheet .chip.it-vchip { border:1.5px solid #E6CDB8; background:#fff; color:#4b3a35; font-weight:600;
                             font-size:11.5px; padding:3px 8px; margin:2px 4px 2px 0; }
  .it-vchip .it-en { font-weight:400; color:#7b6b61; }
  .it-sheet table.it-table { width:100%; border-collapse:collapse; margin:4px 0 8px; }
  .it-sheet table.it-table th { font-family:Menlo,Monaco,monospace; font-size:9.5px; text-transform:uppercase;
                                letter-spacing:0.08em; color:#9c8d7e; font-weight:400; text-align:left;
                                padding:3px 6px 4px 0; border-bottom:1.5px solid #D9C9BA; }
  .it-sheet table.it-table td { border-top:none; border-bottom:1px solid #EADCCF; padding:4px 6px 4px 0;
                                vertical-align:top; line-height:1.4; }
  .it-sheet table.it-agenda td, .it-sheet table.it-agenda th { font-size:10px; padding:3px 4px; border:1px solid #DCCCBE; }
  .it-sheet table.it-agenda td { line-height:1.35; }
  .it-tiles { display:grid; grid-template-columns:repeat(7, 1fr); gap:6px; margin:4px 0 8px; }
  .it-tile { border:1.5px solid #E6CDB8; border-radius:8px; background:#fff; text-align:center; padding:3px 2px; }
  .it-tile b { display:block; font-size:14px; color:#E56D5C; letter-spacing:0.05em; }
  .it-tile span { font-size:11px; color:#5b4841; }
  .it-nums { display:grid; grid-template-columns:repeat(5, 1fr); gap:2px 10px; margin:4px 0 8px; font-size:12px; }
  .it-num b { display:inline-block; min-width:28px; color:#E56D5C; }
  .it-clockrow { display:grid; grid-template-columns:repeat(6, 1fr); gap:6px; margin:6px 0 8px; text-align:center; }
  .it-clock-time { font-family:Menlo,Monaco,monospace; font-size:11px; color:#7b6b61; }
  .it-clock-cap { font-size:11px; line-height:1.3; color:#4b3a35; }
  .it-story { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin:4px 0 8px; }
  .it-frame { border:1.5px solid #E6D6C7; background:#fff; border-radius:8px; padding:5px 8px; font-size:12px;
              line-height:1.42; }
  .it-frame .it-en { font-size:10.5px; color:#857469; line-height:1.38; margin-top:2px; }

  .it-ex-head { display:flex; gap:9px; align-items:flex-start; margin:12px 0 6px; }
  .it-letter { flex:0 0 22px; height:22px; border:2px solid #E56D5C; border-radius:50%; color:#E56D5C;
               font-weight:800; font-size:12px; display:inline-flex; align-items:center; justify-content:center;
               margin-top:1px; }
  .it-ex-title { font-family:Georgia,'Times New Roman',serif; font-style:italic; font-weight:700; font-size:15.5px;
                 color:#4b3a35; line-height:1.25; }
  .it-ex-instr { font-size:11.5px; color:#7a665b; line-height:1.4; }
  .it-say { font-size:11px; font-style:italic; color:#9a877b; margin:-2px 0 4px 31px; }
  .it-intro { margin:2px 0 6px 31px; }
  .it-item { display:flex; margin:0 0 7px 31px; line-height:25px; }
  .it-2col { display:grid; grid-auto-flow:column; grid-template-columns:1fr 1fr; column-gap:16px; margin-left:31px; }
  .it-2col .it-item { margin-left:0; }
  .it-n { flex:0 0 24px; color:#7a665b; }
  .it-body { flex:1; }
  .it-opts { white-space:normal; }
  .it-sheet .chip.it-opt { border:1.5px solid #BFAFA2; border-style:solid; background:#fff; color:#3E302E;
                           font-weight:500; font-size:11.5px; padding:2px 9px; margin:0 3px 0 0; line-height:1.3;
                           white-space:nowrap; }
  .it-blank { display:inline-block; border-bottom:1.5px solid #6b5a50; height:17px; vertical-align:baseline;
              margin:0 2px; }
  .it-sup { font-size:9px; color:#9a877b; margin-left:2px; }
  .it-para { margin:0 0 10px 31px; line-height:31px; }
  .it-prompt { margin:4px 0 2px 31px; font-weight:700; color:#5b4841; }
  .it-lines { margin:0 0 6px 31px; }
  .it-line { border-bottom:1.5px dashed #CFC2B6; height:30px; }
  .it-sheet table.it-conj { width:calc(100% - 31px); margin:4px 0 10px 31px; border-collapse:collapse; }
  .it-sheet table.it-conj th { font-family:Georgia,'Times New Roman',serif; font-size:13px; text-transform:none;
                               letter-spacing:0; color:#4b3a35; padding:2px 6px; text-align:left; }
  .it-sheet table.it-conj td { border:1.5px solid #CDBDB0; height:31px; padding:2px 8px; }
  .it-sheet table.it-conj td.it-person { border:none; width:90px; color:#7a665b; font-size:12px; }
  .it-sheet table.it-conj td.it-given { color:#7a665b; font-style:italic; }
  .it-match { display:grid; grid-template-columns:1fr 1fr; gap:4px 20px; margin:2px 0 8px 31px; line-height:1.5; }
  .it-match-l, .it-match-r { padding:3px 0; }
  .it-match-l .it-n { display:inline-block; width:22px; }
  .it-match-r b { display:inline-block; width:18px; color:#E56D5C; }
  .it-check { list-style:none; padding:0; margin:2px 0 6px 31px; columns:2; column-gap:20px; }
  .it-check li { break-inside:avoid; margin-bottom:5px; padding-left:20px; text-indent:-20px; }
  .it-tally { margin:4px 0 6px 31px; font-weight:700; color:#5b4841; }
  .it-clockgrid { display:grid; grid-template-columns:repeat(4, 1fr); gap:8px 14px; margin:4px 0 8px 31px;
                  text-align:center; }
  .it-clockq { position:relative; }
  .it-clockq-n { position:absolute; left:0; top:0; font-weight:800; color:#E56D5C; }
  .it-clockq .it-line { height:26px; }
  .it-tris { display:flex; gap:14px; align-items:center; margin:2px 0 8px 31px; }
  .it-tris-board { display:grid; grid-template-columns:repeat(3, 40px); grid-template-rows:repeat(3, 40px); }
  .it-tris-cell { border:1.5px solid #8a7a6f; font-size:9px; color:#9a877b; padding:2px 3px; }
  .it-bingo { display:flex; gap:22px; margin:4px 0 10px 31px; align-items:flex-start; }
  .it-sheet table.it-bingo-card { width:auto; border-collapse:collapse; }
  .it-sheet table.it-bingo-card td { width:40px; height:36px; border:1.5px solid #8a7a6f; text-align:center;
                                     font-weight:700; font-size:14px; padding:0; }
  .it-sheet table.it-bingo-card td.it-free { color:#E56D5C; }
  .it-calls { columns:2; column-gap:22px; margin:2px 0 0; padding-left:22px; font-size:12px; line-height:1.55; }
  .it-review ul.it-goals, .it-goals { list-style:none; padding:0; margin:6px 0 0; }
  .it-goals li { margin-bottom:4px; }
  .it-stopline { display:flex; gap:8px; align-items:flex-end; margin-top:6px; }
  .it-stopline .it-line { flex:1; }

  .it-vgroup { margin-bottom:10px; }
  .it-vcols { column-gap:18px; }
  .it-vcols-3 { columns:3; }
  .it-vcols-2 { columns:2; }
  .it-vrow { break-inside:avoid; display:flex; justify-content:space-between; gap:8px; font-size:11.5px;
             line-height:1.35; padding:2px 0; border-bottom:1px dashed #DCCDBF; }
  .it-vrow b { color:#3E302E; }
  .it-vrow span { color:#6b5a50; text-align:right; }

  .it-ans { margin:0 0 8px; font-size:12px; line-height:1.42; }
  .it-ans-h { color:#5b4841; }
  .it-ans-h i { color:#7a665b; }
  .it-ans-b b { color:#4b3a35; }

  @media print {
    .page.flow .frame:has(> .it-sheet) { min-height:9.86in !important; }
  }
</style>
"""


# ── Command line ─────────────────────────────────────────────────────────────

def standalone_html(pages: list[str], css: str, title: str = "Italiano") -> str:
    """A printable page with the workbook's styles (falls back to the Italian CSS alone)."""
    styles = ""
    try:
        sys.path.insert(0, str(HERE / "workbooks"))
        import dailyWorkbookLocal  # noqa: E402
        styles = dailyWorkbookLocal.STYLES
    except Exception:  # pragma: no cover - only for previews
        styles = ("<style>body{margin:0;font-family:Avenir,Helvetica,Arial,sans-serif;background:#fffdf9}"
                  ".page{width:8.5in;padding:.45in;page-break-after:always}.frame{border:3px dashed #f0d9c7;"
                  "border-radius:24px;padding:18px 20px;display:flex;flex-direction:column}"
                  "@page{size:Letter;margin:.25in}</style>")
    return ("<!DOCTYPE html><html lang='it'><head><meta charset='UTF-8'>"
            f"<title>{esc(title)}</title>{styles}{css}</head><body>{''.join(pages)}</body></html>")


def _print_day(ds: dict) -> None:
    if ds.get("done"):
        print(f"All {ds['total_days']} days of {ds['title']} have been printed.")
        return
    print(f"Italiano day {ds['day']} of {ds['total_days']} ({ds['date']}): sections {', '.join(ds['section_ids'])}"
          f" · {ds['exercise_count']} exercises · about {ds['minutes']} minutes")
    for s in ds["sections"]:
        print(f"  {s['id']} {_plain(s['title'])} — {_plain(s['subtitle'])} ({len(s['exercises'])} exercises)")
    if ds["vocab"]:
        print("  vocabulary: " + ", ".join(f"{g['group']} ({len(g['items'])})" for g in ds["vocab"]))
    for r in ds["review"]:
        print(f"  + Ripasso: Capitolo {r['chapter']}")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "today"
    if cmd == "today":
        _print_day(daily_set(mark=False))
    elif cmd == "plan":
        course = load_course()
        for p in plan_days(course):
            ds = day_set_for(p["day"], course=course)
            print(f"Day {p['day']}: {', '.join(p['section_ids'])} · {p['exercise_count']} exercises"
                  + (f" · finishes chapter {', '.join(map(str, p['finishes_chapters']))}" if p["finishes_chapters"] else "")
                  + f"\n        vocab: {', '.join(g['group'] for g in ds['vocab']) or '—'}")
    elif cmd == "status":
        by_date = load_progress()["by_date"]
        total = len(plan_days())
        print(f"{len(set(by_date.values()))} of {total} days printed")
        for d, n in sorted(by_date.items()):
            print(f"  {d}: day {n}")
    elif cmd == "preview":
        n = int(argv[1]) if len(argv) > 1 else 1
        out = Path(argv[2]) if len(argv) > 2 else Path(f"italian-day-{n}.html")
        r = render(day_set_for(n))
        out.write_text(standalone_html(r["lesson_pages"] + r["answer_pages"], r["css"], f"Italiano day {n}"),
                       encoding="utf-8")
        print(f"wrote {out} ({len(r['lesson_pages'])} lesson pages, {len(r['answer_pages'])} answer pages)")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
