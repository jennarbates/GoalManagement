"""CS311 (Algorithms, UMass, Kleinberg & Tardos) practice, one set per workbook.

Each workbook gets COURSE_PER_DAY questions in course order plus one random
question. A question is one worked problem (with its explanation) plus the
matching practice problem (same index in the topic's "problems" and
"practice" lists; answers go on a separate answer-key page).

  * Course order: walks every question in course order, COURSE_PER_DAY a
    workbook, starting at workbook 1 (Algorithm Analysis Q1, Q2, Q3, then
    Graphs Q1, ...) and loops back to the start when it runs out. Topics in
    COURSE_SKIP are left out of this walk.
  * Random: dealt from a shuffled deck of every question (each one comes up
    before any repeats), never from a topic this workbook's course-order
    questions cover and never the same as the last workbook's.
  * Review: REVIEW_PER_DAY questions you already did in course order, one
    from a couple of workbooks ago and one from further back (spaced review).
    Only the "on your own" part is printed: can you still do it cold?

Problems live in cs311_problems.json, so add more there at any time. No
network, no model, no saved state: everything is a function of the workbook
number (1, 2, 3, ...), so it never falls behind a calendar.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

PROBLEMS_FILE = Path(__file__).resolve().parent / "cs311_problems.json"
COURSE_NAME = "CS311 Algorithms"
COURSE_PER_DAY = 6                # course-order questions per workbook
# Topics (by "key") the course-order walk skips because you already know them.
# They still come up now and then as the random review question.
COURSE_SKIP = {"stable-matching"}
REVIEW_PER_DAY = 2                # past course-order questions to redo each workbook
_SHUFFLE_SEED = 311


def load_topics() -> list[dict]:
    return json.loads(PROBLEMS_FILE.read_text(encoding="utf-8"))["topics"]


def all_questions(topics: list[dict]) -> list[tuple[int, int]]:
    """Every (topic index, question index) pair, in course order."""
    return [(ti, qi)
            for ti, t in enumerate(topics)
            for qi in range(min(len(t.get("problems", [])), len(t.get("practice", []))))]


def course_order_questions(n: int, topics: list[dict]) -> list[tuple[int, int]]:
    qs = [q for q in all_questions(topics) if topics[q[0]].get("key") not in COURSE_SKIP] \
        or all_questions(topics)
    first = (n - 1) * COURSE_PER_DAY
    return [qs[(first + k) % len(qs)] for k in range(min(COURSE_PER_DAY, len(qs)))]


def random_question(n: int, topics: list[dict]) -> tuple[int, int]:
    """Deal from a shuffled deck of every question, one card a workbook from workbook 1.

    Each workbook takes the first card that isn't on a topic its course-order
    questions cover and isn't the previous workbook's card. When the deck runs
    out (or nothing left in it fits), a freshly shuffled deck goes underneath,
    so every question comes up once before any comes up twice.
    """
    qs = all_questions(topics)
    deck: list[tuple[int, int]] = []
    shuffles = 0
    prev = None
    for k in range(1, n + 1):
        avoid = {ti for ti, _ in course_order_questions(k, topics)}
        pick = None
        for _ in range(2):
            pick = next((q for q in deck if q[0] not in avoid and q != prev), None)
            if pick is not None:
                break
            deck += [qs[i] for i in _cycle_order(len(qs), shuffles)]
            shuffles += 1
        if pick is None:  # only possible with a tiny bank; just avoid a repeat
            pick = next((q for q in deck if q != prev), deck[0])
        deck.remove(pick)
        prev = pick
    return prev


def review_questions(n: int, topics: list[dict],
                     exclude: set[tuple[int, int]] = frozenset()) -> list[tuple[tuple[int, int], int]]:
    """Up to REVIEW_PER_DAY past course-order questions, each with the workbook it was in.

    The first comes from two workbooks ago (the last one in workbook 2), the
    next from four or more back (or anything earlier when there isn't that
    much history yet).
    """
    past = n - 1
    if past <= 0:
        return []
    done = {}
    for k in range(n - 1, 0, -1):
        for q in course_order_questions(k, topics):
            done.setdefault(q, k)  # most recent workbook it was in
    rng = random.Random(f"workbook-{n}-review")
    recent = [q for q, k in done.items() if n - k == min(2, past)]
    older = [q for q, k in done.items() if n - k >= 4]
    picks: list[tuple[int, int]] = []
    # One recent, one older; any past question fills a slot whose pool is empty.
    for pool in (recent, older) + (list(done),) * REVIEW_PER_DAY:
        if len(picks) >= REVIEW_PER_DAY:
            break
        options = sorted(q for q in pool if q not in picks and q not in exclude)
        if options:
            picks.append(rng.choice(options))
    return [(q, done[q]) for q in picks]


def _cycle_order(n: int, cycle: int) -> list[int]:
    order = list(range(n))
    random.Random(_SHUFFLE_SEED + cycle).shuffle(order)
    return order


def _question(topics: list[dict], ti: int, qi: int, kind: str) -> dict:
    t = topics[ti]
    count = min(len(t.get("problems", [])), len(t.get("practice", [])))
    return {
        "kind": kind,  # "course" or "random"
        "topic": t["name"],
        "chapter": t.get("chapter", ""),
        "lectures": t.get("lectures", ""),
        "intro": t.get("intro") or {},
        "topic_number": ti + 1,
        "topic_count": len(topics),
        "question_number": qi + 1,
        "question_count": count,
        "worked": t["problems"][qi],
        "practice": t["practice"][qi],
    }


def daily_set(n: int | None = None) -> dict:
    """Workbook n's course-order questions (a list), random question and reviews.

    n defaults to the next workbook to be built.
    """
    if n is None:
        import progression
        n = progression.next_number()
    n = max(1, n)
    topics = load_topics()
    course = course_order_questions(n, topics)
    rti, rqi = random_question(n, topics)
    review = review_questions(n, topics, exclude=set(course) | {(rti, rqi)})
    return {
        "course": COURSE_NAME,
        "workbook": n,
        "course_order": [_question(topics, ti, qi, "course") for ti, qi in course],
        "random": _question(topics, rti, rqi, "random"),
        "review": [{**_question(topics, ti, qi, "review"), "from_workbook": k}
                   for (ti, qi), k in review],
    }


if __name__ == "__main__":
    import sys
    s = daily_set(int(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"Workbook {s['workbook']}")
    for label, q in ([("Course order", q) for q in s["course_order"]] + [("Random", s["random"])]
                     + [(f"Review (from workbook {q['from_workbook']})", q) for q in s["review"]]):
        print(f"{label}: {q['topic']} Q{q['question_number']}/{q['question_count']} "
              f"({q['chapter']}, {q['lectures']})")
        print("  worked:  ", q["worked"]["title"])
        print("  practice:", q["practice"]["problem"][:70])
