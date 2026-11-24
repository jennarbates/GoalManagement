# Two quick entries that do not need the guided day:
#   focus done    tick off a task you finished, no pomodoro needed
#   focus extra   record a pomodoro you did away from the script
import focuslib as fl
import matrix

HELP = """
quick.py - quick entries outside the guided day

  focus done     Tick off a task. It lists your open tasks; type a number
                 and the task moves to DONE with today's day number. Its
                 points count toward this cycle. You can also type a
                 one-off thing you did that was never on the list.

  focus extra    Record a pomodoro that happened away from the script
                 (on paper, with a kitchen timer, at the makerspace).
                 It asks what you did and how it went, then adds it to
                 the wall and your milestones.
                 If today's promise is not finished yet, it counts
                 toward the promise. If the promise is already kept, it
                 is logged as an extra on top.

A wrong entry: focus undo.
"""

OPEN = ["DOING", "THIS CYCLE", "BACKLOG - IMPORTANT", "BACKLOG - SOMEDAY"]


def done_main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    day = fl.current_day()
    if not day:
        screen.line("Start your first day with  focus  - finished tasks are dated by focus day.", "grey")
        return
    try:
        while True:
            backlog = fl.load_backlog()
            items = [(section, line) for section in OPEN for line in backlog[section]]
            screen.line("")
            screen.line("== TICK OFF A TASK - D{} ==".format(day), "yellow")
            for number, (section, line) in enumerate(items, 1):
                screen.row([("plain", "  {:>2}. {}".format(number, matrix.strip_box(line))[:66]),
                            ("grey", "  doing" if section == "DOING" else "")])
            if not items:
                screen.line("  no open tasks", "grey")
            pick = fl.ask(screen, "Number of the finished task, or type something else you did (Enter = done):")
            if not pick:
                return
            if pick.isdigit():
                if not 1 <= int(pick) <= len(items):
                    continue
                section, line = items[int(pick) - 1]
                backlog[section].remove(line)
            else:
                line = pick
            backlog["DONE"].append("D{} | {}".format(day, line))
            fl.save_backlog(backlog)
            fl.log(day, "done", "task: " + matrix.strip_box(line))
            points = fl.parse_item(line)["points"]
            screen.line("  Done: {}{}".format(matrix.strip_box(line),
                                              "   (+{} points)".format(points) if points else ""), "green")
    except (KeyboardInterrupt, EOFError):
        pass


def extra_main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    day = fl.current_day()
    days = fl.read_log()
    if not day or day not in days or not days[day]["planned"]:
        screen.line("Start a day with  focus  first - pomodoros are logged against a focus day.", "grey")
        return
    info = days[day]
    try:
        screen.line("")
        screen.line("== A POMODORO DONE AWAY FROM THE SCRIPT - D{} ==".format(day), "yellow")
        what = fl.ask(screen, "What did you work on? (Enter = cancel):")
        if not what:
            return
        focus = fl.ask_int(screen, "How did it go?  3 focused  2 okay  1 scattered:", 1, 3)
        note = fl.ask(screen, "One line on how it went (Enter to skip):")
        counted = sum(1 for kind, _ in fl.day_events(day) if kind.startswith("pomo"))
        if info["did"] is None and counted < info["planned"]:
            numbers = [int(kind.split()[1]) for kind, _ in fl.day_events(day)
                       if kind.startswith("pomo") and kind.split()[1].isdigit()]
            fl.log(day, "pomo {}".format(max(numbers + [0]) + 1), "focus {}".format(focus), "intent: " + what,
                   "note: " + note if note else "", "offscript: yes")
            screen.line("Logged as pomodoro {} of {} for today's promise.".format(
                counted + 1, info["planned"]), "green")
            if counted + 1 >= info["planned"]:
                screen.line("That completes the promise. Type  focus end  to close the day.", "green")
        else:
            fl.log(day, "extra", "focus {}".format(focus), "intent: " + what,
                   "note: " + note if note else "")
            screen.line("Logged as an extra, on top of today's promise.", "green")
            screen.line("It is on your wall. The promise itself stays as it was.", "grey")
    except (KeyboardInterrupt, EOFError):
        pass
