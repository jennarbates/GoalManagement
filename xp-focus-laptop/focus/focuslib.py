# Shared helpers for the focus scripts: screen and colour, questions, files.
# Written for Python 3.4 on Windows XP (no f-strings, ASCII output only).
import io
import os
import re
import sys
import time
from collections import OrderedDict

try:
    import ctypes
except ImportError:
    ctypes = None
try:
    import winsound
except ImportError:
    winsound = None

HERE = os.path.dirname(os.path.abspath(__file__))
SECTIONS = ["DOING", "THIS CYCLE", "BACKLOG - IMPORTANT", "BACKLOG - SOMEDAY", "DONE"]
HEADERS = {"DOING": "DOING (max 1)", "THIS CYCLE": "THIS CYCLE"}
CYCLE_DAYS = 7

# name: (ANSI code, Windows console attribute)
COLORS = {
    "plain":     ("\033[0m", 0x07),
    "bold":      ("\033[0;1m", 0x0F),
    "grey":      ("\033[0;1;30m", 0x08),
    "red":       ("\033[0;1;31m", 0x0C),
    "green":     ("\033[0;1;32m", 0x0A),
    "lo_green":  ("\033[0;32m", 0x02),
    "on_lime":   ("\033[0;1;32;102m", 0xAA),
    "yellow":    ("\033[0;1;33m", 0x0E),
    "cyan":      ("\033[0;1;36m", 0x0B),
    "magenta":   ("\033[0;1;35m", 0x0D),
    "on_magenta": ("\033[0;35;45m", 0x55),
    "on_red":    ("\033[0;31;41m", 0x44),
    "on_green":  ("\033[0;32;42m", 0x22),
    "on_yellow": ("\033[0;33;43m", 0x66),
    "on_cyan":   ("\033[0;36;46m", 0x33),
}


def path(name):
    return os.path.join(HERE, name)


def fix_streams():
    """Never crash on odd characters typed or printed."""
    for name in ("stdin", "stdout"):
        stream = getattr(sys, name)
        try:
            encoding = stream.encoding or "ascii"
            wrapped = io.TextIOWrapper(stream.detach(), encoding=encoding,
                                       errors="replace",
                                       line_buffering=(name == "stdout"))
            setattr(sys, name, wrapped)
        except Exception:
            pass


class Screen(object):
    """Colour and cursor control. Modes: ansi (Cygwin terminal),
    win (a real Windows console such as cmd), plain (no colour)."""

    def __init__(self, display="auto"):
        self.mode = "ansi"
        self.handle = None
        self.kernel = None
        if display == "plain":
            self.mode = "plain"
        elif display != "ansi" and os.name == "nt" and ctypes is not None:
            try:
                kernel = ctypes.windll.kernel32
                handle = kernel.GetStdHandle(-11)
                mode = ctypes.c_ulong()
                if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                    self.mode, self.handle, self.kernel = "win", handle, kernel
            except Exception:
                pass

    def color(self, name):
        if self.mode == "ansi":
            sys.stdout.write(COLORS[name][0])
        elif self.mode == "win":
            sys.stdout.flush()
            self.kernel.SetConsoleTextAttribute(self.handle, COLORS[name][1])

    def write(self, text, color=None):
        if color and color != "plain":
            self.color(color)
            sys.stdout.write(text)
            self.color("plain")
        else:
            sys.stdout.write(text)

    def flush(self):
        sys.stdout.flush()

    def clear(self):
        if self.mode == "ansi":
            sys.stdout.write("\033[0m\033[2J\033[H")
        elif self.mode == "win":
            sys.stdout.flush()
            os.system("cls")
        else:
            sys.stdout.write("\n\n")
        sys.stdout.flush()

    def home(self):
        if self.mode == "ansi":
            sys.stdout.write("\033[H")
        elif self.mode == "win":
            sys.stdout.flush()
            self.kernel.SetConsoleCursorPosition(self.handle, 0)
        else:
            sys.stdout.write("\n")

    def cursor(self, visible):
        if self.mode == "ansi":
            sys.stdout.write("\033[?25h" if visible else "\033[?25l")
            sys.stdout.flush()

    def row(self, segments):
        """Print one line made of (colour, text) pieces."""
        for color, text in segments:
            self.write(text, color)
        if self.mode == "ansi":
            sys.stdout.write("\033[K")
        sys.stdout.write("\n")

    def draw(self, rows):
        """Redraw a whole frame from the top-left corner."""
        self.home()
        for segments in rows:
            self.row(segments)
        sys.stdout.flush()

    def line(self, text="", color=None):
        self.row([(color or "plain", text)])
        sys.stdout.flush()


COMMANDS = """
All commands (type them in the Cygwin terminal):
  focus              the guided day: plan, pomodoros, breaks, log, dashboard
  focus today        one page for today: the MUST, what is done, what is left
  focus dash         the big-picture dashboard
  focus matrix       the Eisenhower chart: see and re-sort your tasks
  focus summary      one-screen recap of a cycle (focus summary 2 = cycle 2)
  focus pomo         the timer only
  focus points       story points for one task
  focus undo         take back the last log line or the last finished task
  focus backup       copy C:\\focus to the USB stick
  focus sync         pull notes typed on the PSPi ("note ...") into park.txt
  focus celebrate    replay the end-of-day confetti
  focus help         this list.   focus dash --help etc. for details.
If "focus" is not set up yet:  python C:/focus/focus.py

Files:  backlog.txt (tasks)   park.txt (stray thoughts)   log.txt (history)
        today.txt (today's plan)   settings.txt (options)   SYSTEM.txt (guide)
"""


def help_requested(text):
    """Print help and return True if the script was run with --help or -h."""
    if any(arg in ("--help", "-h", "help", "/?") for arg in sys.argv[1:]):
        sys.stdout.write(text.strip("\n") + "\n" + COMMANDS)
        sys.stdout.flush()
        return True
    return False


def beep(times=3, pitch=880, length=350):
    for _ in range(times):
        if winsound is not None:
            try:
                winsound.Beep(pitch, length)
            except Exception:
                pass
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
        time.sleep(0.15)


# ---------------------------------------------------------------- questions

def clean(text):
    return " ".join(text.replace("|", "/").split())


def ask(screen, prompt, default=""):
    screen.write(prompt + " ", "cyan")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        raise EOFError()
    line = clean(line)
    return line if line else default


def ask_required(screen, prompt):
    while True:
        answer = ask(screen, prompt)
        if answer:
            return answer
        screen.line("  (type a few words)", "grey")


def ask_int(screen, prompt, low, high, default=None):
    while True:
        answer = ask(screen, prompt)
        if not answer and default is not None:
            return default
        if answer.isdigit() and low <= int(answer) <= high:
            return int(answer)
        screen.line("  Type a number from {} to {}.".format(low, high), "grey")


def ask_yes(screen, prompt, default=True):
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        answer = ask(screen, "{} {}".format(prompt, hint)).lower()
        if not answer:
            return default
        if answer[0] in "yn":
            return answer[0] == "y"


# -------------------------------------------------------------------- files

def read_lines(name):
    try:
        with open(path(name), encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except IOError:
        return []
    return text.lstrip("\ufeff").splitlines()


def write_lines(name, lines):
    with open(path(name), "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write("\n".join(lines) + "\n")


def load_settings():
    settings = {"style": "hourglass", "work": "25", "short": "5", "long": "15",
                "display": "auto", "width": "78", "chime": "on", "colours": "rotate",
                "celebrate": "on"}
    for line in read_lines("settings.txt"):
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            settings[key.strip().lower()] = value.strip()
    return settings


def save_setting(key, value):
    lines = read_lines("settings.txt")
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip().lower() == key:
            lines[i] = "{}={}".format(key, value)
            break
    else:
        lines.append("{}={}".format(key, value))
    write_lines("settings.txt", lines)


def number(settings, key, fallback):
    try:
        return float(settings.get(key, fallback))
    except ValueError:
        return float(fallback)


# ---------------------------------------------------------------------- log

def log(day, kind, *parts):
    line = " | ".join(["D{}".format(day), kind] + [p for p in parts if p])
    with open(path("log.txt"), "a", encoding="utf-8", newline="\r\n") as handle:
        handle.write(line + "\n")


def read_log():
    """Return {day: {...}} in day order."""
    days = {}
    for line in read_lines("log.txt"):
        match = re.match(r"^D(\d+) \| (\w+)(.*)$", line.strip())
        if not match:
            continue
        day, kind, rest = int(match.group(1)), match.group(2), match.group(3)
        info = days.setdefault(day, {"planned": None, "did": None, "focus": [],
                                     "away": [], "points": None, "energy": None})
        if kind == "start":
            found = re.search(r"plan (\d+)", rest)
            if found:
                info["planned"] = int(found.group(1))
            found = re.search(r"\| energy (\d)", rest)
            if found:
                info["energy"] = int(found.group(1))
        elif kind == "pomo":
            found = re.search(r"focus (\d)", rest)
            if found:
                info["focus"].append(int(found.group(1)))
        elif kind == "break":
            found = re.search(r"away ([yn])", rest)
            if found:
                info["away"].append(found.group(1) == "y")
        elif kind == "end":
            found = re.search(r"planned (\d+), did (\d+)", rest)
            if found:
                info["planned"] = int(found.group(1))
                info["did"] = int(found.group(2))
    return OrderedDict(sorted(days.items()))


# ------------------------------------------------------------- parking lot

PARK_HEADER = "# Parking lot: one stray thought per line. day.py sorts them at the end of the day."


def read_park():
    return [line.strip() for line in read_lines("park.txt")
            if line.strip() and not line.strip().startswith("#")]


def write_park(items):
    write_lines("park.txt", [PARK_HEADER] + items)


def park(text):
    write_park(read_park() + [text])


def day_events(day):
    """Everything logged for one day, in order: [(kind, {field: value})]."""
    events = []
    for line in read_lines("log.txt"):
        match = re.match(r"^D(\d+) \| (.*)$", line.strip())
        if not match or int(match.group(1)) != day:
            continue
        parts = [part.strip() for part in match.group(2).split(" | ")]
        fields = {}
        for part in parts[1:]:
            if ": " in part:
                key, value = part.split(": ", 1)
                fields[key] = value
            elif " " in part:
                key, value = part.rsplit(" ", 1)
                fields[key] = value
        events.append((parts[0], fields))
    return events


def cycle_of(day):
    """(cycle number, day within the cycle), both starting at 1."""
    return (day - 1) // CYCLE_DAYS + 1, (day - 1) % CYCLE_DAYS + 1


# ------------------------------------------------------------------ backlog

def load_backlog():
    data = OrderedDict((name, []) for name in SECTIONS)
    current = None
    for raw in read_lines("backlog.txt"):
        line = raw.strip()
        if not line:
            continue
        header = None
        for name in SECTIONS:
            if line.startswith(name):
                header = name
        if header:
            current = header
        elif current:
            data[current].append(line)
    return data


def save_backlog(data):
    lines = []
    for name in SECTIONS:
        lines.append(HEADERS.get(name, name))
        lines.extend(data[name])
        lines.append("")
    write_lines("backlog.txt", lines)


def parse_item(line):
    item = {"day": None, "points": None, "text": line, "tags": []}
    match = re.match(r"^D(\d+)\s*\|\s*(.*)$", line)
    if match:
        item["day"], line = int(match.group(1)), match.group(2)
    match = re.match(r"^\[(\d+)\]\s*(.*)$", line)
    if match:
        item["points"], line = int(match.group(1)), match.group(2)
    item["text"] = line
    item["tags"] = [tag.lower() for tag in re.findall(r"#(\w+)", line)]
    due = re.search(r"@D(\d+)", line)
    item["due"] = int(due.group(1)) if due else None
    return item


def points_of(lines):
    return sum(parse_item(line)["points"] or 0 for line in lines)


def done_points_by_cycle(data):
    totals = {}
    for line in data["DONE"]:
        item = parse_item(line)
        if item["day"] is not None:
            cycle = cycle_of(item["day"])[0]
            totals[cycle] = totals.get(cycle, 0) + (item["points"] or 0)
    return totals
