# What do I actually use? Counts how often each optional question got an answer.
# Run:  focus report        (this cycle)     focus report all
import sys

import dash
import focuslib as fl

HELP = """
report.py - what you use and what you skip

  focus report          this cycle
  focus report 2        cycle 2
  focus report all      everything so far

For each optional question it counts how often you gave an answer and
how often you pressed Enter past it. A question you nearly always skip
is only slowing you down: the report names the line to put in
settings.txt to switch it off (for example  ask_first=off ).
Switch it back on by changing off to on.
day.py shows this report at the end of each cycle.
"""

DEFAULT_BREAK = "stand up, water"
# (label, settings key or None, what counts as one chance, test for "used")
ROWS = [
    ("workbook page", "ask_workbook", "start", lambda f: "workbook" in f),
    ("appointments", "ask_appointments", "day", lambda f: f.get("appts", 0) > 0),
    ("first action", "ask_first", "pomo", lambda f: "first" in f),
    ("how-it-went note", "ask_note", "pomo", lambda f: "note" in f),
    ("NEXT note", "ask_next", "pomo", lambda f: "next" in f),
    ("stray thought", "ask_stray", "pomo", lambda f: "parked" in f),
    ("own break plan", None, "break", lambda f: f.get("intent", DEFAULT_BREAK) != DEFAULT_BREAK),
    ("break note", "ask_break_note", "break", lambda f: "note" in f),
    ("routines ticked", None, "day", lambda f: f.get("ticks", 0) > 0),
    ("reward taken", "ask_reward", "closed", lambda f: f.get("rewards", 0) > 0),
]


def gather(days):
    """{kind of chance: [fields, ...]} for the given days."""
    chances = {"start": [], "pomo": [], "break": [], "day": [], "closed": []}
    log = fl.read_log()
    for day in days:
        if day not in log:
            continue
        events = fl.day_events(day)
        counts = {"appts": len([1 for kind, _ in events if kind == "appt"]),
                  "ticks": len([1 for kind, _ in events if kind == "tick"]),
                  "rewards": len([1 for kind, _ in events if kind == "reward"])}
        chances["day"].append(counts)
        if log[day]["did"] is not None:
            chances["closed"].append(counts)
        for kind, fields in events:
            if kind == "start":
                chances["start"].append(fields)
            elif kind.startswith("pomo"):
                chances["pomo"].append(fields)
            elif kind.startswith("break"):
                chances["break"].append(fields)
    return chances


def show(screen, scope=None):
    log = fl.read_log()
    settings = fl.load_settings()
    if scope == "all":
        days, title = sorted(log), "everything so far"
    else:
        cycle = scope or (fl.cycle_of(max(log))[0] if log else 1)
        first = (cycle - 1) * fl.CYCLE_DAYS + 1
        days = list(range(first, first + fl.CYCLE_DAYS))
        title = "cycle {} (D{} to D{})".format(cycle, first, first + fl.CYCLE_DAYS - 1)
    chances = gather(days)
    screen.line("")
    screen.line("  WHAT YOU USE  -  {}".format(title), "bold")
    screen.line("")
    switch_off = []
    for name, key, kind, used_test in ROWS:
        total = len(chances[kind])
        used = len([fields for fields in chances[kind] if used_test(fields)])
        if key and not fl.on(settings, key):
            verdict, color = "switched off", "grey"
        elif total < 4:
            verdict, color = "too early to say", "grey"
        elif used * 5 < total:
            verdict, color = "rarely used", "yellow"
            if key:
                switch_off.append(key)
        else:
            verdict, color = "in use", "green"
        screen.row([("plain", "  {:<17}".format(name))] + dash.bar(used, total, 12) +
                   [("plain", "  {:>2} of {:<3}".format(used, total)), (color, verdict)])
    screen.line("")
    if switch_off:
        screen.line("  You nearly always skip some questions. To stop being asked, put", "yellow")
        screen.line("  these lines in settings.txt (Notepad++):", "yellow")
        for key in switch_off:
            screen.line("      {}=off".format(key), "bold")
    else:
        screen.line("  Nothing stands out as worth switching off yet.", "grey")
    screen.line("")
    screen.flush()


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    args = [arg.lower() for arg in sys.argv[1:]]
    scope = "all" if "all" in args else None
    numbers = [arg for arg in args if arg.isdigit()]
    if numbers:
        scope = int(numbers[0])
    show(fl.Screen(fl.load_settings()["display"]), scope)


if __name__ == "__main__":
    main()
