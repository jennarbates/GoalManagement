# One file that tells Claude how the system is doing: versions, settings,
# usage, errors, your feedback and the recent log.
# Run:  focus diagnose      (writes diagnose.txt)
import os
import platform
import sys

import focuslib as fl
import report
import rewards

HELP = """
diagnose.py - a check-up file to bring back to Claude

  focus diagnose          writes diagnose.txt and shows a short summary
  focus feedback          add a note about the system itself
  focus feedback the chart is too tall

diagnose.txt gathers, in one place: the script version, the Python
version, your settings, how many days and pomodoros are logged, how
long the daily questions take you, which commands you run, which
optional questions you skip, any crashes (from errors.txt), your
feedback notes, and the last 60 lines of the log.
focus backup copies it to the USB stick with everything else.
"""


class Collector(object):
    """Stands in for the screen and keeps the text."""
    mode = "plain"

    def __init__(self):
        self.lines = []

    def row(self, segments):
        self.lines.append("".join(text for _, text in segments).rstrip())

    def line(self, text="", color=None):
        self.lines.append(text.rstrip())

    def flush(self):
        pass


def tail(name, count):
    lines = [line for line in fl.read_lines(name) if line.strip()]
    return lines[-count:]


def build():
    out = []
    add = out.append
    days = fl.read_log()
    add("FOCUS SYSTEM CHECK-UP")
    add("script version   {}".format(fl.VERSION))
    add("python           {} on {}".format(sys.version.split()[0], platform.platform()))
    add("screen mode      {}".format(fl.Screen(fl.load_settings()["display"]).mode))
    add("")
    add("SETTINGS")
    for line in fl.read_lines("settings.txt"):
        if line.strip() and not line.strip().startswith("#"):
            add("  " + line.strip())
    add("")
    add("FILES")
    for name in sorted(os.listdir(fl.HERE)):
        full = os.path.join(fl.HERE, name)
        if os.path.isfile(full) and not name.startswith("."):
            add("  {:<16} {:>7} bytes".format(name, os.path.getsize(full)))
    add("")

    closed = [d for d in days.values() if d["did"] is not None]
    focus = [f for d in days.values() for f in d["focus"]]
    abandoned = setup = runs = 0
    setups, plans = [], []
    for day in days:
        for kind, fields in fl.day_events(day):
            if kind == "abandoned":
                abandoned += 1
            elif kind == "timing" and fields.get("setup", "").isdigit():
                setups.append(int(fields["setup"]))
            elif kind == "start":
                plans.append("D{} energy {} plan {}".format(day, fields.get("energy", "?"),
                                                            fields.get("plan", "?")))
    add("NUMBERS")
    add("  focus days started      {}".format(len([d for d in days.values() if d["planned"]])))
    add("  days finished           {}".format(len(closed)))
    add("  days left open          {}".format(
        len([d for d in days.values() if d["planned"] and d["did"] is None])))
    add("  pomodoros done          {}".format(len(focus)))
    add("  pomodoros abandoned     {}".format(abandoned))
    if focus:
        add("  average focus           {:.1f} of 3".format(sum(focus) / float(len(focus))))
    if setups:
        add("  setup questions take    {} s on average, {} s at most".format(
            sum(setups) // len(setups), max(setups)))
    add("  parked thoughts waiting {}".format(len(fl.read_park())))
    add("  routines / rewards      {} / {}".format(len(fl.load_routines()),
                                                   len(rewards.load())))
    add("  energy and promise by day:")
    for text in plans[-14:]:
        add("    " + text)
    add("")

    counts = {}
    for line in fl.read_lines("usage.txt"):
        parts = line.split()
        if len(parts) >= 2:
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    add("COMMANDS RUN")
    for name in sorted(counts, key=lambda n: -counts[n]):
        add("  {:<12} {}".format(name, counts[name]))
    if not counts:
        add("  none recorded yet")
    add("")

    collector = Collector()
    report.show(collector, "all")
    out.extend(collector.lines)

    add("ERRORS (errors.txt, most recent last)")
    errors = fl.read_lines("errors.txt")
    out.extend(("  " + line) for line in errors[-45:]) if errors else add("  none")
    add("")
    add("YOUR FEEDBACK (feedback.txt)")
    notes = tail("feedback.txt", 200)
    out.extend(("  " + line) for line in notes) if notes else add("  none yet - add with: focus feedback")
    add("")
    add("LAST 60 LOG LINES")
    out.extend(("  " + line) for line in tail("log.txt", 60))
    return out


def feedback_main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    words = [arg for arg in sys.argv[1:] if arg.lower() != "feedback"]
    try:
        text = fl.clean(" ".join(words)) or fl.ask(
            screen, "What should change, or what is working well? (Enter = cancel):")
    except (KeyboardInterrupt, EOFError):
        return
    if text:
        fl.feedback(text)
        screen.line("Saved in feedback.txt.", "green")


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    lines = build()
    fl.write_lines("diagnose.txt", lines)
    for line in lines:
        if line.startswith("WHAT YOU USE") or line.strip().startswith("WHAT YOU USE"):
            break
        screen.line(line)
    screen.line("The full check-up is in diagnose.txt ({} lines).".format(len(lines)), "green")
    screen.line("Run  focus backup  and bring the stick to the Mac to show Claude.", "grey")


if __name__ == "__main__":
    main()
