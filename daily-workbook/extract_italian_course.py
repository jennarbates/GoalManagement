#!/usr/bin/env python3
"""Rebuild italian_course.json from the parlaplay Quaderno.

The source is the self-contained interactive workbook

    ../../parlaplay/quaderno/index.html   (or ../../parlaplay-quaderno/..., whichever
                                          copy has the most chapters; chapters 1-6 so far)
    "Tutt* a tavola! Quaderno", Volume 1, adapted from
    Tutt* a tavola! Volume 1 by Stacy Giufre and Melina Masterson, CC BY-NC 4.0.

Its content is a JS literal (`const CHAPTERS = [...]`). Node evaluates the
content part of the script (with the browser bits stubbed out) and hands the
data back as JSON; this script then turns the lesson HTML into structured
blocks and the exercises into printable ones. Interactive widgets that work on
paper are converted with fixed, repeatable items (see WIDGET_* below).

    python3 extract_italian_course.py                 # writes italian_course.json
    python3 extract_italian_course.py --source PATH   # another copy of index.html
    python3 extract_italian_course.py --check         # rebuild in memory and compare counts only

Needs `node` on PATH. Standard library only otherwise. The source is only read.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV_DIR = HERE.parent.parent
# The Quaderno checkouts, in order of preference when they have the same chapters.
# (Chapters 4-6 landed on the parlaplay-quaderno checkout before main parlaplay.)
SOURCE_CANDIDATES = [DEV_DIR / d / "quaderno" / "index.html" for d in ("parlaplay", "parlaplay-quaderno")]


def _chapter_count(path: Path) -> int:
    return len(re.findall(r'\bid: "c\d+"', path.read_text(encoding="utf-8"))) if path.exists() else -1


def default_source() -> Path:
    """The Quaderno copy with the most chapters (ties go to the earlier candidate)."""
    return max(SOURCE_CANDIDATES, key=lambda p: (_chapter_count(p), -SOURCE_CANDIDATES.index(p)))


DEFAULT_SOURCE = default_source()
OUT_FILE = HERE / "italian_course.json"

ATTRIBUTION = ("Adapted from Tutt* a tavola! Volume 1 by Stacy Giufre and Melina Masterson, "
               "CC BY-NC 4.0")
BOOK_URL = "https://openbooks.library.umass.edu/tutt-a-tavola-vol-1/"

# ── Fixed items for widgets that are random drills on screen ─────────────────
# (These match the dates, times and dice rolls of the earlier printed days.)
WIDGET_DATES = [(3, 5), (1, 2), (8, 3), (11, 6), (22, 7), (15, 8), (30, 9), (25, 12), (4, 4), (1, 10)]
WIDGET_CLOCKS = [(9, 15), (14, 30), (1, 0), (12, 0), (20, 45), (6, 50), (17, 10), (23, 35)]
WIDGET_DICE = [("io", "parlare"), ("noi", "giocare"), ("tu", "cercare"), ("voi", "leggere"),
               ("lui/lei", "finire"), ("loro", "preferire"), ("tu", "mangiare"), ("noi", "viaggiare"),
               ("lui/lei", "dormire"), ("loro", "cominciare"), ("io", "capire"), ("voi", "pagare")]
WIDGET_NUM_TO_WORDS = [17, 21, 38, 43, 66, 100]
WIDGET_WORDS_TO_NUM = [13, 28, 51, 74, 99, 0]
WIDGET_PHONES = ["3398172645", "2064759183", "6175550142"]
# Tris: which question of each square's pool to print, in board order.
WIDGET_TRIS_PICK = [0, 0, 0, 0, 1, 0, 1, 2, 0]
WIDGET_SPELL_MODEL = "Valentina"
# Lavagna: every third word of the widget's list (12 of 36).
WIDGET_LAVAGNA_STEP = 3

# Screen-only wording, reworded for paper.
PRINT_REWRITES = {
    "The Italian alphabet has 21 letters. Tap a tile to hear its name.":
        "The Italian alphabet has 21 letters. Say each letter’s name out loud.",
    "The consulate clerk spells names back to you. Write the name you hear.":
        "The consulate clerk spells names back to you. Write each name.",
    "Based on your device’s date. Write the days in Italian.":
        "Write the days in Italian, based on the day you’re doing this.",
}

PERSON_INDEX = {"io": 0, "tu": 1, "lui/lei": 2, "lui/lei/Lei": 2, "noi": 3, "voi": 4, "loro": 5}

# ── Node: evaluate the content part of the page ──────────────────────────────

NODE_JS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.env.QUADERNO, 'utf8');
const req = JSON.parse(process.env.QREQ);
const lines = src.split('\n');
const start = lines.findIndex(l => l.trim() === '<script>') + 1;
const end = lines.findIndex(l => l.includes('/* ---------- progress ---------- */'));
if (start <= 0 || end < 0) throw new Error('could not find the CHAPTERS script block');
let code = lines.slice(start, end).join('\n');
// "Oggi e domani" answers depend on today's weekday: keep them symbolic.
code = code.replace(/DAYS_JS\[\(?dIdx(?: \+ (\d)\) % 7)?\]/g, (m, n) => JSON.stringify('@weekday+' + (n || 0)));
const stub = `const window = {}; const document = {addEventListener(){}, documentElement:{classList:{add(){}}},
  querySelector(){return null}, createElement(){return {}}}; const localStorage = {getItem(){return null}, setItem(){}};`;
const R = new Function(stub + code +
  '\nreturn {CHAPTERS, PRON, LETTERS, MONTHS, DAYS_JS, numToIt, dateAnswers, timeAnswers, conj};')();

// Literal data inside the widget code (after the content block).
function literal(after, marker) {
  const i = src.indexOf(after);
  if (i < 0) throw new Error('missing ' + after);
  const j = src.indexOf(marker, i);
  if (j < 0) throw new Error('missing ' + marker + ' after ' + after);
  let k = j + marker.length - 1, depth = 0, q = null;
  const open = src[k], close = open === '[' ? ']' : '}';
  for (let p = k; p < src.length; p++) {
    const c = src[p];
    if (q) { if (c === '\\') { p++; continue; } if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === '`') { q = c; continue; }
    if (c === '[' || c === '{') depth++;
    if (c === ']' || c === '}') { depth--; if (depth === 0) return new Function('return ' + src.slice(k, p + 1))(); }
  }
  throw new Error('unbalanced literal ' + marker);
}

const out = {
  chapters: R.CHAPTERS,
  pron: R.PRON,
  letters: R.LETTERS,
  months: R.MONTHS,
  numwords: Object.fromEntries([...Array(101).keys(), 1000, 2000].map(n => [n, R.numToIt(n)])),
  dates: req.dates.map(([d, m]) => R.dateAnswers(d, m - 1)),
  times: req.times.map(([h, m]) => R.timeAnswers(h, m)),
  conj: Object.fromEntries(req.verbs.map(v => [v, R.conj(v)])),
  widgets: {
    lavagna: literal('lavagna(box, id) {', 'const W = ['),
    tris_cells: literal('tris(box, id) {', 'const CELLS = ['),
    tris_basic: literal('tris(box, id) {', 'const BASIC = ['),
    tris_q: literal('tris(box, id) {', 'const Q = {'),
    etu: literal('etu(box, id) {', 'const L = ['),
  },
};
process.stdout.write(JSON.stringify(out));
"""


def run_node(source: Path) -> dict:
    req = {"dates": WIDGET_DATES, "times": WIDGET_CLOCKS, "verbs": sorted({v for _, v in WIDGET_DICE})}
    env = dict(os.environ, QUADERNO=str(source), QREQ=json.dumps(req))
    res = subprocess.run(["node", "-e", NODE_JS], capture_output=True, text=True, env=env)
    if res.returncode != 0:
        sys.exit("node failed:\n" + res.stderr)
    return json.loads(res.stdout)


# ── A tiny DOM for the lesson HTML ───────────────────────────────────────────

VOID = {"br", "img", "hr", "input", "meta", "link"}


class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or {}), []

    @property
    def classes(self):
        return set((self.attrs.get("class") or "").split())


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(fragment: str) -> Node:
    b = _Builder()
    b.feed(fragment)
    b.close()
    return b.root


def text_of(n) -> str:
    if isinstance(n, str):
        return n
    if n.tag == "br":
        return "\n"
    return "".join(text_of(c) for c in n.children)


def inline(n) -> str:
    """Inline HTML limited to <b>, <i> and <br>. Links become 'text (url)'."""
    if isinstance(n, str):
        return html.escape(n, quote=False)
    kids = "".join(inline(c) for c in n.children)
    t = n.tag
    if t in ("b", "strong"):
        return f"<b>{kids}</b>" if kids.strip() else kids
    if t in ("i", "em"):
        return f"<i>{kids}</i>" if kids.strip() else kids
    if t == "br":
        return "<br>"
    if t == "a":
        href = n.attrs.get("href", "")
        return f"{kids} ({html.escape(href, quote=False)})" if href else kids
    if t == "button":
        return ""
    return kids


def clean_inline(s: str) -> str:
    s = re.sub(r"[ \t\r\n]+", " ", s)
    s = re.sub(r"\s*<br>\s*", "<br>", s)
    return s.strip()


def split_chip(n: Node) -> dict:
    raw = clean_inline(inline(n))
    if " · " in raw:
        it, en = raw.split(" · ", 1)
        return {"it": it.strip(), "en": en.strip()}
    return {"it": raw, "en": ""}


def table_block(t: Node) -> dict:
    rows = []
    for tr in _find_all(t, "tr"):
        cells = []
        for c in tr.children:
            if isinstance(c, Node) and c.tag in ("td", "th"):
                cell = {"html": clean_inline(inline(c))}
                if c.tag == "th":
                    cell["th"] = True
                for k in ("rowspan", "colspan"):
                    if c.attrs.get(k):
                        cell[k] = int(c.attrs[k])
                cells.append(cell)
        rows.append(cells)
    head = None
    if rows and all(c.get("th") for c in rows[0]):
        head = rows.pop(0)

    def simplify(cells):
        out = []
        for c in cells:
            c.pop("th", None)
            out.append(c["html"] if len(c) == 1 else c)
        return out

    block = {"type": "table", "head": simplify(head) if head else None, "rows": [simplify(r) for r in rows]}
    if "agenda" in t.classes:
        block["variant"] = "agenda"
    return block


def _find_all(n: Node, tag: str):
    for c in n.children:
        if isinstance(c, Node):
            if c.tag == tag:
                yield c
            else:
                yield from _find_all(c, tag)


def blocks_of(n: Node, ctx: dict) -> list[dict]:
    """Walk block-level children of n."""
    out: list[dict] = []
    pending_inline: list = []

    def flush():
        if pending_inline:
            s = clean_inline("".join(inline(x) for x in pending_inline))
            if s:
                out.append({"type": "p", "html": s})
            pending_inline.clear()

    for c in n.children:
        if isinstance(c, str) or c.tag in ("b", "i", "span", "a", "br", "em", "strong"):
            if isinstance(c, Node) and c.tag == "span" and "chip" in c.classes:
                flush()
                out.append({"type": "chips", "items": [split_chip(c)]})
                continue
            pending_inline.append(c)
            continue
        flush()
        out.extend(block_of(c, ctx))
    flush()
    return out


def block_of(c: Node, ctx: dict) -> list[dict]:
    cls = c.classes
    t = c.tag
    if t == "button":
        ctx["skipped"].add("screen-only buttons (show/hide English, listen)")
        return []
    if t == "p":
        s = clean_inline(inline(c))
        if not s:
            return []
        if "say" in cls:
            return [{"type": "reading", "html": s}]
        return [{"type": "p", "html": s}]
    if t in ("h3", "h4", "h5"):
        return [{"type": "heading", "html": clean_inline(inline(c))}]
    if t in ("ul", "ol"):
        return [{"type": "list", "ordered": t == "ol",
                 "items": [clean_inline(inline(li)) for li in c.children if isinstance(li, Node) and li.tag == "li"]}]
    if t == "table":
        return [table_block(c)]
    if t == "div":
        if "tscroll" in cls:
            return [table_block(tb) for tb in _find_all(c, "table")]
        if "chips" in cls:
            return [{"type": "chips", "items": [split_chip(x) for x in c.children
                                                 if isinstance(x, Node) and "chip" in x.classes]}]
        if "note" in cls or "tip" in cls:
            kids = [x for x in c.children if not (isinstance(x, str) and not x.strip())]
            title = ""
            if kids and isinstance(kids[0], Node) and kids[0].tag == "b":
                title = clean_inline(text_of(kids[0]))
                kids = kids[1:]
            holder = Node("div")
            holder.children = kids
            return [{"type": "note", "kind": "tip" if "tip" in cls else "note",
                     "title": title or ("Study tip" if "tip" in cls else "Nota culturale"),
                     "blocks": blocks_of(holder, ctx)}]
        if "cols" in cls:
            return [{"type": "columns", "columns": [blocks_of(x, ctx) for x in c.children if isinstance(x, Node)]}]
        if "dialog" in cls:
            return [{"type": "dialog", "lines": [clean_inline(inline(x)) for x in c.children if isinstance(x, Node)]}]
        if "tiles" in cls:
            letters = c.attrs.get("data-letters", "")
            ctx["skipped"].add("audio for letter tiles (printed as a letter/name table)")
            return [{"type": "letters", "items": [{"letter": l, "name": ctx["letters"][l]} for l in letters]}]
        if "numgrid" in cls:
            spec = c.attrs.get("data-nums", "")
            nums = [30, 40, 50, 60, 70, 80, 90, 100, 1000, 2000] if spec == "tens" else list(range(21))
            return [{"type": "numbers", "items": [{"n": n, "word": ctx["numwords"][str(n)]} for n in nums]}]
        if "clockrow" in cls:
            items = []
            for s in c.attrs.get("data-clocks", "").split(";"):
                tm, cap = s.split("|")
                h_, m_ = (int(x) for x in tm.split(":"))
                items.append({"h": h_, "m": m_, "label": cap})
            return [{"type": "clocks", "items": items}]
        if "strip" in cls:
            lines = []
            for fr in c.children:
                if isinstance(fr, Node) and "frame" in fr.classes:
                    en = "".join(text_of(x) for x in fr.children if isinstance(x, Node) and "en" in x.classes)
                    it = "".join(inline(x) for x in fr.children if not (isinstance(x, Node) and "en" in x.classes))
                    lines.append({"it": clean_inline(it), "en": clean_inline(html.escape(en, quote=False))})
            return [{"type": "story", "lines": lines}]
        return blocks_of(c, ctx)
    return blocks_of(c, ctx)


def merge_heading_into_story(blocks: list[dict]) -> list[dict]:
    """A heading right before a story strip becomes the story's title."""
    out = []
    for b in blocks:
        if b["type"] == "story" and out and out[-1]["type"] == "heading":
            b = {"type": "story", "title": out.pop()["html"], "lines": b["lines"]}
        out.append(b)
    return out


def lesson_blocks(fragment: str, ctx: dict) -> list[dict]:
    return merge_heading_into_story(blocks_of(parse(fragment), ctx))


# ── Exercises ────────────────────────────────────────────────────────────────

def frag_inline(s: str) -> str:
    return clean_inline(inline(parse(s)))


def cloze_parts(q: str) -> list:
    parts = []
    for p in re.split(r"(\{\{.+?\}\})", q):
        if not p:
            continue
        if p.startswith("{{"):
            parts.append({"blank": p[2:-2].split("|")})
        else:
            # keep line breaks of dialogues as <br>
            # keep the spaces around blanks, and dialogue line breaks as <br>
            t = inline(parse(p.replace("\n", "<br>")))
            t = re.sub(r"[ \t\r\n]+", " ", t)
            t = re.sub(r" ?<br> ?", "<br>", t)
            parts.append(t)
    if parts and isinstance(parts[0], str):
        parts[0] = parts[0].lstrip()
    if parts and isinstance(parts[-1], str):
        parts[-1] = parts[-1].rstrip()
    return [p for p in parts if p != ""]


def match_order(pairs: list, salt: str) -> list[int]:
    """Deterministic shuffle of the right column (never the identity)."""
    idx = list(range(len(pairs)))
    rng = random.Random("match:" + salt)
    for _ in range(50):
        rng.shuffle(idx)
        if all(i != j for j, i in enumerate(idx)) or len(idx) < 2:
            break
    return idx


def convert_exercise(ex: dict, sec_no: str, ctx: dict) -> dict | None:
    base = {"title": frag_inline(ex.get("title", "")), "instructions": frag_inline(ex.get("en", ""))}
    if ex.get("intro"):
        base["intro"] = lesson_blocks(ex["intro"], ctx)
    t = ex["type"]
    if t == "choice":
        items = []
        for it in ex["items"]:
            item = {"prompt": frag_inline(it["q"]), "options": list(it.get("opts") or ex.get("opts")),
                    "answer": it["a"]}
            if it.get("why"):
                item["why"] = frag_inline(it["why"])
            assert item["answer"] in item["options"], (sec_no, it)
            items.append(item)
        return {"type": "choice", **base, "items": items}
    if t == "fill":
        items = []
        for it in ex["items"]:
            if it.get("a"):
                items.append({"parts": [frag_inline(it["q"]), {"blank": list(it["a"])}]})
            else:
                items.append({"parts": cloze_parts(it["q"])})
        return {"type": "fill", **base, "paragraph": bool(ex.get("para")), "items": items}
    if t == "free":
        return {"type": "open", **base, "prompts": [frag_inline(p) for p in ex["prompts"]],
                "example": ex.get("model", "")}
    if t == "conj":
        return {"type": "conjugation", **base, "persons": ctx["pron"],
                "verbs": [{"infinitive": v["inf"], "forms": v["forms"], "given": v.get("given", [])}
                          for v in ex["verbs"]]}
    if t == "match":
        pairs = [[frag_inline(l), frag_inline(r)] for l, r in ex["pairs"]]
        return {"type": "match", **base, "pairs": pairs, "right_order": match_order(pairs, sec_no + base["title"])}
    if t == "widget":
        return convert_widget(ex["widget"], base, sec_no, ctx)
    raise ValueError(f"unknown exercise type {t} in {sec_no}")


def convert_widget(w: str, base: dict, sec_no: str, ctx: dict) -> dict | None:
    words = ctx["numwords"]
    W = ctx["widgets"]
    note = "Paper version of an interactive exercise."
    if w == "spell":
        name = WIDGET_SPELL_MODEL
        spelled = " – ".join(ctx["letters"][ch] for ch in name.lower())
        return {"type": "open", "from_widget": w, "note": note, "title": base["title"],
                "instructions": "Write your first and last name, then spell each one letter by letter in Italian. "
                                "Say it out loud as you write.",
                "prompts": ["Mi chiamo… Si scrive…"],
                "example": f"Mi chiamo {name}. Si scrive: {spelled}."}
    if w == "numbers":
        items = [{"parts": [f"{n} →", {"blank": [words[str(n)]]}]} for n in WIDGET_NUM_TO_WORDS]
        items += [{"parts": [f"{words[str(n)]} →", {"blank": [str(n)]}]} for n in WIDGET_WORDS_TO_NUM]
        return {"type": "fill", "from_widget": w, "note": note, "title": base["title"],
                "instructions": "Numbers from 0 to 100. Write the first six in words and the last six in digits.",
                "paragraph": False, "items": items}
    if w == "phone":
        items = []
        for num in WIDGET_PHONES:
            spoken = " – ".join(words[d] for d in num)
            items.append({"parts": [f"Il mio numero di telefono è {spoken} →", {"blank": [num]}]})
        return {"type": "fill", "from_widget": w, "note": note, "title": base["title"],
                "instructions": "A classmate reads you their number. Write it in digits.",
                "paragraph": False, "items": items}
    if w == "tombola":
        return tombola_exercise(base, words)
    if w == "lavagna":
        arts = ["il", "lo", "l’", "la", "i", "gli", "le"]
        items = [{"prompt": f"___ {word}", "options": arts, "answer": art}
                 for art, word in W["lavagna"][::WIDGET_LAVAGNA_STEP]]
        return {"type": "choice", "from_widget": w, "note": note, "title": base["title"],
                "instructions": "Which definite article? Circle it, then say the article and noun aloud.",
                "items": items}
    if w == "dates":
        items = []
        for (d, m), answers in zip(WIDGET_DATES, ctx["dates"]):
            words_first = [a for a in answers if not re.search(r"\d", a)][:1]
            digits = [a for a in answers if re.search(r"\d", a)]
            # prefer "il 1° gennaio" over "il 1 gennaio" when both exist
            digit = next((a for a in digits if "°" in a), digits[0] if digits else None)
            alts = words_first + ([digit] if digit else []) + [a for a in answers if a not in words_first and a != digit]
            items.append({"parts": [f"{d}/{m} →", {"blank": alts}]})
        return {"type": "fill", "from_widget": w, "note": note, "title": base["title"],
                "instructions": "Write each date in Italian (day/month). Numbers or words are both fine.",
                "paragraph": False, "items": items}
    if w == "clock":
        items = []
        for (h_, m_), answers in zip(WIDGET_CLOCKS, ctx["times"]):
            part = ("di notte" if h_ < 6 else "di mattina" if h_ < 12 else "del pomeriggio" if h_ < 18 else "di sera")
            if (h_, m_) == (12, 0):
                part = "a mezzogiorno"
            items.append({"h": h_, "m": m_, "part": part, "answers": prefer_full_phrases(answers)})
        return {"type": "clock", "from_widget": w, "note": note, "title": "L’orologio",
                "instructions": "Che ore sono? Write each time as a full phrase. Any correct version counts: "
                                "12-hour, 24-hour, e or meno.", "items": items}
    if w == "dice":
        items = []
        for person, verb in WIDGET_DICE:
            en = ctx["verb_en"].get(verb, "")
            form = ctx["conj"][verb][PERSON_INDEX[person]]
            items.append({"parts": [f"{person} + {verb}" + (f" <i>({html.escape(en)})</i>" if en else "") + " →",
                                    {"blank": [form]}]})
        return {"type": "fill", "from_widget": w, "note": note, "title": "Giochiamo con i dadi!",
                "instructions": "The dice are already rolled: 1 io, 2 tu, 3 lui/lei, 4 noi, 5 voi, 6 loro. "
                                "Write the verb form, then say a full sentence with it out loud.",
                "paragraph": False, "items": items}
    if w == "tris":
        cells, basic, Q = W["tris_cells"], W["tris_basic"], W["tris_q"]
        items = []
        for i, (cell, k) in enumerate(zip(cells, WIDGET_TRIS_PICK)):
            pool = Q[cell]
            q, a, *rest = pool[k % len(pool)]
            if rest:
                opts = list(rest[0])
            else:
                others = [b for b in basic if b != a]
                rng = random.Random(f"tris:{i}")
                opts = [a] + rng.sample(others, 3)
                rng.shuffle(opts)
            items.append({"prompt": q, "options": opts, "answer": a})
        return {"type": "choice", "from_widget": w, "note": note, "title": "Giochiamo a Tris!",
                "instructions": "Paper tic-tac-toe. Answer all nine, then check the key. Right: draw X in that "
                                "square. Wrong: draw O. Did you get three X’s in a row?",
                "board": True, "items": items}
    if w == "etu":
        return {"type": "checklist", "from_widget": w, "note": note, "title": base["title"],
                "instructions": base["instructions"], "items": list(W["etu"]),
                "tally": f"How many do you have in common with Valentina? ____ of {len(W['etu'])}"}
    ctx["skipped"].add(f"widget {w}")
    return None


def prefer_full_phrases(answers: list[str]) -> list[str]:
    full = [a for a in answers if a.startswith(("sono ", "è "))]
    return full + [a for a in answers if a not in full]


def tombola_exercise(base: dict, words: dict) -> dict:
    """A fixed bingo card plus a list of numbers called out in words."""
    rng = random.Random("tombola-1.3")
    nums = rng.sample(range(1, 101), 24)
    card = nums[:12] + [0] + nums[12:]          # 0 = free square in the middle
    rows = [card[i:i + 5] for i in range(0, 25, 5)]
    win_row = rows[2]                            # middle row: free square + 4 numbers
    winners = [n for n in win_row if n]
    others_on_card = [n for n in card if n and n not in winners]
    decoys = rng.sample([n for n in range(1, 101) if n not in card], 8)
    near = rng.sample(others_on_card, 5)
    calls = decoys[:3] + [winners[0]] + near[:2] + [decoys[3], winners[1]] + near[2:4] + \
        decoys[4:6] + [winners[2]] + [near[4], decoys[6]] + [winners[3]]
    hits = [n for n in calls if n in card]
    # Check which call first completes a line (rows, columns, diagonals; 0 is free).
    lines = [list(range(r * 5, r * 5 + 5)) for r in range(5)] + [list(range(c, 25, 5)) for c in range(5)] + \
        [[0, 6, 12, 18, 24], [4, 8, 12, 16, 20]]
    marked = {12}
    first = None
    for k, n in enumerate(calls, 1):
        if n in card:
            marked.add(card.index(n))
        if any(all(i in marked for i in ln) for ln in lines):
            first = k
            break
    assert first == len(calls), "tombola: the designed winning call isn't the first full line"
    return {"type": "bingo", "from_widget": "tombola", "note": "Paper version of an interactive exercise.",
            "title": base["title"],
            "instructions": "Italian bingo. Read each called number (they’re only in words), and if it’s on your "
                            "card, cross it out. Five in a row in any direction wins: write “Tombola!” next to the "
                            "call that wins.",
            "card": rows, "calls": [{"n": n, "word": words[str(n)]} for n in calls],
            "answer": {"hits": hits, "winning_call": len(calls),
                       "line": "the middle row (" + ", ".join(str(n) for n in winners) + " and the free square)"}}


# ── Whole course ─────────────────────────────────────────────────────────────

def _source_label(source: Path) -> str:
    try:
        return Path(source).resolve().relative_to(DEV_DIR).as_posix()
    except ValueError:
        return str(source)


def build(source: Path) -> dict:
    raw = run_node(source)
    ctx = {"letters": raw["letters"], "numwords": raw["numwords"], "pron": raw["pron"],
           "dates": raw["dates"], "times": raw["times"], "conj": raw["conj"], "widgets": raw["widgets"],
           "skipped": set(), "verb_en": {}}
    for ch in raw["chapters"]:
        for g in ch["vocab"]:
            for it, en in g["items"]:
                ctx["verb_en"].setdefault(re.sub(r" \(-isc\)$", "", it), en)

    chapters = []
    for ch in raw["chapters"]:
        sections = []
        for s in ch["sections"]:
            exs = []
            for ex in s["ex"]:
                c = convert_exercise(ex, s["no"], ctx)
                if c:
                    c["id"] = f"{s['no']}-{len(exs) + 1}"
                    exs.append(c)
            sec = {"id": s["no"], "title": frag_inline(s["title"]), "subtitle": frag_inline(s.get("en", "")),
                   "lesson": lesson_blocks(s.get("lesson", ""), ctx), "exercises": exs}
            if s.get("after"):
                sec["after"] = lesson_blocks(s["after"], ctx)
            sections.append(sec)
        chapters.append({
            "id": ch["id"], "number": ch["num"], "title": frag_inline(ch["title"]), "gloss": ch.get("gloss", ""),
            "summary": ch.get("short", ""), "goals": ch.get("goals", []),
            "vocab": [{"group": g["g"], "items": [{"it": it, "en": en} for it, en in g["items"]]}
                      for g in ch["vocab"]],
            "sections": sections,
        })

    chapters = _rewrite(chapters)
    skipped = sorted(ctx["skipped"]) + [
        "text-to-speech (dotted words and speaker buttons)",
        "on-screen checking, scores and progress sync",
        "flashcard mode for the vocabulary (printed as a list instead)",
    ]
    return {
        "title": "Tutt* a tavola! Quaderno",
        "volume": f"Volume 1, chapters 1–{len(chapters)}",
        "attribution": ATTRIBUTION,
        "book_url": BOOK_URL,
        "source_file": _source_label(source),
        "skipped": skipped,
        "source_counts": source_counts(raw),
        "counts": course_counts(chapters),
        "chapters": chapters,
    }


def _rewrite(x):
    if isinstance(x, str):
        for a, b in PRINT_REWRITES.items():
            x = x.replace(a, b)
        return x
    if isinstance(x, list):
        return [_rewrite(v) for v in x]
    if isinstance(x, dict):
        return {k: _rewrite(v) for k, v in x.items()}
    return x


def source_counts(raw: dict) -> dict:
    secs = [s for c in raw["chapters"] for s in c["sections"]]
    exs = [e for s in secs for e in s["ex"]]
    by_type: dict[str, int] = {}
    for e in exs:
        k = e["type"] + (":" + e["widget"] if e["type"] == "widget" else "")
        by_type[k] = by_type.get(k, 0) + 1
    return {"chapters": len(raw["chapters"]), "sections": len(secs), "exercises": len(exs),
            "items": sum(len(e.get("items", e.get("pairs", e.get("prompts", e.get("verbs", []))))) for e in exs),
            "vocab_items": sum(len(g["items"]) for c in raw["chapters"] for g in c["vocab"]),
            "by_type": dict(sorted(by_type.items()))}


def course_counts(chapters: list[dict]) -> dict:
    secs = [s for c in chapters for s in c["sections"]]
    exs = [e for s in secs for e in s["exercises"]]
    by_type: dict[str, int] = {}
    for e in exs:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    return {"chapters": len(chapters), "sections": len(secs), "exercises": len(exs),
            "vocab_items": sum(len(g["items"]) for c in chapters for g in c["vocab"]),
            "by_type": dict(sorted(by_type.items()))}


def check(course: dict) -> list[str]:
    """Problems found comparing the converted course with the source counts."""
    problems = []
    src, out = course["source_counts"], course["counts"]
    for k in ("chapters", "sections", "vocab_items"):
        if src[k] != out[k]:
            problems.append(f"{k}: source {src[k]}, converted {out[k]}")
    if out["exercises"] != src["exercises"]:
        problems.append(f"exercises: source {src['exercises']}, converted {out['exercises']} "
                        f"(skipped: {course['skipped']})")
    for c in course["chapters"]:
        for s in c["sections"]:
            if not s["lesson"]:
                problems.append(f"{s['id']}: empty lesson")
            for e in s["exercises"]:
                if e["type"] == "fill":
                    for it in e["items"]:
                        if not any(isinstance(p, dict) for p in it["parts"]):
                            problems.append(f"{e['id']}: fill item without a blank")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out", type=Path, default=OUT_FILE)
    ap.add_argument("--check", action="store_true", help="don't write, just report counts")
    a = ap.parse_args(argv)
    course = build(a.source)
    s, o = course["source_counts"], course["counts"]
    print(f"source:    {s['chapters']} chapters, {s['sections']} sections, {s['exercises']} exercises, "
          f"{s['vocab_items']} vocabulary items")
    print(f"           {s['by_type']}")
    print(f"converted: {o['chapters']} chapters, {o['sections']} sections, {o['exercises']} exercises, "
          f"{o['vocab_items']} vocabulary items")
    print(f"           {o['by_type']}")
    problems = check(course)
    for p in problems:
        print("  ! " + p)
    if not a.check:
        a.out.write_text(json.dumps(course, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
