# One page for one day: what today is for, what is done, what is left.
# Run:  focus today      (focus today 3 shows day D3)
import sys

import appts
import dash
import focuslib as fl
import matrix
import routines

HELP = """
today.py - one page for one day

  focus today          the current (or most recent) day
  focus today 3        day D3

  FIXED TODAY  appointments and other fixed times (focus appt)
  MUST         the one task today is for
  PROMISE      (O) pomodoro done, ( ) still promised
  ROUTINES     today's boxes for shower, meals and so on (focus check)
  DONE SO FAR  each pomodoro and break, in order, with what you said
               you would do and how it went
  NEXT         the note you left yourself for the next pomodoro
  STILL TO DO  what is left of today's promise
  DUE SOON     other tasks due within 2 focus days
  PARKED       stray thoughts waiting to be sorted
Nothing else from the backlog is shown, on purpose.
"""

FOCUS = {"3": ("on_green", "focused"), "2": ("on_yellow", "okay"), "1": ("on_red", "scattered")}
ENERGY = {"1": "low", "2": "normal", "3": "high"}


def show(screen, day=None):
    days = fl.read_log()
    if day is None:
        day = max(days) if days else None
    screen.line("")
    if day is None or day not in days:
        screen.line("  TODAY", "bold")
        screen.line("")
        screen.line("  No day has been started yet. Type  focus  to begin.", "grey")
        return
    info = days[day]
    events = fl.day_events(day)
    backlog = fl.load_backlog()
    start = dict(pair for kind, fields in events if kind == "start" for pair in fields.items())
    cycle, position = fl.cycle_of(day)
    planned = info["planned"] or 0
    done = len(info["focus"])
    closed = info["did"] is not None

    title = "  TODAY  -  D{}  -  cycle {}, day {} of {}".format(day, cycle, position, fl.CYCLE_DAYS)
    if start.get("workbook"):
        title += "     workbook: {}".format(start["workbook"])
    screen.line(title, "bold")
    screen.line("")

    fixed = appts.rows(day)
    for row in fixed:
        screen.row(row)
    if fixed:
        screen.line("")
    must = start.get("must", "")
    finished = "D{} | {}".format(day, must) in backlog["DONE"]
    screen.row([dash.label("MUST"), ("bold", matrix.strip_box(must)[:58] or "-"),
                ("green", "   FINISHED" if finished else "")])
    screen.row([dash.label("PROMISE")] + dash.today_row(done, planned) +
               [("plain", "  {} of {} pomodoros".format(min(done, planned), planned))])
    if start.get("energy") in ENERGY:
        screen.row([dash.label("ENERGY"), ("plain", ENERGY[start["energy"]])])

    for row in routines.rows(day):
        screen.row(row)

    screen.line("")
    screen.line("  DONE SO FAR", "bold")
    next_note, shown = "", 0
    for kind, fields in events:
        if kind.startswith("pomo"):
            color, word = FOCUS.get(fields.get("focus"), ("grey", ""))
            screen.row([("plain", "    {:<3}".format(kind.split()[-1])), (color, "##"),
                        ("plain", "  {:<46}".format(fields.get("intent", "")[:46])), ("grey", word)])
            if fields.get("note"):
                screen.row([("grey", "           note: {}".format(fields["note"])[:76])])
            next_note = fields.get("next", next_note)
            shown += 1
        elif kind.startswith("break"):
            away = fields.get("away") == "y"
            screen.row([("plain", "       "), ("on_cyan" if away else "grey", "~~"),
                        ("grey", "  break: {:<39}".format(fields.get("intent", "")[:39])),
                        ("grey", "stepped away" if away else "stayed at the screen")])
            shown += 1
        elif kind == "abandoned":
            screen.row([("grey", "    x      abandoned: {}".format(fields.get("intent", ""))[:76])])
            shown += 1
    if not shown:
        screen.line("    nothing yet", "grey")

    screen.line("")
    if closed:
        screen.row([dash.label("STILL TO DO"), ("green", "nothing - promise kept. You are done for today.")])
    else:
        if next_note:
            screen.row([dash.label("NEXT"), ("green", next_note[:60])])
        left = max(0, planned - done)
        screen.row([dash.label("STILL TO DO"), ("yellow", "{} pomodoro{}".format(
            left, "" if left == 1 else "s")), ("plain", "  (next is {} of {})".format(done + 1, planned))])

    soon = []
    for section in fl.SECTIONS[:-1]:
        for line in backlog[section]:
            item = fl.parse_item(line)
            if item["due"] is not None and item["due"] - day <= 2 and line != must:
                soon.append((item["due"] - day, matrix.strip_box(item["text"])))
    for i, (left, text) in enumerate(sorted(soon)[:4]):
        when = "OVERDUE" if left < 0 else "today" if left == 0 else "in {} day{}".format(
            left, "" if left == 1 else "s")
        screen.row([dash.label("DUE SOON" if i == 0 else ""), ("red", "{:<10}".format(when)),
                    ("plain", text[:50])])

    parked = fl.read_park()
    if parked:
        screen.row([dash.label("PARKED"), ("yellow", "{} thought{}".format(
            len(parked), "" if len(parked) == 1 else "s")), ("grey", "  (sorted at the end of the day)")])
        for text in parked[:4]:
            screen.line("              - {}".format(text[:60]), "grey")

    screen.line("")
    if not closed:
        screen.line("  Type  focus  to carry on with this day.", "grey")
    screen.flush()


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    numbers = [arg for arg in sys.argv[1:] if arg.isdigit()]
    show(fl.Screen(fl.load_settings()["display"]), int(numbers[0]) if numbers else None)


if __name__ == "__main__":
    main()
