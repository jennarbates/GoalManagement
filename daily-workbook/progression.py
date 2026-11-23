"""Which workbook comes next.

Workbooks are numbered (1, 2, 3, ...) instead of dated: each one picks up
where the last one stopped, whenever you get to it. The number of the last
workbook built lives in workbook_progress.json; the next one is that plus one.

    python3 progression.py        # the next workbook's number
"""
from __future__ import annotations

import json
from pathlib import Path

PROGRESS_FILE = Path(__file__).resolve().parent / "workbook_progress.json"


def last_built() -> int:
    try:
        return max(0, int(json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))["last_built"]))
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return 0


def next_number() -> int:
    return last_built() + 1


def mark_built(n: int) -> None:
    """Record that workbook n exists (rebuilding an earlier one changes nothing)."""
    if n > last_built():
        PROGRESS_FILE.write_text(json.dumps({"last_built": n}, indent=2) + "\n", encoding="utf-8")


def label(n: int) -> str:
    """Zero-padded number used in file names: 7 -> '007'."""
    return f"{n:03d}"


if __name__ == "__main__":
    print(f"Next workbook: {next_number()}")
