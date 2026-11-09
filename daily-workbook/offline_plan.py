"""Offline plan: shared by the daily workbook and the receipt printer.

Settings live in offline_plan.json and the things you need to do online live
in online_list.txt, both next to this file. No dependencies, no network.

Modes (set "mode" in offline_plan.json):
  daily_hour   one online window every day, e.g. 19:00-20:00
  weekly_day   one internet day a week, plus an optional short daily check
"""
from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN_FILE = HERE / "offline_plan.json"
ONLINE_LIST_FILE = HERE / "online_list.txt"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

DEFAULT_PLAN = {
    "mode": "daily_hour",
    "online_window": {"start": "19:00", "end": "20:00"},
    "internet_day": "saturday",
    "daily_check_minutes": 10,
    "exceptions": [
        "Emergencies",
        "Work that needs it",
        "Bills and banking",
        "Maps when I'm out",
    ],
    "offline_toolkit": [
        "Local MLX model for quick questions",
        "Today's printed Substack article",
        "HSK flashcards + offline dictionary",
        "Kleinberg & Tardos textbook",
        "Downloaded music and podcasts",
    ],
}

LIST_HEADER = """# Online list: things to do in your online time, one per line.
# Write things here (or on the printout) instead of going online right away.
# Delete a line once it's done. Lines starting with # are ignored.
"""


def load_plan() -> dict:
    plan = dict(DEFAULT_PLAN)
    try:
        plan.update(json.loads(PLAN_FILE.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠ offline_plan.json could not be read ({e}); using defaults")
    if plan.get("mode") not in ("daily_hour", "weekly_day"):
        plan["mode"] = "daily_hour"
    return plan


def load_online_list() -> list[str]:
    try:
        lines = ONLINE_LIST_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def save_online_list(items: list[str]) -> None:
    body = "".join(f"{i}\n" for i in items)
    ONLINE_LIST_FILE.write_text(LIST_HEADER + "\n" + body, encoding="utf-8")


def add_online_item(text: str) -> None:
    save_online_list(load_online_list() + [text.strip()])


def _fmt_time(hhmm: str) -> str:
    t = time.fromisoformat(hhmm)
    return datetime.combine(date.today(), t).strftime("%-I:%M%p").lower().replace(":00", "")


def window_text(plan: dict) -> str:
    w = plan.get("online_window", {})
    try:
        # Plain hyphen: thermal printers often can't print an en dash.
        return f"{_fmt_time(w['start'])}-{_fmt_time(w['end'])}"
    except (KeyError, ValueError):
        return "your online window"


def today_summary(day: date | None = None) -> dict:
    """Everything a printout needs for today's offline section."""
    day = day or date.today()
    plan = load_plan()
    weekday = DAYS[day.weekday()]
    internet_day = str(plan.get("internet_day", "saturday")).lower()

    if plan["mode"] == "weekly_day":
        is_online_day = weekday == internet_day
        if is_online_day:
            headline = "Internet day: work through your online list"
        else:
            mins = plan.get("daily_check_minutes", 0)
            check = f" (plus a {mins}-min urgent check)" if mins else ""
            headline = f"Offline today. Internet day is {internet_day.title()}{check}"
    else:
        is_online_day = False
        headline = f"Online window: {window_text(plan)}"

    return {
        "mode": plan["mode"],
        "headline": headline,
        "is_online_day": is_online_day,
        "window": window_text(plan),
        "internet_day": internet_day.title(),
        "online_list": load_online_list(),
        "exceptions": list(plan.get("exceptions", [])),
        "toolkit": list(plan.get("offline_toolkit", [])),
    }
