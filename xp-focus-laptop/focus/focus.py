# One word for everything:  focus, focus dash, focus undo ...
# Set it up once in the Cygwin terminal:
#     echo "alias focus='python C:/focus/focus.py'" >> ~/.bashrc
# then close and reopen the terminal.
import sys
import traceback

import appts
import backup
import celebrate
import dash
import day
import diagnose
import focuslib as fl
import matrix
import points
import pomo
import report
import rewards
import routines
import today
import undo

HELP = """
focus - the whole focus system behind one word
"""

COMMANDS = {
    "day": day.main, "dash": dash.main, "summary": dash.summary_main,
    "pomo": pomo.main, "points": points.main, "undo": undo.main,
    "backup": backup.main, "matrix": matrix.main, "today": today.main,
    "celebrate": celebrate.main, "check": routines.main,
    "appt": appts.main, "reward": rewards.main, "report": report.main,
    "diagnose": diagnose.main, "feedback": diagnose.feedback_main,
}


def inbox(filename):
    """Add notes fetched from the PSPi (one per line) to the parking lot."""
    try:
        with open(filename, encoding="utf-8", errors="replace") as handle:
            notes = [fl.clean(line) for line in handle]
    except IOError:
        sys.stdout.write("Could not read the fetched notes.\n")
        return
    notes = [note for note in notes if note]
    for note in notes:
        fl.park(note)
    if notes:
        sys.stdout.write("{} note{} added to the parking lot (park.txt):\n".format(
            len(notes), "" if len(notes) == 1 else "s"))
        for note in notes:
            sys.stdout.write("  - {}\n".format(note))
    else:
        sys.stdout.write("No notes waiting on the PSPi.\n")


def main():
    """Run the command; record it, and save any crash to errors.txt."""
    name = sys.argv[1].lower() if len(sys.argv) > 1 else "day"
    if name not in ("inbox", "help", "--help", "-h", "/?"):
        fl.append_line("usage.txt", "D{} {}".format(fl.current_day(), name))
    try:
        dispatch()
    except (KeyboardInterrupt, EOFError, SystemExit):
        raise
    except Exception:
        fl.append_line("errors.txt", "--- D{} | focus {} | version {} | python {}".format(
            fl.current_day(), " ".join(sys.argv[1:]), fl.VERSION, sys.version.split()[0]))
        fl.append_line("errors.txt", traceback.format_exc().rstrip())
        sys.stdout.write("\033[0m\n\nSomething went wrong inside the script (a bug, not you).\n"
                         "The details are saved in errors.txt - show that file to Claude.\n"
                         "Everything you had already answered is saved. Try  focus  again.\n")


def dispatch():
    args = sys.argv[1:]
    if not args:
        day.main()
    elif args[0].lower() in ("help", "--help", "-h", "/?"):
        sys.stdout.write(HELP.strip("\n") + "\n" + fl.COMMANDS)
    elif args[0].lower() == "inbox" and len(args) > 1:
        fl.fix_streams()
        inbox(args[1])
    elif args[0].lower() == "sync":
        sys.stdout.write("focus sync needs the updated launcher. Run once:\n"
                         "  cp /cygdrive/c/focus/focus.sh /usr/bin/focus && chmod +x /usr/bin/focus\n")
    elif args[0].lower() in COMMANDS:
        COMMANDS[args[0].lower()]()
    else:
        sys.stdout.write("Unknown command: {}\n".format(args[0]) + fl.COMMANDS)


if __name__ == "__main__":
    main()
