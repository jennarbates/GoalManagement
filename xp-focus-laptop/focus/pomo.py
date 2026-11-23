# Visual pomodoro timer with no numbers: an hourglass, or a bouncing ball
# in a box that slowly fills up.
# Run by itself:  python pomo.py     (day.py also uses it)
import time

import focuslib as fl

R = 8                      # rows in each half of the hourglass
GRAINS = R * R             # 64 grains of sand
BOX_W, BOX_H = 60, 14      # ball box, in characters


def _center_out(width):
    mid = width // 2
    return sorted(range(width), key=lambda c: (abs(c - mid), c))


# Top half empties from the surface down; bottom half piles up from the floor.
TOP_ORDER = [(r, c) for r in range(R) for c in _center_out(2 * (R - r) - 1)]
BOT_ORDER = [(r, c) for r in range(R - 1, -1, -1) for c in _center_out(2 * r + 1)]


def _squash(cells):
    """[(colour, char), ...] -> merged (colour, text) pieces."""
    pieces = []
    for color, char in cells:
        if pieces and pieces[-1][0] == color:
            pieces[-1] = (color, pieces[-1][1] + char)
        else:
            pieces.append((color, char))
    return pieces


def _centered(text, width, color="plain"):
    text = text[:width]
    return [("plain", " " * ((width - len(text)) // 2)), (color, text)]


def _footer(label, intent, width):
    rows = [[("plain", "")], _centered(label, width, "bold")]
    rows.append(_centered(intent, width, "plain") if intent else [("plain", "")])
    rows.append([("plain", "")])
    rows.append(_centered("Ctrl+C abandons this one", width, "grey"))
    return rows


def hourglass(frac, tick, sand, grain, label, intent, width):
    fallen = GRAINS if frac >= 1.0 else int(frac * GRAINS)
    gone = set(TOP_ORDER[:fallen])
    piled = set(BOT_ORDER[:fallen])
    margin = " " * ((width - (2 * R + 1)) // 2)
    rows = [[("plain", margin + "_" * (2 * R + 1))]]
    for r in range(R):
        cells = [("plain", c) for c in margin + " " * r + "\\"]
        for c in range(2 * (R - r) - 1):
            cells.append(("plain", " ") if (r, c) in gone else (sand, "#"))
        cells.append(("plain", "/"))
        rows.append(_squash(cells))
    drop = tick % R
    for r in range(R):
        cells = [("plain", c) for c in margin + " " * (R - 1 - r) + "/"]
        for c in range(2 * r + 1):
            if (r, c) in piled:
                cells.append((sand, "#"))
            elif fallen < GRAINS and r == drop and c == r:
                cells.append((grain, "."))
            else:
                cells.append(("plain", " "))
        cells.append(("plain", "\\"))
        rows.append(_squash(cells))
    rows.append([("plain", margin + "=" * (2 * R + 1))])
    return rows + _footer(label, intent, width)


class Ball(object):
    def __init__(self):
        self.x, self.y, self.dx, self.dy = 3, 1, 2, 1

    def frame(self, frac, sand, label, intent, width):
        filled = BOX_W * BOX_H if frac >= 1.0 else int(frac * BOX_W * BOX_H)
        full, part = filled // BOX_W, filled % BOX_W
        free = BOX_H - full - (1 if part else 0)     # rows the ball can use
        if free > 0:
            self.x += self.dx
            self.y += self.dy
            if self.x <= 0:
                self.x, self.dx = 0, 2
            elif self.x >= BOX_W - 1:
                self.x, self.dx = BOX_W - 1, -2
            if self.y >= free - 1:
                self.y, self.dy = free - 1, -1
            elif self.y <= 0:
                self.y, self.dy = 0, 1
            self.y = max(0, self.y)
        margin = " " * ((width - (BOX_W + 2)) // 2)
        edge = [("plain", margin + "+" + "-" * BOX_W + "+")]
        rows = [edge]
        for r in range(BOX_H):
            cells = [("plain", c) for c in margin + "|"]
            for c in range(BOX_W):
                if r >= BOX_H - full or (part and r == BOX_H - full - 1 and c < part):
                    cells.append((sand, "#"))
                elif free > 0 and r == self.y and c == self.x:
                    cells.append(("bold", "O"))
                else:
                    cells.append(("plain", " "))
            cells.append(("plain", "|"))
            rows.append(_squash(cells))
        rows.append(edge)
        return rows + _footer(label, intent, width)


def run(screen, minutes, label, intent="", kind="work", style="hourglass", width=78,
        color="yellow", chime=False):
    """Show the timer until the time is up, then beep. No numbers on screen.
    color is the work colour (yellow, cyan or magenta); breaks are always green.
    chime gives one soft beep at the halfway point."""
    total = max(1.0, minutes * 60.0)
    if kind != "work" or "on_" + color not in fl.COLORS:
        color = "green" if kind != "work" else "yellow"
    sand, grain = "on_" + color, color
    chimed = not chime
    use_ball = style == "ball" and screen.mode != "plain"
    ball = Ball()
    delay = 0.08 if use_ball else 0.5
    screen.clear()
    screen.cursor(False)
    start, tick, last = time.time(), 0, None
    try:
        while True:
            frac = min(1.0, (time.time() - start) / total)
            if use_ball:
                rows = ball.frame(frac, sand, label, intent, width)
            else:
                rows = hourglass(frac, tick, sand, grain, label, intent, width)
            step = int(frac * GRAINS)
            if screen.mode != "plain" or step != last:
                screen.draw(rows)
                last = step
            if frac >= 1.0:
                break
            if not chimed and frac >= 0.5:
                chimed = True
                fl.beep(1, 660, 150)
            time.sleep(delay)
            tick += 1
    finally:
        screen.cursor(True)
        screen.color("plain")
    fl.beep(3)


HELP = """
pomo.py - the visual timer, without the questions

  python pomo.py

Asks how many pomodoros, then runs work and break timers.
No numbers: the hourglass empties, or the box fills up.
One soft beep = halfway. Three beeps = time. Ctrl+C = abandon.
Nothing is logged; use day.py for the full day.

Options are in settings.txt:
  style=hourglass | ball | rotate      work=25  short=5  long=15
  chime=on | off                       width=78
"""

def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    settings = fl.load_settings()
    screen = fl.Screen(settings["display"])
    width = int(fl.number(settings, "width", 78))
    try:
        rounds = fl.ask_int(screen, "How many pomodoros?", 1, 12, 2)
        for n in range(1, rounds + 1):
            run(screen, fl.number(settings, "work", 25),
                "WORK {} of {}".format(n, rounds), "", "work", settings["style"], width)
            if n < rounds:
                key = "long" if n % 4 == 0 else "short"
                run(screen, fl.number(settings, key, 5), "BREAK", "step away from the screen",
                    "break", settings["style"], width)
        screen.line("Planned {}, did {}. Close the laptop.".format(rounds, rounds), "green")
    except (KeyboardInterrupt, EOFError):
        screen.line("")
        screen.line("Stopped. That one does not count.", "yellow")


if __name__ == "__main__":
    main()
