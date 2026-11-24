# The guided day. It asks questions, runs the timers and writes the files.
# Run in the Cygwin terminal:
#     cd /cygdrive/c/focus
#     python day.py
import appts
import time

import backup
import celebrate
import dash
import focuslib as fl
import matrix
import points
import pomo
import practice
import report
import rewards
import routines
import today


WORK_COLORS = ["yellow", "cyan", "magenta"]
TODAY = {"day": 1}


def look_for(settings, day):
    """Timer design and work colour for this day (they rotate for novelty)."""
    style = settings["style"]
    if style == "rotate":
        style = pomo.STYLES[day % len(pomo.STYLES)]
    color = "yellow"
    if settings.get("colours", "rotate") != "fixed":
        color = WORK_COLORS[day % len(WORK_COLORS)]
    return style, color


def heading(screen, text):
    screen.line("")
    screen.line("== {} ==".format(text), "yellow")


def show_items(screen, lines):
    for i, line in enumerate(lines, 1):
        screen.line("  {:>2}. {}".format(i, line))


# ------------------------------------------------------------ adding tasks

def categories(backlog):
    """Category words already used in the backlog, in alphabetical order."""
    counts = {}
    for section in fl.SECTIONS:
        for line in backlog[section]:
            for tag in fl.parse_item(line)["tags"]:
                counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts)


def ask_category(screen, backlog):
    """Pick an existing category by number, type a new one, or skip."""
    known = categories(backlog)
    if known:
        screen.line("  Your categories:", "bold")
        for start in range(0, len(known), 4):
            screen.line("    " + "".join("{:>2} {:<15}".format(i + 1, known[i][:15])
                                         for i in range(start, min(start + 4, len(known)))))
        answer = fl.ask(screen, "  Category - a number, a new word, or Enter for none:")
    else:
        answer = fl.ask(screen, "  Category? One word like hsk or cs311 (Enter = none):")
    if answer.isdigit() and 1 <= int(answer) <= len(known):
        return known[int(answer) - 1]
    words = answer.lstrip("#").split()
    return words[0].lower() if words else ""


def capture(screen, backlog, text):
    """Sort one new task with the Eisenhower questions, size it, file it."""
    screen.line("  First, WHEN to do it - two questions put it in a box on the chart:", "grey")
    urgent = fl.ask_yes(screen, "  Is it urgent (a real deadline soon)?", False)
    important = fl.ask_yes(screen, "  Is it important (moves a goal you care about)?", True)
    if not urgent and not important:
        screen.line("  Box 4: not urgent, not important. Dropped - not added.", "grey")
        return
    screen.line("")
    screen.line("  Now, HOW BIG it is - points. They do not change its priority;", "grey")
    screen.line("  they only show how much fits in a cycle.", "grey")
    size = points.estimate(screen)
    if size == 8:
        screen.line("  8 points is too big to finish. Add it, but split it before starting.", "yellow")
    tag = ask_category(screen, backlog)
    line = "[{}] {}".format(size, text)
    if tag:
        line += " #" + tag
    if urgent:
        screen.line("  Deadlines count focus days (days you run this), not calendar days.", "grey")
        due = fl.ask(screen, "  Due in how many focus days? (Enter = no deadline):")
        if due.isdigit():
            line += " @D{}".format(TODAY["day"] + int(due))
    line += " (B{})".format(1 if urgent and important else 2 if important else 3)
    if urgent and important:
        backlog["THIS CYCLE"].insert(0, line)
        where = "Box 1 (do first) -> top of THIS CYCLE"
    elif important:
        backlog["BACKLOG - IMPORTANT"].append(line)
        where = "Box 2 (the real work) -> BACKLOG - IMPORTANT"
    else:
        backlog["BACKLOG - SOMEDAY"].append(line)
        where = "Box 3 (urgent, not important) -> BACKLOG - SOMEDAY"
    fl.save_backlog(backlog)
    screen.line("  Added: {}".format(line), "green")
    screen.line("  {}".format(where), "grey")


def capture_loop(screen, backlog, prompt):
    while True:
        text = fl.ask(screen, prompt)
        if not text:
            return
        capture(screen, backlog, text)
        prompt = "Another new task? (Enter = no more):"


# ----------------------------------------------------------- cycle planning

def plan_cycle(screen, backlog, cycle):
    heading(screen, "NEW CYCLE {} - planning".format(cycle))
    screen.line("Get everything that is on your mind into the backlog first.")
    screen.line("For each task it asks urgent? and important? - that is the four boxes.", "grey")
    past = fl.done_points_by_cycle(backlog)
    recent = [past[c] for c in sorted(past) if c < cycle][-3:]
    if recent:
        capacity = max(1, int(round(sum(recent) / float(len(recent)))))
        screen.line("Your recent velocity is about {} points per cycle.".format(capacity))
    else:
        capacity = 9
        screen.line("No history yet, so aim for 8 to 10 points this cycle.")

    left = backlog["THIS CYCLE"]
    if left:
        screen.line("")
        screen.line("Left over from last cycle:")
        show_items(screen, left)
        if fl.ask_yes(screen, "Return these to the backlog and choose again from scratch?"):
            backlog["BACKLOG - IMPORTANT"] = left + backlog["BACKLOG - IMPORTANT"]
            backlog["THIS CYCLE"] = []
            fl.save_backlog(backlog)

    capture_loop(screen, backlog, "A new task to add? (Enter = none):")
    matrix.walk(screen, backlog)

    while backlog["BACKLOG - IMPORTANT"]:
        load = fl.points_of(backlog["DOING"]) + fl.points_of(backlog["THIS CYCLE"])
        screen.line("")
        screen.row([("bold", "  THIS CYCLE  ")] + dash.bar(load, capacity) +
                   [("plain", "  {} of about {} points".format(load, capacity))])
        if load >= capacity:
            screen.line("  That is a full cycle. Stop adding.", "yellow")
        screen.line("  BACKLOG - IMPORTANT:")
        show_items(screen, backlog["BACKLOG - IMPORTANT"])
        pick = fl.ask(screen, "Number to pull into this cycle (Enter = done):")
        if not pick:
            break
        if pick.isdigit() and 1 <= int(pick) <= len(backlog["BACKLOG - IMPORTANT"]):
            backlog["THIS CYCLE"].append(backlog["BACKLOG - IMPORTANT"].pop(int(pick) - 1))
            fl.save_backlog(backlog)


def plan_practice(screen, settings, day):
    if fl.on(settings, "ask_practice"):
        practice.cycle_plan(screen, day)


def review_cycle(screen, backlog, day, cycle):
    heading(screen, "CYCLE {} REVIEW".format(cycle))
    total = fl.done_points_by_cycle(backlog).get(cycle, 0)
    dash.banner(screen, "CYCLE {} COMPLETE - {} POINTS".format(cycle, total))
    dash.show_summary(screen, cycle)
    report.show(screen, cycle)
    worked = fl.ask(screen, "What worked well this cycle?")
    blocked = fl.ask(screen, "What got in the way?")
    change = fl.ask(screen, "One thing to change next cycle?")
    about = fl.ask(screen, "Anything about this system itself to fix or change? (saved for Claude):")
    if about:
        fl.feedback(about)
    fl.log(day, "review", "CYCLE {} DONE - {} points".format(cycle, total),
           "worked: " + worked if worked else "",
           "blocked: " + blocked if blocked else "", "change: " + change if change else "")
    if fl.ask_yes(screen, "Back up C:\\focus to the USB stick now?"):
        backup.run(screen)


# ------------------------------------------------------------------ the day

def pick_day(screen, days):
    """Return (day number, True if continuing a day already started)."""
    if not days:
        screen.line("This is your first focus day: D1.", "bold")
        screen.line("Focus days are counted here, so it does not matter which", "grey")
        screen.line("workbook page you are on - start anywhere.", "grey")
        return 1, False
    last = max(days)
    if days[last]["did"] is None:
        if fl.pomo_count(last) >= (days[last]["planned"] or 0):
            screen.line("D{}: every promised pomodoro is done, but the day was never closed.".format(last))
            if fl.ask_yes(screen, "Close D{} now?".format(last)):
                return last, True
        elif fl.ask_yes(screen, "D{} was started but not closed. Continue it?".format(last)):
            return last, True
        if not fl.ask_yes(screen, "Leave D{} unfinished and start D{}?".format(last, last + 1), False):
            return None, False
        return last + 1, False
    screen.line("D{} is finished.".format(last), "green")
    if fl.ask_yes(screen, "Is this a new day? Start D{}?".format(last + 1), False):
        return last + 1, False
    return None, False


def usual_plan(days):
    """The number promised on the most recent finished day that was not a low day."""
    for day in sorted(days, reverse=True):
        info = days[day]
        if info["did"] is not None and info["energy"] != 1 and info["planned"]:
            return info["planned"]
    return 2


def sort_parking_lot(screen, backlog):
    """End of day: every parked thought is added to the backlog, dropped or kept."""
    items = fl.read_park()
    if not items:
        return
    heading(screen, "PARKING LOT - {} parked".format(len(items)))
    kept = []
    for text in items:
        screen.line("  " + text, "bold")
        answer = fl.ask(screen, "  a = add to backlog, d = drop, k = keep parked (Enter = k):").lower()
        if answer.startswith("a"):
            capture(screen, backlog, text)
        elif answer.startswith("d"):
            screen.line("  Dropped.", "grey")
        else:
            kept.append(text)
    fl.write_park(kept)


def pick_must(screen, backlog):
    if backlog["DOING"]:
        current = backlog["DOING"][0]
        screen.line("Still in DOING: {}".format(current), "bold")
        if fl.ask_yes(screen, "Keep it as today's MUST?"):
            return current
        backlog["THIS CYCLE"] = backlog["DOING"] + backlog["THIS CYCLE"]
        backlog["DOING"] = []
    while True:
        source = "THIS CYCLE" if backlog["THIS CYCLE"] else "BACKLOG - IMPORTANT"
        choices = backlog[source]
        if choices:
            screen.line("{}:".format(source))
            show_items(screen, choices)
            pick = fl.ask(screen, "Today's MUST - a number, p = pick for me, or type a new task:")
        else:
            pick = fl.ask(screen, "The backlog is empty. Type today's MUST:")
        if pick.lower() == "p" and choices:
            must = choices.pop(0)
            screen.line("Picked for you: {}".format(must), "green")
        elif pick.isdigit() and 1 <= int(pick) <= len(choices):
            must = choices.pop(int(pick) - 1)
        elif pick and not pick.isdigit():
            must = pick
        else:
            continue
        backlog["DOING"] = [must]
        fl.save_backlog(backlog)
        return must


def write_today(day, workbook, planned, must, next_note=""):
    fl.write_lines("today.txt", [
        "DAY:    D{}{}".format(day, "  (workbook: {})".format(workbook) if workbook else ""),
        "PLAN:   {} pomodoros".format(planned),
        "MUST:   {}".format(must),
        "",
        "NEXT:   {}".format(next_note),
    ])


def read_today(key):
    for line in fl.read_lines("today.txt"):
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def run_pomodoros(screen, settings, day, planned, first, must, workbook):
    style, color = look_for(settings, day)
    chime = settings.get("chime", "on") != "off"
    width = int(fl.number(settings, "width", 78))
    n = first
    while n <= planned:
        heading(screen, "POMODORO {} of {}".format(n, planned))
        if appts.one_line(day):
            screen.line("  " + appts.one_line(day)[:76], "cyan")
        screen.row([("bold", "  TODAY  ")] + dash.today_row(n - 1, planned))
        intent = fl.ask_required(screen, "What exactly will you do in this one?")
        first = ""
        if fl.on(settings, "ask_first"):
            first = fl.ask(screen, "The first two-minute action? (Enter to skip):")
        showing = "{}   (first: {})".format(intent, first) if first else intent
        screen.line("Stray thought mid-way? Type it into park.txt in Notepad++ and carry on.", "grey")
        fl.ask(screen, "Press Enter to start. One task only until the beep.")
        pomo.run(screen, fl.number(settings, "work", 25),
                 "WORK {} of {}".format(n, planned), showing, "work", style, width,
                 color, chime)

        screen.clear()
        screen.line("Time. Stop mid-sentence.", "yellow")
        screen.line("You said: {}".format(intent), "grey")
        focus = fl.ask_int(screen, "How did it go?  3 focused  2 okay  1 scattered  0 abandoned:", 0, 3)
        if focus == 0:
            fl.log(day, "abandoned", "pomo {}".format(n), "intent: " + intent)
            screen.line("That one does not count. No penalty - start it again.", "yellow")
            continue
        note = next_note = stray = ""
        if fl.on(settings, "ask_note"):
            note = fl.ask(screen, "One line on how it went (Enter to skip):")
        if fl.on(settings, "ask_next"):
            next_note = fl.ask(screen, "NEXT - what were you about to do? (Enter to skip):")
        if fl.on(settings, "ask_stray"):
            stray = fl.ask(screen, "Any stray thought to park for later? (Enter = none):")
        if stray:
            fl.park(stray)
        fl.log(day, "pomo {}".format(n), "focus {}".format(focus), "intent: " + intent,
               "first: " + first if first else "",
               "note: " + note if note else "", "next: " + next_note if next_note else "",
               "parked: yes" if stray else "")
        if next_note:
            write_today(day, workbook, planned, must, next_note)
        screen.row([("bold", "  TODAY  ")] + dash.today_row(n, planned))
        total = dash.total_pomodoros()
        if total in dash.MILESTONES:
            dash.banner(screen, "FIRST POMODORO DONE" if total == 1
                        else "{} POMODOROS DONE".format(total))

        if n < planned:
            long_break = n % 4 == 0
            heading(screen, "LONG BREAK" if long_break else "BREAK")
            plan = fl.ask(screen, "What will you do away from the screen? (Enter = stand up, water):",
                          "stand up, water")
            fl.ask(screen, "Press Enter, then leave the laptop until the beep.")
            pomo.run(screen, fl.number(settings, "long" if long_break else "short", 5),
                     "BREAK", plan, "break", style, width)
            screen.clear()
            away = fl.ask_yes(screen, "Break over. Did you actually step away from the laptop?")
            rest = ""
            if fl.on(settings, "ask_break_note"):
                rest = fl.ask(screen, "How was the break? (Enter to skip):")
            fl.log(day, "break {}".format(n), "away {}".format("y" if away else "n"),
                   "intent: " + plan, "note: " + rest if rest else "")
        n += 1


def close_day(screen, settings, day, planned, did, must, started=None):
    """Everything that happens when a day ends, kept promise or not."""
    cycle, position = fl.cycle_of(day)
    heading(screen, "DONE FOR TODAY")
    fl.log(day, "end", "planned {}, did {}".format(planned, did))
    if did >= planned:
        if settings.get("celebrate", "on") != "off":
            celebrate.run(screen, day, int(fl.number(settings, "width", 78)))
        screen.line("Planned {}, did {}. Promise kept.".format(planned, did), "green")
    else:
        screen.line("Planned {}, did {}. Ended early, and logged honestly.".format(planned, did), "yellow")
        screen.line("The next day is a new promise. Make it one you will keep.", "grey")
    backlog = fl.load_backlog()
    if must and "D{} | {}".format(day, must) in backlog["DONE"]:
        screen.line("Your MUST is already ticked off: {}".format(matrix.strip_box(must)), "green")
    elif must and must in backlog["DOING"] and fl.ask_yes(
            screen, "Did you finish: {} ?".format(matrix.strip_box(must)), False):
        backlog["DOING"].remove(must)
        backlog["DONE"].append("D{} | {}".format(day, must))
        fl.save_backlog(backlog)
        screen.line("Moved to DONE.", "green")
    elif must and must in backlog["DOING"]:
        screen.line("It stays in DOING for next time.", "grey")
    if routines.any_routines():
        routines.check(screen, day, allow_add=False)
    if fl.on(settings, "ask_practice"):
        practice.end_of_day(screen, day)
    sort_parking_lot(screen, backlog)
    if position == fl.CYCLE_DAYS:
        review_cycle(screen, backlog, day, cycle)

    today.show(screen, day)
    fl.ask(screen, "That was today. Press Enter for the big picture.")
    dash.show(screen, day)
    if fl.on(settings, "ask_reward") and did >= planned:
        rewards.offer(screen, day)
    if started is not None:
        fl.log(day, "timing", "run {}".format(int(time.time() - started)))
    screen.line("That is the day. Close the laptop.", "bold")


def repair_finished_days(screen, days, skip=None):
    """Close days where every promised pomodoro was done but the day was never ended."""
    for day in sorted(days):
        info = days[day]
        if day != skip and info["planned"] and info["did"] is None \
                and fl.pomo_count(day) >= info["planned"]:
            fl.log(day, "end", "planned {}, did {}".format(info["planned"], info["planned"]))
            screen.line("D{} had all {} pomodoros done but was never closed. Closed it: promise kept.".format(
                day, info["planned"]), "green")


def end_main():
    """focus end: close the current day without running more pomodoros."""
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    settings = fl.load_settings()
    screen = fl.Screen(settings["display"])
    try:
        days = fl.read_log()
        if not days:
            screen.line("No day has been started yet. Type  focus  to begin.", "grey")
            return
        day = max(days)
        repair_finished_days(screen, days, skip=day)
        info = days[day]
        if not info["planned"] or info["did"] is not None:
            screen.line("D{} is already finished. There is nothing to end.".format(day), "grey")
            return
        planned, did = info["planned"], fl.pomo_count(day)
        if did < planned:
            screen.line("D{}: you promised {} and have done {}.".format(day, planned, did), "yellow")
            if not fl.ask_yes(screen, "End the day here anyway?", False):
                screen.line("Not ended. Type  focus  to carry on with it.", "grey")
                return
        TODAY["day"] = day
        backlog = fl.load_backlog()
        must = read_today("MUST") or (backlog["DOING"][0] if backlog["DOING"] else "")
        close_day(screen, settings, day, planned, min(did, planned), must)
    except (KeyboardInterrupt, EOFError):
        screen.cursor(True)
        screen.color("plain")
        screen.line("")
        screen.line("Stopped. Anything already answered is saved.", "yellow")


def run(screen, settings):
    started = time.time()
    screen.clear()
    days = fl.read_log()
    backlog = fl.load_backlog()
    if days:
        repair_finished_days(screen, days, skip=max(days))
        days = fl.read_log()
    if days and days[max(days)]["did"] is None:
        today.show(screen, max(days))
    elif days:
        dash.show(screen)
    day, resumed = pick_day(screen, days)
    if day is None:
        today.show(screen, max(days))
        screen.line("  Nothing new was started. D{} stays as it is.".format(max(days)), "grey")
        return
    TODAY["day"] = day
    cycle, position = fl.cycle_of(day)

    if resumed:
        planned = days[day]["planned"] or 2
        done = fl.pomo_count(day)
        must = read_today("MUST") or (backlog["DOING"][0] if backlog["DOING"] else "")
        workbook = ""
        screen.line("Continuing D{}: {} of {} pomodoros done.".format(day, done, planned))
    else:
        workbook = ""
        if fl.on(settings, "ask_workbook"):
            workbook = fl.ask(screen, "Which workbook day or page are you on? (Enter to skip):")
        if fl.on(settings, "ask_appointments"):
            appts.ask(screen, day)
        if position == 1:
            plan_cycle(screen, backlog, cycle)
            plan_practice(screen, settings, day)
        else:
            capture_loop(screen, backlog, "Anything new to capture in the backlog? (Enter = no):")
            matrix.walk(screen, backlog)

        heading(screen, "TODAY - D{} (cycle {}, day {} of {})".format(day, cycle, position, fl.CYCLE_DAYS))
        last_next = read_today("NEXT")
        if last_next:
            screen.line("Last time you left yourself this note:")
            screen.line("  NEXT: {}".format(last_next), "green")
        must = pick_must(screen, backlog)
        energy = fl.ask_int(screen, "Energy right now?  1 low  2 normal  3 high  (Enter = 2):", 1, 3, 2)
        suggest = 1 if energy == 1 else usual_plan(days)
        if energy == 1:
            screen.line("Low day. One pomodoro kept is a full win.", "green")
        elif energy == 3:
            screen.line("High energy - keep your usual number anyway. The cap protects you.", "grey")
        screen.line("Promise a number you will actually do. Doing more breaks it too.", "grey")
        planned = fl.ask_int(screen, "How many pomodoros today? (Enter = {}):".format(suggest),
                             1, 8, suggest)
        names = dict((str(i), name) for i, name in enumerate(pomo.STYLES, 1))
        names["s"] = "rotate"
        choices = ["{} {}".format(i, name) for i, name in enumerate(pomo.STYLES, 1)] + ["s surprise me"]
        for start in range(0, len(choices), 5):
            screen.line("    " + "".join("{:<14}".format(c) for c in choices[start:start + 5]), "grey")
        choice = fl.ask(screen, "Which timer? (Enter = {}):".format(
            "surprise me" if settings["style"] == "rotate" else settings["style"])).lower()
        if choice in names:
            settings["style"] = names[choice]
            fl.save_setting("style", settings["style"])
        write_today(day, workbook, planned, must)
        fl.log(day, "start", "plan {}".format(planned), "energy {}".format(energy), "must: " + must,
               "workbook: " + workbook if workbook else "")
        done = 0
        if routines.any_routines():
            screen.line("")
            screen.line("Tick any routine you have already done today.", "grey")
            routines.check(screen, day, allow_add=False)

    if not resumed:
        fl.log(day, "timing", "setup {}".format(int(time.time() - started)))
    run_pomodoros(screen, settings, day, planned, done + 1, must, workbook)

    close_day(screen, settings, day, planned, planned, must, started)


HELP = """
day.py - the guided focus day

  python day.py

It asks the questions and writes the files for you, in this order:
  1. Shows the dashboard and counts the focus day (D1, D2, ...).
     It has no clock: a new day starts only when you answer y to
     "Is this a new day?". An unfinished day is offered to continue.
  2. Day 1 of a 7-day cycle: cycle planning. Other days: anything new
     for the backlog?
     Then the Eisenhower chart: every open task in its box. Type a
     number to re-sort one, or Enter if the chart is right.
     Before that, on every day: anything fixed today, with its time
     (a work shift, the vet). Those show at the top of the day page.
  3. Today's MUST (a number, p = pick for me, or type a new task).
  4. Energy 1-3, then how many pomodoros you promise.
     Then the routines checklist (shower, meals ...): tick what is done.
     It comes back at the end of the day.
  5. Each pomodoro: what you will do, the first two-minute action,
     the timer, then how it went (3 focused, 2 okay, 1 scattered,
     0 abandoned = does not count), a NEXT note, a stray thought to park.
  6. Each break: what you will do away from the screen, the timer,
     then whether you really stepped away.
  7. Stops at the promised number, sorts the parking lot, shows the
     dashboard. Day 7 of a cycle adds a short review.

On day 1 of a cycle it offers to plan one practice rep per ladder, and
each day ends by asking whether you did one (focus practice).
The day ends with a reward from your menu (focus reward).
Questions you always skip can be switched off: see  focus report .
focus end closes the day at any point, without more pomodoros. If you
stop short it logs that honestly ("planned 4, did 2").
Enter accepts the suggestion shown in brackets.
Ctrl+C stops; run it again and it offers to continue the same day.
"""

def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    settings = fl.load_settings()
    screen = fl.Screen(settings["display"])
    try:
        run(screen, settings)
    except (KeyboardInterrupt, EOFError):
        screen.cursor(True)
        screen.color("plain")
        screen.line("")
        screen.line("Stopped. Everything already answered is saved in log.txt.", "yellow")
        screen.line("Run  python day.py  again to continue this day.", "grey")


if __name__ == "__main__":
    main()
