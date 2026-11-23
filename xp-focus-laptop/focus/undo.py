# Take back a mistake: the last line of the log, or the last finished task.
# Run:  focus undo      (or: python undo.py)
import focuslib as fl

HELP = """
undo.py - take back a mistake

  focus undo

  1  removes the last line of log.txt (shown first). Repeat to go further
     back. Removing a day's "end" line reopens that day.
  2  moves the last finished task from DONE back to DOING.
For anything else, edit log.txt or backlog.txt by hand in Notepad++.
"""


def run(screen):
    while True:
        lines = fl.read_lines("log.txt")
        while lines and not lines[-1].strip():
            lines.pop()
        backlog = fl.load_backlog()
        last_log = lines[-1] if lines and lines[-1].startswith("D") else None
        last_done = backlog["DONE"][-1] if backlog["DONE"] else None
        screen.line("")
        screen.line("  1  remove the last log line:", "bold")
        screen.line("       {}".format(last_log or "(nothing to remove)"), "grey")
        screen.line("  2  move the last finished task back to DOING:", "bold")
        screen.line("       {}".format(last_done or "(nothing finished yet)"), "grey")
        choice = fl.ask(screen, "1, 2, or Enter to finish:")
        if choice == "1" and last_log:
            fl.write_lines("log.txt", lines[:-1])
            screen.line("  Removed.", "green")
        elif choice == "2" and last_done:
            backlog["DONE"].pop()
            task = last_done.split("|", 1)[1].strip() if fl.parse_item(last_done)["day"] else last_done
            backlog["THIS CYCLE"] = backlog["DOING"] + backlog["THIS CYCLE"]
            backlog["DOING"] = [task]
            fl.save_backlog(backlog)
            screen.line("  Back in DOING: {}".format(task), "green")
        elif not choice:
            return


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    try:
        run(fl.Screen(fl.load_settings()["display"]))
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
