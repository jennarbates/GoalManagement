"""Lesson-help actions shown as buttons on each card in the Today tab.

This is the easiest place to add new features. Every function decorated with
@action shows up in the Mac app automatically after you restart the bridge
(Settings tab, "Restart bridge"). No Swift changes needed.

Each action receives `item`, a dict describing the card the button was
clicked on. Keys you can rely on:

    kind      "algorithms" | "leetcode" | "hsk" | "chore"
    title     short title, e.g. "Dynamic Programming (Ch. 6)"
    detail    longer description of the lesson / project
    url       reference link (may be empty)
    words     list of {"char","pinyin","meaning"} (HSK cards only)
    day_type  "work" | "free" | "therapy" | "weekend"

It must return a list of chat messages ({"role", "content"}). The bridge
runs them through the local model and streams the answer back.

`kinds` limits which cards show the button. Use ("*",) for every card.
"""
from __future__ import annotations

ACTIONS: dict[str, dict] = {}


def action(action_id: str, label: str, kinds=("*",), max_tokens: int = 700,
           temperature: float = 0.4, icon: str = "sparkles"):
    """Register an action. `icon` is an SF Symbols name used by the Mac app."""
    def wrap(fn):
        ACTIONS[action_id] = {
            "id": action_id, "label": label, "kinds": list(kinds),
            "max_tokens": max_tokens, "temperature": temperature,
            "icon": icon, "fn": fn,
        }
        return fn
    return wrap


def public_list() -> list[dict]:
    return [{k: v for k, v in a.items() if k != "fn"} for a in ACTIONS.values()]


TUTOR = (
    "You are a patient, concise study tutor. Use short paragraphs and small "
    "code or math examples. Never pad the answer. Plain text only, no markdown "
    "tables."
)


def _describe(item: dict) -> str:
    parts = [f"Topic: {item.get('title', '')}"]
    if item.get("detail"):
        parts.append(f"Details: {item['detail']}")
    if item.get("words"):
        ws = ", ".join(f"{w['char']} ({w['pinyin']}, {w['meaning']})" for w in item["words"])
        parts.append(f"Words: {ws}")
    return "\n".join(parts)


@action("explain", "Explain it", kinds=("algorithms",), icon="lightbulb")
def explain(item):
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nExplain this topic from "
         "scratch in under 250 words, then give one tiny worked example."},
    ]


@action("quiz", "Quiz me", kinds=("algorithms", "hsk"), icon="questionmark.circle")
def quiz(item):
    extra = ""
    if item.get("kind") == "algorithms":
        extra = " Ask about running times, which technique fits, and small traces by hand."
    if item.get("kind") == "hsk":
        extra = " Mix meaning, pinyin, and fill-in-the-blank sentence questions."
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nWrite 5 multiple choice "
         "questions (A to D) on this." + extra + " Put the answer key at the very end "
         "under the line 'ANSWERS'."},
    ]


@action("plan", "Break it down", kinds=("chore",), icon="list.bullet")
def plan(item):
    budget = {"work": "about 30 minutes", "free": "about 2 hours",
              "therapy": "about 15 minutes", "weekend": "about 1 hour"}.get(
        item.get("day_type", ""), "about 1 hour")
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + f"\n\nBreak this into 4 to 7 "
         f"concrete steps that fit in {budget}. Number them. Keep each step to one line."},
    ]


@action("pseudocode", "Pseudocode", kinds=("algorithms",), icon="chevron.left.forwardslash.chevron.right")
def pseudocode(item):
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nPick the main algorithm "
         "from this topic and write short, clear pseudocode for it, then state its "
         "running time in one line."},
    ]


@action("lc_hint", "Give me a hint", kinds=("leetcode",), icon="lightbulb.min")
def lc_hint(item):
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nI'm stuck on this LeetCode "
         "problem. Give me ONE small hint that points toward the right pattern or "
         "data structure. No code and no full solution."},
    ]


@action("lc_complexity", "Check my complexity", kinds=("leetcode",), icon="gauge")
def lc_complexity(item):
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nExplain how to work out the "
         "time and space complexity of a solution to this problem, step by step, "
         "without giving away the solution itself."},
    ]


@action("sentences", "Example sentences", kinds=("hsk",), icon="character.bubble")
def sentences(item):
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nFor each word, write one "
         "very simple HSK 1 level sentence. Format each as: Chinese | pinyin | English."},
    ]
