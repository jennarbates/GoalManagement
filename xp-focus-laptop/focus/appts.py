# Appointments: fixed things at fixed times today (work, the vet, a class).
# Run:  focus appt
import focuslib as fl

HELP = """
appts.py - today's appointments

  focus appt

Fixed things at fixed times: a work shift, the vet, a class. They are not
tasks (no points, no boxes) - they are the shape of the day that the
pomodoros have to fit around. day.py asks for them at the start of each
day; this command shows today's and lets you add more.
Type each with its time, for example:   2pm-6pm work at the makerspace
This laptop has no clock and cannot remind you: set a phone alarm.
A wrong entry: focus undo.
"""


def rows(day):
    """Rows for the day page."""
    out = []
    for i, text in enumerate(fl.read_appts().get(day, [])):
        out.append([("bold", "  {:<12}".format("FIXED TODAY" if i == 0 else "")), ("cyan", text[:62])])
    return out


def one_line(day):
    items = fl.read_appts().get(day, [])
    return "Fixed today: " + ";  ".join(items) if items else ""


def ask(screen, day):
    """Collect today's appointments, one per line."""
    added = 0
    prompt = "Anything fixed today, with its time? Like: 2pm-6pm work (Enter = nothing):"
    while True:
        text = fl.ask(screen, prompt)
        if not text:
            break
        fl.log(day, "appt", text)
        added += 1
        prompt = "Another fixed thing today? (Enter = no more):"
    if added:
        screen.line("Set a phone alarm for each one - this laptop cannot remind you.", "yellow")
    return added


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    days = fl.read_log()
    if not days:
        screen.line("Start your first day with  focus  - appointments belong to a focus day.", "grey")
        return
    day = max(days)
    screen.line("")
    screen.line("== FIXED TODAY - D{} ==".format(day), "yellow")
    items = fl.read_appts().get(day, [])
    for text in items:
        screen.line("  " + text, "cyan")
    if not items:
        screen.line("  nothing yet", "grey")
    try:
        ask(screen, day)
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
