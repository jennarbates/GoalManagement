# The Eisenhower chart: every open task in one of four boxes.
# Run:  focus matrix      (day.py walks through it every day)
import re

import focuslib as fl

HELP = """
matrix.py - the Eisenhower chart

  focus matrix

Draws your open tasks in four boxes:
  1 urgent + important      DO FIRST     (today's MUST comes from here)
  2 important, not urgent   SCHEDULE     (the real work - protect it)
  3 urgent, not important   MINIMISE
  4 neither                 DROP         (nothing is kept here)
Type a task's number to re-sort it: it asks "urgent?" and "important?"
again and moves the task. Enter leaves the chart as it is.
A task's box is stored at the end of its line in backlog.txt, like (B2).
"""

OPEN = ["DOING", "THIS CYCLE", "BACKLOG - IMPORTANT", "BACKLOG - SOMEDAY"]
CELL = 34
ROWS = 6
TITLES = {1: ("red", "1 DO FIRST"), 2: ("green", "2 SCHEDULE - the real work"),
          3: ("yellow", "3 MINIMISE"), 4: ("grey", "4 DROP")}


def strip_box(line):
    return re.sub(r"\s*\(B[1-4]\)", "", line)


def box_of(section, line):
    marked = re.search(r"\(B([1-4])\)", line)
    if marked:
        return int(marked.group(1))
    if section == "BACKLOG - SOMEDAY":
        return 3
    if fl.parse_item(line)["due"] is not None:
        return 1
    return 2


def collect(backlog):
    """Open tasks, numbered box by box."""
    items = []
    for box in (1, 2, 3):
        for section in OPEN:
            for line in backlog[section]:
                if box_of(section, line) == box:
                    items.append({"section": section, "line": line, "box": box})
    for number, item in enumerate(items, 1):
        item["number"] = number
    return items


def _cell(text, color="plain"):
    return (color, " {:<{}}".format(text[:CELL - 1], CELL - 1))


def _box_rows(items, box):
    mine = [item for item in items if item["box"] == box]
    rows = [_cell(TITLES[box][1], TITLES[box][0])]
    for item in mine[:ROWS]:
        rows.append(_cell("{:>2}. {}".format(item["number"], strip_box(item["line"]))))
    if len(mine) > ROWS:
        rows.append(_cell("    + {} more".format(len(mine) - ROWS), "grey"))
    if box == 4:
        rows.append(_cell("    (nothing is kept here)", "grey"))
    return rows


def draw(screen, items):
    edge = [("plain", "      +" + "-" * CELL + "+" + "-" * CELL + "+")]
    screen.line("")
    screen.row([("bold", "       {:<{}} {}".format("URGENT", CELL, "NOT URGENT"))])
    for left, right, side in ((1, 2, ("IMPOR", "TANT")), (3, 4, ("NOT", "IMP."))):
        screen.row(edge)
        a, b = _box_rows(items, left), _box_rows(items, right)
        for i in range(max(len(a), len(b), 3)):
            label = side[i] if i < len(side) else ""
            screen.row([("bold", " {:<5}".format(label)), ("plain", "|"),
                        a[i] if i < len(a) else _cell(""), ("plain", "|"),
                        b[i] if i < len(b) else _cell(""), ("plain", "|")])
    screen.row(edge)
    screen.flush()


def resort(screen, backlog, item):
    """Ask the two questions again and move the task to its new box."""
    line, section = item["line"], item["section"]
    screen.line("  " + strip_box(line), "bold")
    urgent = fl.ask_yes(screen, "  Is it urgent (a real deadline soon)?", False)
    important = fl.ask_yes(screen, "  Is it important (moves a goal you care about)?", True)
    box = 1 if urgent and important else 2 if important else 3 if urgent else 4
    if box == 4:
        if fl.ask_yes(screen, "  Box 4 means drop it. Remove it from the backlog?"):
            backlog[section].remove(line)
            fl.save_backlog(backlog)
            screen.line("  Dropped.", "grey")
        return
    new = "{} (B{})".format(strip_box(line), box)
    where = backlog[section].index(line)
    if section == "DOING":
        backlog[section][where] = new
    elif box == 1:
        backlog[section].pop(where)
        backlog["THIS CYCLE"].insert(0, new)
    elif box == 3:
        backlog[section].pop(where)
        backlog["BACKLOG - SOMEDAY"].append(new)
    elif section == "BACKLOG - SOMEDAY":
        backlog[section].pop(where)
        backlog["BACKLOG - IMPORTANT"].append(new)
    else:
        backlog[section][where] = new
    fl.save_backlog(backlog)
    screen.line("  Now in box {}.".format(box), "green")


def walk(screen, backlog):
    """Show the chart, let the user fix anything in the wrong box, then advise."""
    screen.line("")
    screen.line("== EISENHOWER CHART ==", "yellow")
    while True:
        items = collect(backlog)
        draw(screen, items)
        if not items:
            screen.line("  No open tasks yet.", "grey")
            return
        pick = fl.ask(screen, "Anything in the wrong box? Type its number (Enter = the chart is right):")
        if not pick:
            break
        if pick.isdigit() and 1 <= int(pick) <= len(items):
            resort(screen, backlog, items[int(pick) - 1])
    first = len([item for item in collect(backlog) if item["box"] == 1])
    if first:
        screen.line("Box 1 has {} task{}. Today's MUST comes from there.".format(
            first, "" if first == 1 else "s"), "red")
    else:
        screen.line("Box 1 is empty, so today is a box 2 day: the work that matters.", "green")


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    try:
        walk(fl.Screen(fl.load_settings()["display"]), fl.load_backlog())
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
