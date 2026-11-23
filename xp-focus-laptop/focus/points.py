# Suggests story points for a task from four questions.
# Run by itself:  python points.py     (day.py also uses it)
import focuslib as fl

QUESTIONS = [
    ("How long will it take?  (1 session = 2 pomodoros, about 50 min)",
     [("less than half a session", 0), ("about one session", 1),
      ("two or three sessions", 3), ("more than that", 5)]),
    ("Have I done this kind of thing before?",
     [("yes, this exact kind", 0), ("something similar", 1), ("never", 2)]),
    ("Do I know the first step and what done looks like?",
     [("both", 0), ("only one", 1), ("neither", 2)]),
    ("Does it need something else first?",
     [("no", 0), ("yes", 1)]),
]


def to_points(score):
    if score == 0:
        return 1
    if score <= 2:
        return 2
    if score <= 4:
        return 3
    if score <= 6:
        return 5
    return 8


def estimate(screen):
    score = 0
    for question, options in QUESTIONS:
        screen.line("")
        screen.line("  " + question, "bold")
        for i, (text, _) in enumerate(options, 1):
            screen.line("    {}. {}".format(i, text))
        choice = fl.ask_int(screen, "  >", 1, len(options))
        score += options[choice - 1][1]
    return to_points(score)


HELP = """
points.py - suggest story points for one task

  python points.py

Asks for the task and four questions, then prints a line such as
  [3] write linked list in C
Sizes are 1, 2, 3, 5 or 8. The anchor is "re-solve one LeetCode
problem" = 2 points. 8 means too big: split it first.
Nothing is saved; day.py does this for you when you add a task.
"""

def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    try:
        task = fl.ask_required(screen, "Task:")
        points = estimate(screen)
        screen.line("")
        screen.line("[{}] {}".format(points, task), "green")
        if points == 8:
            screen.line("Too big - split it into smaller tasks first.", "yellow")
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
