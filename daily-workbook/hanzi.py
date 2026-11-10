#!/usr/bin/env python3
"""Stroke order and writing grids for the Chinese pages.

Stroke data comes from the hanzi-writer-data package (derived from the Make Me
a Hanzi project, Arphic Public License). Download it once while online:

    python3 hanzi.py fetch          # every character in the workbook's HSK 1 list

After that everything renders offline from hanzi_data/<char>.json. If a
character has no data, the workbook falls back to a plain big character.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "hanzi_data"
CDN = "https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/{}.json"

# Hanzi Writer's coordinate system: a 1024 box with y pointing up, baseline at 900.
_FLIP = 'transform="translate(0,900) scale(1,-1)"'
GRID_COLOR = "#F2B9B3"
INK = "#3c3c3c"
TRACE = "#E3E3E3"
ACCENT = "#E56D5C"


def load(char: str) -> dict | None:
    try:
        return json.loads((DATA_DIR / f"{char}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def fetch(chars) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    todo = [c for c in dict.fromkeys(chars) if not (DATA_DIR / f"{c}.json").exists()]
    print(f"{len(todo)} characters to download")
    for c in todo:
        try:
            url = CDN.format(urllib.parse.quote(c))
            req = urllib.request.Request(url, headers={"User-Agent": "DailyWorkbook/1.0"})
            data = urllib.request.urlopen(req, timeout=20).read()
            json.loads(data)
            (DATA_DIR / f"{c}.json").write_bytes(data)
            print(f"✓ {c}")
        except Exception as e:
            print(f"⚠ {c}: {e}")
        time.sleep(0.2)


def _grid(size: float) -> str:
    """田字格 guides: outer square, dashed center cross and diagonals."""
    s = 1024
    return (f'<rect x="8" y="8" width="{s-16}" height="{s-16}" rx="40" fill="white" stroke="{GRID_COLOR}" stroke-width="16"/>'
            f'<g stroke="{GRID_COLOR}" stroke-width="7" stroke-dasharray="30 26" opacity="0.8">'
            f'<line x1="512" y1="24" x2="512" y2="1000"/><line x1="24" y1="512" x2="1000" y2="512"/>'
            f'<line x1="40" y1="40" x2="984" y2="984" opacity="0.45"/><line x1="984" y1="40" x2="40" y2="984" opacity="0.45"/></g>')


def box(char: str | None = None, size_in: float = 0.72, mode: str = "empty") -> str:
    """One practice square. mode: 'empty', 'trace' (light gray to write over) or 'model' (dark)."""
    inner = ""
    data = load(char) if char else None
    if char and mode != "empty":
        color = INK if mode == "model" else TRACE
        if data:
            inner = f'<g {_FLIP}>' + "".join(f'<path d="{p}" fill="{color}"/>' for p in data["strokes"]) + "</g>"
        else:
            inner = (f'<text x="512" y="800" font-size="760" text-anchor="middle" fill="{color}" '
                     f'font-family="PingFang SC, Heiti SC, sans-serif">{char}</text>')
    return (f'<svg class="tzg" viewBox="0 0 1024 1024" width="{size_in}in" height="{size_in}in" '
            f'xmlns="http://www.w3.org/2000/svg">{_grid(size_in)}{inner}</svg>')


def stroke_order(char: str, size_in: float = 0.46) -> str:
    """A strip of small boxes building the character one stroke at a time.

    Earlier strokes are dark, the new stroke is highlighted with a dot where the
    pen starts. Returns '' if there's no stroke data for the character.
    """
    data = load(char)
    if not data:
        return ""
    strokes, medians = data["strokes"], data.get("medians") or []
    cells = []
    for k in range(len(strokes)):
        paths = "".join(f'<path d="{p}" fill="{INK if i < k else "#D9D9D9"}"/>' for i, p in enumerate(strokes) if i != k)
        paths += f'<path d="{strokes[k]}" fill="{ACCENT}"/>'
        dot = ""
        if k < len(medians) and medians[k]:
            x, y = medians[k][0]
            dot = f'<circle cx="{x}" cy="{y}" r="46" fill="white" stroke="{ACCENT}" stroke-width="18"/>'
        cells.append(
            f'<div class="so-cell"><svg viewBox="0 0 1024 1024" width="{size_in}in" height="{size_in}in" xmlns="http://www.w3.org/2000/svg">'
            f'{_grid(size_in)}<g {_FLIP}>{paths}{dot}</g></svg><div class="so-num">{k + 1}</div></div>')
    return f'<div class="so-strip">{"".join(cells)}</div>'


def stroke_count(char: str) -> int | None:
    data = load(char)
    return len(data["strokes"]) if data else None


def manuscript(rows: int = 3, cols: int = 12, size_in: float = 0.5) -> str:
    """Rows of joined writing squares (like Chinese manuscript paper) for copying sentences."""
    row = "".join(box(None, size_in) for _ in range(cols))
    return "".join(f'<div class="ms-row">{row}</div>' for _ in range(rows))


def _hsk_chars() -> list[str]:
    sys.path.insert(0, str(HERE / "workbooks"))
    from dailyWorkbookLocal import HSK1_VOCAB
    chars = []
    for item in HSK1_VOCAB:
        for c in item["char"]:
            if "一" <= c <= "鿿":
                chars.append(c)
    return list(dict.fromkeys(chars))


if __name__ == "__main__":
    if sys.argv[1:2] == ["fetch"]:
        extra = sys.argv[2:]
        fetch(_hsk_chars() + [c for word in extra for c in word])
    else:
        print(__doc__)
