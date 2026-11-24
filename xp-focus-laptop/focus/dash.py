# Progress dashboard: reads log.txt and backlog.txt and draws them.
# Run by itself:  python dash.py     (day.py shows it at the start and end)
import re
import sys

import focuslib as fl
import practice
import routines

BAR = 30
WALL_COLOR = {3: "green", 2: "yellow", 1: "red"}
MILESTONES = [1, 5, 10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 750, 1000]
WALL_MAX = 200             # pomodoros drawn on the wall (20 per row)
HEAT_CYCLES = 20           # columns in the activity grid


def label(text):
    return ("bold", "  {:<12}".format(text))


def bar(done, total, width=BAR):
    if total <= 0:
        return [("grey", "." * width)]
    filled = min(width, int(round(float(done) / total * width)))
    if done > 0 and filled == 0:
        filled = 1
    return [("on_green", "#" * filled), ("grey", "." * (width - filled))]


def all_focus(days):
    return [f for info in days.values() for f in info["focus"]]


def total_pomodoros():
    return len(all_focus(fl.read_log()))


def today_row(done, planned):
    """Filled tomatoes for finished pomodoros, hollow ones still promised."""
    done = min(done, planned)
    return [("red", "(O) " * done), ("grey", "( ) " * (planned - done))]


def banner(screen, text):
    width = len(text) + 10
    screen.line("")
    screen.line("  " + "*" * width, "yellow")
    screen.line("  *" + " " * (width - 2) + "*", "yellow")
    screen.line("  *    " + text + "    *", "yellow")
    screen.line("  *" + " " * (width - 2) + "*", "yellow")
    screen.line("  " + "*" * width, "yellow")
    screen.line("")


def heat_cell(info):
    """Activity grid: darker to brighter green for more pomodoros that day."""
    if info is None:
        return ("grey", "..")
    if info["planned"] is not None and info["did"] is None:
        return ("on_cyan", "~~")          # started, not finished
    count = len(info["focus"])
    if count <= 0:
        return ("grey", "..")
    if count == 1:
        return ("lo_green", "::")
    if count == 2:
        return ("on_green", "##")
    return ("on_lime", "@@")


def show_wall(screen, focus):
    shown = focus[-WALL_MAX:]
    if not shown:
        screen.row([label("POMODOROS"), ("grey", "none yet - the wall starts with your first one")])
        return
    for start in range(0, len(shown), 20):
        cells = [label("POMODOROS" if start == 0 else "")]
        for i, value in enumerate(shown[start:start + 20]):
            if i and i % 5 == 0:
                cells.append(("plain", " "))
            cells.append((WALL_COLOR.get(value, "grey"), "o"))
        screen.row(cells)
    note = "{} total".format(len(focus))
    if len(focus) > len(shown):
        note += " (showing the last {})".format(len(shown))
    screen.row([label(""), ("plain", note + "    "), ("green", "o"), ("plain", " focused  "),
                ("yellow", "o"), ("plain", " okay  "), ("red", "o"), ("plain", " scattered")])


def show_milestones(screen, total):
    earned = [m for m in MILESTONES if m <= total]
    upcoming = [m for m in MILESTONES if m > total]
    cells = [label("MILESTONES")]
    if earned:
        cells.append(("yellow", "".join("*{} ".format(m) for m in earned)))
    else:
        cells.append(("grey", "none yet"))
    screen.row(cells)
    if upcoming:
        screen.row([label(""), ("plain", "next {:<5}".format(upcoming[0]))] +
                   bar(total, upcoming[0], 20) +
                   [("plain", "  {} of {}".format(total, upcoming[0]))])


def show_activity(screen, days, cycle):
    first = max(1, cycle - HEAT_CYCLES + 1)
    cycles = range(first, cycle + 1)
    screen.row([label("ACTIVITY"), ("grey", "    " + "".join("{:<3}".format(c) for c in cycles))])
    for position in range(1, fl.CYCLE_DAYS + 1):
        cells = [label(""), ("grey", "d{}  ".format(position))]
        for c in cycles:
            day = (c - 1) * fl.CYCLE_DAYS + position
            cells += [heat_cell(days.get(day)), ("plain", " ")]
        screen.row(cells)
    screen.row([label(""), ("grey", "    "), ("grey", ".."), ("plain", " 0  "), ("lo_green", "::"), ("plain", " 1  "),
                ("on_green", "##"), ("plain", " 2  "), ("on_lime", "@@"), ("plain", " 3+  "),
                ("on_cyan", "~~"), ("plain", " not finished")])


def show_deadlines(screen, backlog, today):
    """Open tasks with a deadline (written @D20), nearest first."""
    due = []
    for section in fl.SECTIONS[:-1]:
        for line in backlog[section]:
            item = fl.parse_item(line)
            if item["due"] is not None:
                due.append((item["due"] - today, item["text"]))
    for i, (left, text) in enumerate(sorted(due)[:5]):
        if left < 0:
            when = "OVERDUE by {}".format(-left)
        elif left == 0:
            when = "due today"
        else:
            when = "due in {} day{}".format(left, "" if left == 1 else "s")
        screen.row([label("DEADLINES" if i == 0 else ""),
                    ("red" if left <= 2 else "yellow", "{:<15}".format(when)),
                    ("plain", text[:48])])


def show_summary(screen, cycle=None):
    """One-screen recap of a cycle."""
    days = fl.read_log()
    backlog = fl.load_backlog()
    if cycle is None:
        cycle = fl.cycle_of(max(days))[0] if days else 1
    first = (cycle - 1) * fl.CYCLE_DAYS + 1
    span = [(d, days[d]) for d in range(first, first + fl.CYCLE_DAYS) if d in days]
    focus = [f for _, info in span for f in info["focus"]]
    started = [info for _, info in span if info["planned"] is not None]
    kept = len([info for info in started if info["did"] == info["planned"]])
    away = [a for _, info in span for a in info["away"]]
    energy = [info["energy"] for _, info in span if info["energy"]]

    screen.line("")
    screen.line("  CYCLE {} SUMMARY  (D{} to D{})".format(cycle, first, first + fl.CYCLE_DAYS - 1), "bold")
    screen.line("")
    if not span:
        screen.line("  Nothing logged in this cycle yet.", "grey")
        return
    screen.row([label("DAYS WORKED")] + bar(len(span), fl.CYCLE_DAYS, 14) +
               [("plain", "  {} of {}".format(len(span), fl.CYCLE_DAYS))])
    for position in range(fl.CYCLE_DAYS):
        day = first + position
        cells = [label("POMODOROS" if position == 0 else ""), ("grey", "D{:<4}".format(day))]
        info = days.get(day)
        if info is None or not info["focus"]:
            cells.append(("grey", "-"))
        for value in (info["focus"] if info else []):
            cells.append((WALL_COLOR.get(value, "grey"), "o "))
        screen.row(cells)
    if focus:
        average = sum(focus) / float(len(focus))
        screen.row([label("FOCUS")] + bar(sum(focus), 3 * len(focus), 14) +
                   [("plain", "  average {:.1f} of 3 over {} pomodoros".format(average, len(focus)))])
    screen.row([label("PROMISES")] + bar(kept, len(started), 14) +
               [("plain", "  kept {} of {} days".format(kept, len(started)))])
    screen.row([label("BREAKS")] + bar(len([a for a in away if a]), len(away), 14) +
               [("plain", "  stepped away {} of {}".format(len([a for a in away if a]), len(away)))])
    if energy:
        screen.row([label("ENERGY"), ("plain", "low {}   normal {}   high {}".format(
            energy.count(1), energy.count(2), energy.count(3)))])
    with_work = [(len(info["focus"]), sum(info["focus"]), d) for d, info in span if info["focus"]]
    if with_work:
        count, _, best = max(with_work)
        screen.row([label("BEST DAY"), ("green", "D{} - {} pomodoro{}".format(
            best, count, "" if count == 1 else "s"))])
    finished = [fl.parse_item(line) for line in backlog["DONE"]]
    finished = [item for item in finished
                if item["day"] is not None and fl.cycle_of(item["day"])[0] == cycle]
    screen.row([label("POINTS"), ("on_green", "#" * min(40, sum(i["points"] or 0 for i in finished))),
                ("plain", "  {}".format(sum(i["points"] or 0 for i in finished)))])
    for i, item in enumerate(finished):
        screen.row([label("FINISHED" if i == 0 else ""),
                    ("plain", "[{}] {}".format(item["points"] or "?", item["text"])[:60])])
    screen.line("")
    screen.flush()


def summary_main():
    import sys
    fl.fix_streams()
    numbers = [arg for arg in sys.argv[1:] if arg.isdigit()]
    show_summary(fl.Screen(fl.load_settings()["display"]), int(numbers[0]) if numbers else None)


def show_full(screen, today=None):
    days = fl.read_log()
    backlog = fl.load_backlog()
    if today is None:
        today = max(days) if days else 1
    cycle, position = fl.cycle_of(today)
    focus = all_focus(days)

    screen.line("")
    screen.line("  FOCUS  -  day D{}  -  cycle {}, day {} of {}".format(
        today, cycle, position, fl.CYCLE_DAYS), "bold")
    screen.line("")

    info = days.get(today)
    if info is not None and info["planned"]:
        screen.row([label("TODAY")] + today_row(len(info["focus"]), info["planned"]))

    # Points finished this cycle, against everything planned for it.
    by_cycle = fl.done_points_by_cycle(backlog)
    done = by_cycle.get(cycle, 0)
    planned = done + fl.points_of(backlog["DOING"]) + fl.points_of(backlog["THIS CYCLE"])
    screen.row([label("THIS CYCLE")] + bar(done, planned) +
               [("plain", "  {} of {} points".format(done, planned))])

    show_deadlines(screen, backlog, today)
    started = [d for d in days.values() if d["planned"] is not None]
    kept = len([d for d in started if d["did"] == d["planned"]])
    screen.row([label("PROMISES")] + bar(kept, len(started), 14) +
               [("plain", "  kept {} of {} days".format(kept, len(started)))])
    away = [a for d in days.values() for a in d["away"]]
    screen.row([label("BREAKS")] + bar(len([a for a in away if a]), len(away), 14) +
               [("plain", "  stepped away {} of {}".format(len([a for a in away if a]), len(away)))])

    levels = [d["energy"] for d in days.values() if d["energy"]][-10:]
    if levels:
        looks = {1: ("on_cyan", "__"), 2: ("on_yellow", "=="), 3: ("on_green", "##")}
        cells = [label("ENERGY")]
        for level in levels:
            cells += [looks.get(level, ("grey", "..")), ("plain", " ")]
        screen.row(cells + [("grey", "  __ low  == normal  ## high")])
    parked = len(fl.read_park())
    if parked:
        screen.row([label("PARKED"), ("yellow", "{} thought{} waiting".format(
            parked, "" if parked == 1 else "s"))])

    screen.line("")
    show_wall(screen, focus)
    show_milestones(screen, len(focus))
    screen.line("")
    show_activity(screen, days, cycle)

    routine_rows = routines.grid_rows(days, today)
    if routine_rows:
        screen.line("")
        for row in routine_rows:
            screen.row(row)
        screen.row([label(""), ("grey", "{:<12}".format("12 days")), ("on_green", "##"),
                    ("plain", " all  "), ("on_yellow", "=="), ("plain", " some  "),
                    ("grey", ".."), ("plain", " none   "), ("yellow", "number"),
                    ("plain", " = streak")])

    for row in routines.weekly_history_rows(today):
        screen.row(row)

    if fl.on(fl.load_settings(), "ask_practice"):
        screen.line("")
        for row in practice.dash_rows(today):
            screen.row(row)

    if by_cycle:
        screen.line("")
        for i, c in enumerate(sorted(by_cycle)[-6:]):
            screen.row([label("VELOCITY" if i == 0 else ""), ("plain", "C{:<3}".format(c)),
                        ("on_green", "#" * min(by_cycle[c], 40)),
                        ("plain", "  {}".format(by_cycle[c]))])

    # Points by goal: tasks tagged like  [3] linked list in C #cs311
    goals = {}
    for section in fl.SECTIONS:
        for line in backlog[section]:
            item = fl.parse_item(line)
            for tag in item["tags"]:
                entry = goals.setdefault(tag, [0, 0])
                entry[1] += item["points"] or 0
                if section == "DONE":
                    entry[0] += item["points"] or 0
    if goals:
        screen.line("")
        wide = min(18, max(len(tag) for tag in goals) + 3)
        for i, tag in enumerate(sorted(goals)):
            got, total = goals[tag]
            screen.row([label("GOALS" if i == 0 else ""),
                        ("plain", "{:<{}}".format("#" + tag, wide)[:wide])] +
                       bar(got, total, 20) + [("plain", "  {} of {} points".format(got, total))])
    screen.line("")
    screen.flush()


HELP = """
dash.py - the progress dashboard

  focus dash           one screen: one line per area
  focus dash all       everything, in full (about two screens)

The short dashboard:
  TODAY, THIS CYCLE, DEADLINE (the nearest), PROMISES, POMODOROS (total
  and the bar to your next star), 14 DAYS (one block per day),
  ROUTINES (streaks), PRACTICE (rungs, fears against reality), PARKED.

The full dashboard adds:

  TODAY       (O) done, ( ) still promised
  THIS CYCLE  points finished out of points planned
  PROMISES    days where you did exactly what you planned
  BREAKS      breaks where you really stepped away
  ENERGY      your last 10 check-ins
  PARKED      stray thoughts waiting in park.txt
  POMODOROS   the wall: one o each, green focused, yellow okay, red scattered
  MILESTONES  stars at 1, 5, 10, 25, 50, 75, 100 ... and a bar to the next
  ACTIVITY    cycles across, days down; brighter green = more pomodoros
  ROUTINES    each routine over the last 12 focus days, and its streak
  PRACTICE    rungs climbed on each ladder, a dot per rep coloured by how
              hard it was, and bars for "feared it" against "it happened"
  VELOCITY    points finished per cycle
  GOALS       points per goal, for tasks tagged like #hsk or #cs311
"""

def nearest_deadline(backlog, today):
    """(days left, text, how many more) for the closest open deadline, or None."""
    due = []
    for section in fl.SECTIONS[:-1]:
        for line in backlog[section]:
            item = fl.parse_item(line)
            if item["due"] is not None:
                due.append((item["due"] - today, item["text"]))
    if not due:
        return None
    due.sort()
    return due[0][0], due[0][1], len(due) - 1


def show(screen, today=None):
    """The one-screen dashboard: one line per area. The long one is show_full."""
    days = fl.read_log()
    backlog = fl.load_backlog()
    if today is None:
        today = max(days) if days else 1
    cycle, position = fl.cycle_of(today)
    focus = all_focus(days)

    screen.line("")
    screen.line("  FOCUS  -  day D{}  -  cycle {}, day {} of {}".format(
        today, cycle, position, fl.CYCLE_DAYS), "bold")
    screen.line("")

    info = days.get(today)
    if info is not None and info["planned"]:
        screen.row([label("TODAY")] + today_row(len(info["focus"]), info["planned"]))

    by_cycle = fl.done_points_by_cycle(backlog)
    done = by_cycle.get(cycle, 0)
    planned = done + fl.points_of(backlog["DOING"]) + fl.points_of(backlog["THIS CYCLE"])
    screen.row([label("THIS CYCLE")] + bar(done, planned) +
               [("plain", "  {} of {} points".format(done, planned))])

    nearest = nearest_deadline(backlog, today)
    if nearest:
        left, text, more = nearest
        when = ("OVERDUE by {}".format(-left) if left < 0 else "due today" if left == 0
                else "due in {} day{}".format(left, "" if left == 1 else "s"))
        text = re.sub(r"\s*(\(B[1-4]\)|@D\d+)", "", text)
        screen.row([label("DEADLINE"), ("red" if left <= 2 else "yellow", "{:<15}".format(when)),
                    ("plain", text[:36]), ("grey", "  +{} more".format(more) if more else "")])

    started = [d for d in days.values() if d["planned"] is not None]
    kept = len([d for d in started if d["did"] == d["planned"]])
    screen.row([label("PROMISES")] + bar(kept, len(started), 14) +
               [("plain", "  kept {} of {} days".format(kept, len(started)))])

    upcoming = [m for m in MILESTONES if m > len(focus)]
    cells = [label("POMODOROS"), ("red", "o "), ("plain", "{:<5}".format(len(focus)))]
    if upcoming:
        cells += [("plain", "next star at {:<5}".format(upcoming[0]))] + bar(len(focus), upcoming[0], 20)
    screen.row(cells)

    cells = [label("14 DAYS")]
    for day in range(max(1, today - 13), today + 1):
        cells += [heat_cell(days.get(day)), ("plain", " ")]
    screen.row(cells)

    items = fl.load_routines()
    if items:
        ticks = fl.read_ticks()
        cells, used = [label("ROUTINES")], 0
        for name, times in items:
            current, best = routines.streaks(name, times, ticks, today)
            text = "{} ".format(name[:14])
            if used + len(text) + 6 > 62:
                cells.append(("grey", "..."))
                break
            cells += [("plain", text), ("yellow", "{}".format(current)), ("plain", "   ")]
            used += len(text) + len(str(current)) + 3
        cells.append(("grey", "(streaks)"))
        screen.row(cells)

    weekly = fl.load_weekly()
    if weekly:
        wticks = fl.read_weekly_ticks().get(cycle, {})
        cells = [label("WEEKLY")]
        for name, times in weekly[:4]:
            hit = wticks.get(name, 0) >= times
            cells += [("plain", "{} ".format(name[:16])), ("green" if hit else "grey", "[x]" if hit else "[ ]"),
                      ("plain", "   ")]
        screen.row(cells)

    if fl.on(fl.load_settings(), "ask_practice"):
        state = practice.load()
        cells = [label("PRACTICE")]
        for name in practice.ORDER:
            cells += [("plain", "{} ".format(name)), ("green", "r{}".format(state[name]["rung"])),
                      ("plain", "   ")]
        total, happened, _ = practice.fear_counts(state)
        if total:
            cells.append(("yellow", "feared {}, happened {}".format(total, happened)))
        screen.row(cells)

    parked = len(fl.read_park())
    if parked:
        screen.row([label("PARKED"), ("yellow", "{} thought{} waiting".format(
            parked, "" if parked == 1 else "s"))])

    screen.line("")
    screen.line("  More:  focus dash all    focus today    focus summary    focus practice", "grey")
    screen.line("")
    screen.flush()


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    if "all" in [arg.lower() for arg in sys.argv[1:]]:
        show_full(screen)
    else:
        show(screen)


if __name__ == "__main__":
    main()
