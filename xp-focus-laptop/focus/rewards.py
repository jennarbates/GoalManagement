# Reward menu: things you enjoy. One is suggested when the day's promise is kept.
# Run:  focus reward
import random

import focuslib as fl

HELP = """
rewards.py - the reward menu

  focus reward

A list of things you enjoy, kept in rewards.txt, one per line. When a
day's promise is kept, day.py suggests one at random:
  Enter = take it     r = roll again     n = no reward today
This command shows the list, rolls one, and "a" adds a new reward.
Write the list when you are in a good mood - small, real things you can
do the same day. To stop the question: ask_reward=off in settings.txt.
"""


def load():
    return [fl.clean(line) for line in fl.read_lines("rewards.txt")
            if fl.clean(line) and not line.strip().startswith("#")]


def offer(screen, day):
    """Suggest a reward at the end of a kept day and log the one taken."""
    items = load()
    screen.line("")
    if not items:
        screen.line("No rewards on your menu yet. Add some with:  focus reward", "grey")
        return
    last = None
    while True:
        choices = [item for item in items if item != last] or items
        last = random.choice(choices)
        screen.row([("bold", "  YOUR REWARD   "), ("green", last)])
        answer = fl.ask(screen, "Enter = take it, r = roll again, n = none today:").lower()
        if answer.startswith("r"):
            continue
        if not answer.startswith("n"):
            fl.log(day, "reward", last)
            screen.line("Enjoy it. You earned it.", "green")
        return


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    try:
        while True:
            items = load()
            screen.line("")
            screen.line("== REWARD MENU ==", "yellow")
            for item in items:
                screen.line("  - " + item)
            if not items:
                screen.line("  empty - add things you enjoy", "grey")
            answer = fl.ask(screen, "a = add a reward, r = roll one (Enter = done):").lower()
            if answer == "a":
                text = fl.ask(screen, "  Something you enjoy (Enter = cancel):")
                if text:
                    fl.write_lines("rewards.txt", fl.read_lines("rewards.txt") + [text])
            elif answer == "r" and items:
                screen.row([("bold", "  ROLLED   "), ("green", random.choice(items))])
            elif not answer:
                return
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
