"""CS311 (Algorithms, UMass, Kleinberg & Tardos) daily practice.

Each day gets one topic from the course, chosen in a shuffled order that
visits every topic before repeating one. That topic contributes 3 worked
problems (with explanations) and 3 practice problems (answers go on a
separate answer-key page). Problems live in cs311_problems.json, so add more
there at any time. No network, no model.
"""
from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

PROBLEMS_FILE = Path(__file__).resolve().parent / "cs311_problems.json"
COURSE_NAME = "CS311 Algorithms"
_SHUFFLE_SEED = 311


def load_topics() -> list[dict]:
    return json.loads(PROBLEMS_FILE.read_text(encoding="utf-8"))["topics"]


def topic_for(day: date | None = None) -> dict:
    """The topic for a given day. Every topic comes up once per cycle."""
    day = day or date.today()
    topics = load_topics()
    cycle, pos = divmod(day.toordinal(), len(topics))
    order = _cycle_order(len(topics), cycle)
    # Don't repeat a topic across the boundary between two cycles.
    if len(topics) > 1 and order[0] == _cycle_order(len(topics), cycle - 1)[-1]:
        order[0], order[1] = order[1], order[0]
    return topics[order[pos]]


def _cycle_order(n: int, cycle: int) -> list[int]:
    order = list(range(n))
    random.Random(_SHUFFLE_SEED + cycle).shuffle(order)
    return order


def _pick(items: list, n: int, day: date, salt: str) -> list:
    if len(items) <= n:
        return list(items)
    return random.Random(f"{day.isoformat()}-{salt}").sample(items, n)


def daily_set(day: date | None = None) -> dict:
    """Today's topic plus 3 worked and 3 practice problems."""
    day = day or date.today()
    t = topic_for(day)
    return {
        "course": COURSE_NAME,
        "topic": t["name"],
        "chapter": t.get("chapter", ""),
        "lectures": t.get("lectures", ""),
        "worked": _pick(t.get("problems", []), 3, day, "worked"),
        "practice": _pick(t.get("practice", []), 3, day, "practice"),
    }


if __name__ == "__main__":
    s = daily_set()
    print(f"{s['course']}: {s['topic']} ({s['chapter']}, {s['lectures']})")
    for p in s["worked"]:
        print("  worked:  ", p["title"])
    for i, p in enumerate(s["practice"], 1):
        print(f"  practice {i}:", p["problem"][:70])
