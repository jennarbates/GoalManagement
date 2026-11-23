# One word for everything:  focus, focus dash, focus undo ...
# Set it up once in the Cygwin terminal:
#     echo "alias focus='python C:/focus/focus.py'" >> ~/.bashrc
# then close and reopen the terminal.
import sys

import backup
import celebrate
import dash
import day
import focuslib as fl
import matrix
import points
import pomo
import today
import undo

HELP = """
focus - the whole focus system behind one word
"""

COMMANDS = {
    "day": day.main, "dash": dash.main, "summary": dash.summary_main,
    "pomo": pomo.main, "points": points.main, "undo": undo.main,
    "backup": backup.main, "matrix": matrix.main, "today": today.main,
    "celebrate": celebrate.main,
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
