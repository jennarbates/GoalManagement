#!/usr/bin/env python3
"""Daily LeetCode practice for the workbook.

How the section teaches (based on common advice for learning LeetCode):
  * Patterns first: problems come in roadmap order, grouped by pattern
    (Arrays & Hashing -> Two Pointers -> ... -> Bit Manipulation), and the first
    problem of each pattern prints a short intro to it.
  * Attempt before help: a timebox (default 25 min), then hints one at a time
    on a separate page, then the solution.
  * A fixed method on paper: UMPIRE (Understand, Match, Plan, Implement,
    Review, Evaluate).
  * Spaced repetition: problems come back after 3, 7, 14 and 30 days to
    re-solve from memory.

Settings live in leetcode_plan.json. To move up a level, change "level" (once
leetcode_bank.LEVELS has that level). Progress lives in leetcode_progress.json.

    python3 leetcode.py            # today's problem and reviews
    python3 leetcode.py status     # progress through the current level
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import leetcode_bank

HERE = Path(__file__).resolve().parent
PLAN_FILE = HERE / "leetcode_plan.json"
PROGRESS_FILE = HERE / "leetcode_progress.json"

DEFAULT_PLAN = {"level": "easy", "minutes": 25, "review_after_days": [3, 7, 14, 30]}


def load_plan() -> dict:
    plan = dict(DEFAULT_PLAN)
    try:
        plan.update(json.loads(PLAN_FILE.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if plan["level"] not in leetcode_bank.LEVELS:
        plan["level"] = "easy"
    return plan


def load_progress() -> dict:
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"by_date": {}}


def save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, indent=2), encoding="utf-8")


def _all_problems() -> dict:
    return {p["id"]: p for problems in leetcode_bank.LEVELS.values() for p in problems}


def daily_set(day: date | None = None, mark: bool = True) -> dict:
    """Today's new problem (next in roadmap order) plus any re-solves due."""
    day = day or date.today()
    key = day.isoformat()
    plan = load_plan()
    problems = leetcode_bank.LEVELS[plan["level"]]
    progress = load_progress()
    by_date = progress.setdefault("by_date", {})
    by_id = _all_problems()

    pid = by_date.get(key)
    if pid not in by_id:
        done = set(by_date.values())
        nxt = next((p for p in problems if p["id"] not in done), None)
        pid = nxt["id"] if nxt else None
        if pid and mark:
            by_date[key] = pid
            save_progress(progress)

    problem = by_id.get(pid) if pid else None
    new_pattern = False
    if problem:
        earlier = [by_id[i]["pattern"] for d, i in by_date.items() if d < key and i in by_id]
        new_pattern = problem["pattern"] not in earlier

    reviews = []
    for days_ago in plan["review_after_days"]:
        old = by_date.get((day - timedelta(days=days_ago)).isoformat())
        if old in by_id and old != pid:
            reviews.append({**by_id[old], "days_ago": days_ago})

    position = next((i for i, p in enumerate(problems, 1) if problem and p["id"] == problem["id"]), None)
    return {
        "level": plan["level"],
        "minutes": plan["minutes"],
        "problem": problem,
        "position": position,
        "total": len(problems),
        "new_pattern": new_pattern,
        "pattern_intro": leetcode_bank.PATTERNS.get(problem["pattern"], "") if problem else "",
        "reviews": reviews,
        "level_done": problem is None,
    }


def main(argv: list[str]) -> int:
    s = daily_set(mark=False)
    if argv[:1] == ["status"]:
        done = len(load_progress().get("by_date", {}))
        print(f"Level: {s['level']} | problems handed out: {done} of {s['total']}")
        return 0
    if s["level_done"]:
        print(f"All {s['total']} {s['level']} problems done. Time to move up a level.")
    else:
        p = s["problem"]
        print(f"Today ({s['level']} {s['position']}/{s['total']}): #{p['lc']} {p['title']} [{p['pattern']}]"
              + ("  <- new pattern" if s["new_pattern"] else ""))
    for r in s["reviews"]:
        print(f"  re-solve: #{r['lc']} {r['title']} (from {r['days_ago']} days ago)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
