# A few seconds of confetti and a short tune when a day's promise is kept.
# Run:  focus celebrate      (day.py plays it at the end of each day)
import random
import time

import focuslib as fl
import pomo

HELP = """
celebrate.py - the end-of-day celebration

  focus celebrate

A short rising tune, then a few seconds of confetti around
"D5 DONE - PROMISE KEPT". Odd days rain confetti, even days float
bubbles upward. To turn it off, set  celebrate=off  in settings.txt.
"""

HEIGHT = 16
SHAPES = "*+o.'"
SHADES = ["yellow", "green", "cyan", "magenta", "red", "bold"]
TUNE = [523, 659, 784, 1047]


def tune():
    if fl.winsound is None:
        return
    for pitch in TUNE:
        try:
            fl.winsound.Beep(pitch, 130)
        except Exception:
            return


def run(screen, day, width=78, seconds=3.5):
    lines = ["D{} DONE".format(day), "PROMISE KEPT"]
    if screen.mode == "plain":
        screen.line("")
        screen.line("  *** {} - {} ***".format(lines[0], lines[1]))
        return
    tune()
    rising = day % 2 == 0
    pieces = []                                   # [x, y, char, colour]
    screen.clear()
    screen.cursor(False)
    start = time.time()
    try:
        while time.time() - start < seconds:
            for _ in range(5):
                pieces.append([random.randrange(width), HEIGHT - 1 if rising else 0,
                               random.choice("oO." if rising else SHAPES), random.choice(SHADES)])
            grid = [[("plain", " ")] * width for _ in range(HEIGHT)]
            for piece in pieces:
                if 0 <= piece[1] < HEIGHT:
                    grid[piece[1]][piece[0]] = (piece[3], piece[2])
            for offset, text in enumerate(lines):
                row = HEIGHT // 2 - 1 + offset
                left = (width - len(text) - 4) // 2
                for i, char in enumerate("  " + text + "  "):
                    grid[row][left + i] = ("bold" if offset == 0 else "green", char)
            screen.draw([pomo._squash(cells) for cells in grid])
            for piece in pieces:
                piece[1] += -1 if rising else 1
            pieces = [piece for piece in pieces if 0 <= piece[1] < HEIGHT]
            time.sleep(0.08)
    finally:
        screen.cursor(True)
        screen.color("plain")


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    settings = fl.load_settings()
    days = fl.read_log()
    run(fl.Screen(settings["display"]), max(days) if days else 1,
        int(fl.number(settings, "width", 78)))


if __name__ == "__main__":
    main()
