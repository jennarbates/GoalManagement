"""CS311 (Algorithms, UMass, Kleinberg & Tardos) daily practice.

Each day gets COURSE_PER_DAY questions in course order plus one random
question. A question is one worked problem (with its explanation) plus the
matching practice problem (same index in the topic's "problems" and
"practice" lists; answers go on a separate answer-key page).

  * Course order: walks every question in course order, COURSE_PER_DAY a
    day, starting at COURSE_START (Algorithm Analysis Q1, Q2, Q3, then
    Graphs Q1, ...) and loops back to the start when it runs out. Topics in
    COURSE_SKIP are left out of this walk.
  * Random: dealt from a shuffled deck of every question (each one comes up
    before any repeats), never from a topic today's course-order questions
    cover and never the same as yesterday's.
  * Review: REVIEW_PER_DAY questions you already did in course order, one
    from a couple of days ago and one from further back (spaced review).
    Only the "on your own" part is printed: can you still do it cold?

Problems live in cs311_problems.json, so add more there at any time. No
network, no model, no saved state: everything is a function of the date.
"""
from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

PROBLEMS_FILE = Path(__file__).resolve().parent / "cs311_problems.json"
COURSE_NAME = "CS311 Algorithms"
COURSE_START = date(2026, 11, 10)  # day 1 of the course (nothing before it)
COURSE_PER_DAY = 6                # course-order questions per day
# Topics (by "key") the course-order walk skips because you already know them.
# They still come up now and then as the random review question.
COURSE_SKIP = {"stable-matching"}
REVIEW_PER_DAY = 2                # past course-order questions to redo each day
_SHUFFLE_SEED = 311


def load_topics() -> list[dict]:
    return json.loads(PROBLEMS_FILE.read_text(encoding="utf-8"))["topics"]


def all_questions(topics: list[dict]) -> list[tuple[int, int]]:
    """Every (topic index, question index) pair, in course order."""
    return [(ti, qi)
            for ti, t in enumerate(topics)
            for qi in range(min(len(t.get("problems", [])), len(t.get("practice", []))))]


def course_order_questions(day: date, topics: list[dict]) -> list[tuple[int, int]]:
    qs = [q for q in all_questions(topics) if topics[q[0]].get("key") not in COURSE_SKIP] \
        or all_questions(topics)
    first = (day - COURSE_START).days * COURSE_PER_DAY
    return [qs[(first + k) % len(qs)] for k in range(min(COURSE_PER_DAY, len(qs)))]


def random_question(day: date, topics: list[dict]) -> tuple[int, int]:
    """Deal from a shuffled deck of every question, one card a day from COURSE_START.

    Each day takes the first card that isn't on a topic the course-order
    questions cover that day and isn't yesterday's card. When the deck runs out
    (or nothing left in it fits), a freshly shuffled deck goes underneath, so
    every question comes up once before any comes up twice.
    """
    qs = all_questions(topics)
    d = min(day, COURSE_START).toordinal()
    deck: list[tuple[int, int]] = []
    shuffles = 0
    prev = None
    while True:
        avoid = {ti for ti, _ in course_order_questions(date.fromordinal(d), topics)}
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
        if d == day.toordinal():
            return pick
        d += 1


def review_questions(day: date, topics: list[dict],
                     exclude: set[tuple[int, int]] = frozenset()) -> list[tuple[tuple[int, int], date]]:
    """Up to REVIEW_PER_DAY past course-order questions, each with the day it was done.

    The first comes from two days ago (yesterday on day 2), the next from four or
    more days back (or anything earlier when there isn't that much history yet).
    """
    past_days = (day - COURSE_START).days
    if past_days <= 0:
        return []
    done = {}
    for k in range(1, past_days + 1):
        d = date.fromordinal(day.toordinal() - k)
        for q in course_order_questions(d, topics):
            done.setdefault(q, d)  # most recent day it was done
    rng = random.Random(f"{day.isoformat()}-review")
    recent = [q for q, d in done.items() if (day - d).days == min(2, past_days)]
    older = [q for q, d in done.items() if (day - d).days >= 4]
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


def daily_set(day: date | None = None) -> dict:
    """Today's course-order questions (a list), random question and reviews.

    Before COURSE_START there is nothing yet: empty lists and no random question.
    """
    day = day or date.today()
    if day < COURSE_START:
        return {"course": COURSE_NAME, "course_order": [], "random": None, "review": []}
    topics = load_topics()
    course = course_order_questions(day, topics)
    rti, rqi = random_question(day, topics)
    review = review_questions(day, topics, exclude=set(course) | {(rti, rqi)})
    return {
        "course": COURSE_NAME,
        "course_order": [_question(topics, ti, qi, "course") for ti, qi in course],
        "random": _question(topics, rti, rqi, "random"),
        "review": [{**_question(topics, ti, qi, "review"), "from_date": d.isoformat()}
                   for (ti, qi), d in review],
    }


if __name__ == "__main__":
    import sys
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    s = daily_set(d)
    if not s["course_order"]:
        print(f"Nothing yet: the course starts {COURSE_START.isoformat()}.")
    for label, q in ([("Course order", q) for q in s["course_order"]] + ([("Random", s["random"])] if s["random"] else [])
                     + [(f"Review (from {q['from_date']})", q) for q in s["review"]]):
        print(f"{label}: {q['topic']} Q{q['question_number']}/{q['question_count']} "
              f"({q['chapter']}, {q['lectures']})")
        print("  worked:  ", q["worked"]["title"])
        print("  practice:", q["practice"]["problem"][:70])
