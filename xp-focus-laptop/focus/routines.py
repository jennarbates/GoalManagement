# Daily routines: things that recur (shower, meals, meds). Tick boxes, no points.
# Run:  focus check
import focuslib as fl

HELP = """
routines.py - the daily routines checklist

  focus check

Routines are things that come round every day, like shower or meals.
They are not tasks: no points, no Eisenhower boxes, no deadlines.
The list is in routines.txt, one per line. Add x3 for three times a day:
    shower
    eat a meal x3
Type a routine's number to tick one box. Boxes start empty again on each
new focus day.
A streak counts focus days in a row on which the routine was fully done.
A day you do not open the laptop is not a focus day, so it does not break
a streak; a focus day that ends with a box empty does. "a" adds a routine. A wrong tick: focus undo.
The day page and the dashboard both show them.
"""

GRID_DAYS = 12
STREAK_MARKS = [3, 7, 14, 21, 30, 50, 75, 100, 150, 200, 365]


def label(text):
    return ("bold", "  {:<12}".format(text))


def streaks(name, times, ticks, today):
    """(current streak, best streak) in focus days where the routine was fully done.
    A day still in progress does not break the current streak."""
    best = run = 0
    for day in range(1, today + 1):
        if ticks.get(day, {}).get(name, 0) >= times:
            run += 1
            best = max(best, run)
        elif day < today:
            run = 0
    return run, best


def streak_text(current, best):
    if best == 0:
        return ""
    text = "streak {}".format(current)
    if best > current:
        text += "  (best {})".format(best)
    return text


def boxes(times, done):
    done = min(done, times)
    return [("green", "[x] " * done), ("grey", "[ ] " * (times - done))]


def rows(day, first="ROUTINES"):
    """Rows for the day page: one line of boxes per routine."""
    every = fl.read_ticks()
    ticks = every.get(day, {})
    out = []
    for i, (name, times) in enumerate(fl.load_routines()):
        current, best = streaks(name, times, every, day)
        out.append([label(first if i == 0 else "")] + boxes(times, ticks.get(name, 0)) +
                   [("plain", "{:<22}".format(name[:22])), ("yellow", streak_text(current, best))])
    return out


def grid_rows(days, today):
    """Rows for the dashboard: each routine across the last 12 focus days."""
    ticks = fl.read_ticks()
    span = [d for d in range(max(1, today - GRID_DAYS + 1), today + 1)]
    out = []
    for i, (name, times) in enumerate(fl.load_routines()):
        cells = [label("ROUTINES" if i == 0 else ""), ("plain", "{:<12}".format(name[:11]))]
        for d in span:
            done = ticks.get(d, {}).get(name, 0)
            if d not in days or done <= 0:
                cells.append(("grey", ".."))
            elif done >= times:
                cells.append(("on_green", "##"))
            else:
                cells.append(("on_yellow", "=="))
            cells.append(("plain", " "))
        current, best = streaks(name, times, ticks, today)
        if best:
            cells.append(("yellow", " {}".format(current)))
            cells.append(("grey", " (best {})".format(best) if best > current else ""))
        out.append(cells)
    return out


def add(screen):
    name = fl.ask(screen, "  Name of the routine (Enter = cancel):")
    if not name:
        return
    times = fl.ask_int(screen, "  How many times a day? (Enter = 1):", 1, 9, 1)
    lines = fl.read_lines("routines.txt")
    lines.append(name if times == 1 else "{} x{}".format(name, times))
    fl.write_lines("routines.txt", lines)
    screen.line("  Added.", "green")


def check(screen, day, allow_add=True):
    """Show today's boxes and tick them off by number."""
    while True:
        items = fl.load_routines()
        every = fl.read_ticks()
        ticks = every.get(day, {})
        screen.line("")
        screen.line("== ROUTINES - D{} ==".format(day), "yellow")
        for i, (name, times) in enumerate(items, 1):
            current, best = streaks(name, times, every, day)
            screen.row([("plain", "  {:>2}. ".format(i))] + boxes(times, ticks.get(name, 0)) +
                       [("plain", "{:<22}".format(name[:22])), ("yellow", streak_text(current, best))])
        if not items:
            screen.line("  No routines yet.", "grey")
        left = sum(max(0, times - ticks.get(name, 0)) for name, times in items)
        if items and left == 0:
            screen.line("  All done for today.", "green")
        prompt = "Tick one off - type its number"
        if allow_add:
            prompt += ", a = add a routine"
        pick = fl.ask(screen, prompt + " (Enter = done):")
        if not pick:
            return
        if pick.lower() == "a" and allow_add:
            add(screen)
        elif pick.isdigit() and 1 <= int(pick) <= len(items):
            name, times = items[int(pick) - 1]
            if ticks.get(name, 0) >= times:
                screen.line("  Already complete for today.", "grey")
            else:
                fl.log(day, "tick", name)
                if ticks.get(name, 0) + 1 >= times:
                    current = streaks(name, times, fl.read_ticks(), day)[0]
                    if current in STREAK_MARKS:
                        screen.line("")
                        screen.line("  *** {}: {} days in a row! ***".format(name, current), "yellow")


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    days = fl.read_log()
    if not days:
        screen.line("Start your first day with  focus  - routines are ticked per focus day.", "grey")
        return
    try:
        check(screen, max(days))
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
