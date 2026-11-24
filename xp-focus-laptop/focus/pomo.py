# Visual pomodoro timer with no numbers: an hourglass, or a bouncing ball
# in a box that slowly fills up.
# Run by itself:  python pomo.py     (day.py also uses it)
import math
import sys
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


# ------------------------------------------------- more ways to watch time

def _canvas(height, width):
    return [[("plain", " ")] * width for _ in range(height)]


def _put(grid, y, x, text, color="plain"):
    if 0 <= y < len(grid):
        for i, char in enumerate(text):
            if 0 <= x + i < len(grid[y]):
                grid[y][x + i] = (color, char)


def _finish(grid, label, intent, width):
    margin = [("plain", " " * max(0, (width - len(grid[0])) // 2))]
    return [margin + _squash(cells) for cells in grid] + _footer(label, intent, width)


def candle(frac, tick, sand, grain, label, intent, width):
    """A candle that burns down. When it is out, time is up."""
    height, full = 16, 12
    grid = _canvas(height, 21)
    left = 0 if frac >= 1.0 else int(math.ceil((1.0 - frac) * full))
    base = height - 2
    top = base - left
    for y in range(top, base):
        _put(grid, y, 7, "|")
        _put(grid, y, 8, "#####", sand)
        _put(grid, y, 13, "|")
    _put(grid, base, 4, "=============")
    _put(grid, base + 1, 6, "\\_______/")
    if frac < 1.0:
        _put(grid, top - 1, 9, "(o)" if tick % 2 else "(O)", grain)
        _put(grid, top - 2, 10, "'" if tick % 2 else ".", grain)
    else:
        _put(grid, base - 1, 10, "~", "grey")
        _put(grid, base - 3, 11, "~", "grey")
    return _finish(grid, label, intent, width)


def sun(frac, tick, sand, grain, label, intent, width):
    """The sun crosses the sky from left to right. Sunset means time is up."""
    height, wide = 14, 60
    grid = _canvas(height, wide)
    horizon = height - 2

    def place(f):
        return int(f * (wide - 4)), horizon - 1 - int(round((horizon - 2) * math.sin(math.pi * f)))

    for step in range(0, 100, 4):
        if step / 100.0 < frac:
            x, y = place(step / 100.0)
            _put(grid, y, x + 1, ".", "grey")
    _put(grid, horizon, 0, "_" * wide)
    _put(grid, horizon + 1, 0, ("~ " * wide)[:wide], "grey")
    if frac < 1.0:
        x, y = place(frac)
        _put(grid, y, x, "(O)", grain)
    else:
        for x, y in ((6, 2), (15, 5), (24, 1), (33, 4), (44, 2), (52, 6)):
            _put(grid, y, x, "*", "bold")
        _put(grid, 1, wide - 8, "C", "bold")
    return _finish(grid, label, intent, width)


def snake(frac, tick, sand, grain, label, intent, width):
    """A snake winds across the box until it has filled every square."""
    height, wide = 12, 40
    total = height * wide
    filled = total if frac >= 1.0 else int(frac * total)
    grid = _canvas(height + 2, wide + 2)
    for y in (0, height + 1):
        _put(grid, y, 0, "+" + "-" * wide + "+")
    for y in range(1, height + 1):
        _put(grid, y, 0, "|")
        _put(grid, y, wide + 1, "|")
    for index in range(min(filled + 1, total)):
        y, x = divmod(index, wide)
        if y % 2:
            x = wide - 1 - x
        if index < filled:
            _put(grid, y + 1, x + 1, "#", sand)
        else:
            _put(grid, y + 1, x + 1, "O", "bold")
    return _finish(grid, label, intent, width)


STARS = ((3, 2), (9, 6), (24, 3), (27, 9), (5, 11), (19, 1), (13, 8), (22, 12))


def rocket(frac, tick, sand, grain, label, intent, width):
    """A rocket climbs from the ground to the moon."""
    height, wide = 16, 30
    grid = _canvas(height, wide)
    for x, y in STARS:
        _put(grid, y, x, ".", "grey")
    _put(grid, 0, wide - 7, "( )", "bold")
    ground = height - 1
    _put(grid, ground, 0, "=" * wide)
    nose = 1 if frac >= 1.0 else (ground - 3) - int(frac * (ground - 4))
    x = wide // 2 - 2
    for y in range(nose + 4, ground):
        _put(grid, y, x + 1, "::", grain)
    _put(grid, nose, x, " /\\ ", "bold")
    _put(grid, nose + 1, x, " || ", "bold")
    _put(grid, nose + 2, x, "/__\\", "bold")
    if 0 < frac < 1.0 and nose + 3 < ground:
        _put(grid, nose + 3, x, " ** " if tick % 2 else " ^^ ", grain)
    return _finish(grid, label, intent, width)


# ------------------------------------------------------------ cute timers

def _stamp(grid, y, x, lines, color="plain"):
    """Draw a small picture; its spaces are see-through."""
    for dy, line in enumerate(lines):
        for dx, char in enumerate(line):
            if char != " " and 0 <= y + dy < len(grid) and 0 <= x + dx < len(grid[0]):
                grid[y + dy][x + dx] = (color, char)


def cat(frac, tick, sand, grain, label, intent, width):
    """A cat pads across the floor to its fish, leaving paw prints."""
    height, wide = 9, 60
    grid = _canvas(height, wide)
    floor = height - 1
    done = frac >= 1.0
    x = wide - 16 if done else int(frac * (wide - 16))
    _put(grid, floor, 0, "_" * wide)
    for step in range(2, x, 5):
        _put(grid, floor, step, ".", grain)
    if done:
        _stamp(grid, 1, x + 8, ["<3"], grain)
    else:
        _stamp(grid, floor - 1, wide - 6, ["<><"], grain)
    face = "( ^.^ )" if done else ("( -.- )" if tick % 7 == 0 else "( o.o )")
    _stamp(grid, floor - 4, x, [" /\\_/\\", face, " > ^ <", "  U U" if tick % 2 or done else " U   U"], "bold")
    if x:
        _put(grid, floor - 2, x - 1, "~", "bold")
    return _finish(grid, label, intent, width)


def snail(frac, tick, sand, grain, label, intent, width):
    """A snail crawls to its leaf. The trail behind it is the time gone."""
    height, wide = 7, 60
    grid = _canvas(height, wide)
    floor = height - 1
    done = frac >= 1.0
    x = wide - 17 if done else int(frac * (wide - 17))
    _put(grid, floor, 0, "." * wide, "grey")
    _put(grid, floor, 0, "_" * (x + 2), sand)
    _stamp(grid, floor - 3, wide - 5, ["\\|/", " | ", " | "], "green")
    _stamp(grid, floor - 2, x, ["   __    oo" if tick % 2 or done else "   __   o o",
                                "__(  )___/"], "bold")
    _put(grid, floor - 1, x + 3, "@", grain)
    if done:
        _stamp(grid, floor - 4, x + 6, ["nom"], grain)
    return _finish(grid, label, intent, width)


def plant(frac, tick, sand, grain, label, intent, width):
    """A sprout grows out of its pot and flowers when the time is up."""
    height, wide, tallest = 16, 31, 9
    grid = _canvas(height, wide)
    middle = wide // 2
    done = frac >= 1.0
    grown = tallest if done else int(frac * tallest)
    _stamp(grid, height - 3, middle - 4, ["_________", "\\       /", " \\_____/"])
    for i in range(grown):
        y = height - 4 - i
        _put(grid, y, middle, "|", grain)
        if i % 2:
            if (i // 2) % 2:
                _put(grid, y, middle + 1, "/~", grain)
            else:
                _put(grid, y, middle - 2, "~\\", grain)
    tip = height - 4 - grown
    if done:
        _stamp(grid, tip - 2, middle - 3, [" _(_)_", "(_) (_)", "  (_)"], grain)
        _put(grid, tip - 1, middle, "@", "bold")
    else:
        _put(grid, tip, middle, "o" if tick % 2 else ".", grain)
    return _finish(grid, label, intent, width)


def mug(frac, tick, sand, grain, label, intent, width):
    """A hot drink goes down sip by sip. An empty mug means time is up."""
    height, wide, full = 12, 22, 6
    grid = _canvas(height, wide)
    left = 0 if frac >= 1.0 else int(math.ceil((1.0 - frac) * full))
    _put(grid, 3, 1, ".------------.")
    for i in range(full):
        _put(grid, 4 + i, 1, "|")
        _put(grid, 4 + i, 14, "|")
        if i >= full - left:
            _put(grid, 4 + i, 2, "#" * 12, sand)
    _put(grid, 10, 1, "'------------'")
    _put(grid, 5, 15, "--.")
    _put(grid, 6, 17, "|")
    _put(grid, 7, 17, "|")
    _put(grid, 8, 15, "--'")
    if frac < 1.0:
        steam = [" )  )", "(  (", " )  )"] if tick % 2 else ["(  (", " )  )", "(  ("]
        _stamp(grid, 0, 5, steam, "grey")
    else:
        _stamp(grid, 6, 4, ["all gone"], "grey")
    return _finish(grid, label, intent, width)


def duck(frac, tick, sand, grain, label, intent, width):
    """A duck and two ducklings paddle across the pond to the reeds."""
    height, wide = 9, 60
    grid = _canvas(height, wide)
    done = frac >= 1.0
    x = wide - 17 if done else int(frac * (wide - 17))
    for y in (6, 7, 8):
        _put(grid, y, 0, (("~ " if (y + tick) % 2 else " ~") * wide)[:wide], "grey")
    _put(grid, 6, 0, "=" * x, sand)
    _stamp(grid, 3, wide - 4, ["\\|/", " | ", " | "], "green")
    _stamp(grid, 2, x, ["    __", "___( o)", "\\ <_. )", " `---'"], "bold")
    _put(grid, 3, x + 7, ">", grain)
    for gap in (5, 10):
        if x >= gap:
            _stamp(grid, 5 - (tick + gap) % 2, x - gap, ["(o>"], "bold")
    if done:
        _stamp(grid, 0, x + 2, ["quack!"], grain)
    return _finish(grid, label, intent, width)


HEART = ["  ***   ***  ", " ***** ***** ", "*************", "*************", " *********** ",
         "  *********  ", "   *******   ", "    *****    ", "     ***     ", "      *      "]
HEART_CELLS = [(y, x) for y in range(len(HEART) - 1, -1, -1)
               for x in range(len(HEART[0])) if HEART[y][x] == "*"]


def heart(frac, tick, sand, grain, label, intent, width):
    """A heart fills up from the bottom."""
    grid = _canvas(len(HEART) + 1, 2 * len(HEART[0]))
    filled = len(HEART_CELLS) if frac >= 1.0 else int(frac * len(HEART_CELLS))
    for index, (y, x) in enumerate(HEART_CELLS):
        if index < filled:
            _put(grid, y, 2 * x, "##", sand)
        else:
            _put(grid, y, 2 * x, "..", "grey")
    return _finish(grid, label, intent, width)


def muncher(frac, tick, sand, grain, label, intent, width):
    """A little muncher eats every dot in the box."""
    height, wide = 7, 40
    total = height * wide
    eaten = total if frac >= 1.0 else int(frac * total)
    grid = _canvas(height + 2, wide + 2)
    for y in (0, height + 1):
        _put(grid, y, 0, "+" + "-" * wide + "+")
    for y in range(1, height + 1):
        _put(grid, y, 0, "|")
        _put(grid, y, wide + 1, "|")
    for index in range(eaten, total):
        y, x = divmod(index, wide)
        if y % 2:
            x = wide - 1 - x
        if index == eaten:
            _put(grid, y + 1, x + 1, "C" if tick % 2 else "O", "bold")
        else:
            _put(grid, y + 1, x + 1, ".", grain)
    if eaten >= total:
        _stamp(grid, height // 2 + 1, wide // 2 - 1, ["yum!"], grain)
    return _finish(grid, label, intent, width)


STYLES = ["hourglass", "ball", "candle", "sun", "snake", "rocket",
          "cat", "snail", "plant", "mug", "duck", "heart", "muncher"]
FRAMES = {"hourglass": hourglass, "candle": candle, "sun": sun, "snake": snake, "rocket": rocket,
          "cat": cat, "snail": snail, "plant": plant, "mug": mug, "duck": duck, "heart": heart,
          "muncher": muncher}
DELAY = {"hourglass": 0.5, "candle": 0.4, "sun": 1.0, "snake": 0.5, "rocket": 0.4,
         "cat": 0.4, "snail": 0.6, "plant": 0.6, "mug": 0.5, "duck": 0.5, "heart": 0.6,
         "muncher": 0.3}


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
    frame = FRAMES.get(style, hourglass)
    delay = 0.08 if use_ball else DELAY.get(style, 0.5)
    screen.clear()
    screen.cursor(False)
    start, tick, last = time.time(), 0, None
    try:
        while True:
            frac = min(1.0, (time.time() - start) / total)
            if use_ball:
                rows = ball.frame(frac, sand, label, intent, width)
            else:
                rows = frame(frac, tick, sand, grain, label, intent, width)
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

  focus pomo                 runs work and break timers, logs nothing
  focus pomo rocket          the same, with the rocket
  focus pomo candle demo     a 25-second preview of a design

Thirteen ways to watch time pass, none with numbers:
  hourglass   sand runs from the top to the bottom
  ball        a ball bounces in a box that fills from the floor up
  candle      a candle burns down until it goes out
  sun         the sun crosses the sky; sunset is the end
  snake       a snake winds across a box until it is full
  rocket      a rocket climbs from the ground to the moon
  cat         a cat pads across the floor to its fish
  snail       a snail crawls to its leaf, leaving a trail
  plant       a sprout grows out of its pot and flowers
  mug         a hot drink goes down until the mug is empty
  duck        a duck and two ducklings paddle across the pond
  heart       a heart fills up from the bottom
  muncher     a little muncher eats every dot in the box
One soft beep = halfway. Three beeps = time. Ctrl+C = abandon.

Options are in settings.txt:
  style=<any name above> | rotate (a different one each day)
  work=25  short=5  long=15  chime=on | off  width=78
"""

def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    settings = fl.load_settings()
    screen = fl.Screen(settings["display"])
    width = int(fl.number(settings, "width", 78))
    args = [arg.lower() for arg in sys.argv[1:]]
    style = ([arg for arg in args if arg in STYLES] or [settings["style"]])[0]
    if style == "rotate":
        style = STYLES[fl.current_day() % len(STYLES)]
    try:
        if "demo" in args:
            run(screen, 0.4, "DEMO - {}".format(style), "about 25 seconds", "work", style, width)
            return
        rounds = fl.ask_int(screen, "How many pomodoros?", 1, 12, 2)
        for n in range(1, rounds + 1):
            run(screen, fl.number(settings, "work", 25),
                "WORK {} of {}".format(n, rounds), "", "work", style, width)
            if n < rounds:
                key = "long" if n % 4 == 0 else "short"
                run(screen, fl.number(settings, key, 5), "BREAK", "step away from the screen",
                    "break", style, width)
        screen.line("Planned {}, did {}. Close the laptop.".format(rounds, rounds), "green")
    except (KeyboardInterrupt, EOFError):
        screen.line("")
        screen.line("Stopped. That one does not count.", "yellow")


if __name__ == "__main__":
    main()
