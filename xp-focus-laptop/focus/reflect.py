# Your week in numbers and in your own words, for talking it through.
# Run:  focus reflect        (this cycle)     focus reflect all
import sys
import textwrap

import focuslib as fl
import matrix
import practice

HELP = """
reflect.py - your week, to reflect on and talk through with Claude

  focus reflect          this cycle
  focus reflect 2        cycle 2
  focus reflect all      everything so far

Writes reflect.txt and shows it. It is about you, not about the software:
  DAY BY DAY          energy, what you promised, what you did, focus
  ENERGY AND PROMISES what you promise on low, normal and high days,
                      and how those days actually go
  WHERE THE WORK WENT points and tasks finished in each category
  ROUTINES            how often each one got done
  PRACTICE            reps on each ladder, and fears against reality
  WHAT YOU WROTE      your own notes and end-of-cycle answers
  THINGS TO TALK ABOUT patterns worth a conversation
focus backup writes it too, so it travels on the USB stick.
"""

ENERGY = {1: "low", 2: "normal", 3: "high"}


def gather(days_wanted):
    log = fl.read_log()
    backlog = fl.load_backlog()
    ticks = fl.read_ticks()
    daily = fl.load_routines()
    done_items = [fl.parse_item(line) for line in backlog["DONE"]]
    days = []
    for day in days_wanted:
        if day not in log or not log[day]["planned"]:
            continue
        info = log[day]
        events = fl.day_events(day)
        pomos = [fields for kind, fields in events if kind.startswith("pomo")]
        focus = [int(f["focus"]) for f in pomos if f.get("focus", "").isdigit()]
        finished = [item for item in done_items if item["day"] == day]
        full = len([1 for name, times in daily if ticks.get(day, {}).get(name, 0) >= times])
        days.append({
            "day": day, "energy": info["energy"], "planned": info["planned"], "did": info["did"],
            "pomos": len(pomos), "focus": focus,
            "extras": len([1 for kind, _ in events if kind == "extra"]),
            "abandoned": len([1 for kind, _ in events if kind == "abandoned"]),
            "offscript": len([1 for f in pomos if f.get("offscript")]),
            "away": [f.get("away") == "y" for kind, f in events if kind.startswith("break")],
            "tasks": len(finished), "points": sum(item["points"] or 0 for item in finished),
            "routines": (full, len(daily)),
            "notes": [(f.get("intent", ""), f.get("note", "")) for f in pomos],
            "review": [f for kind, f in events if kind == "review"],
        })
    return days, backlog, done_items


def average(values):
    return sum(values) / float(len(values)) if values else 0.0


def build(scope=None):
    log = fl.read_log()
    if scope == "all":
        wanted, title = sorted(log), "everything so far"
    else:
        cycle = scope or (fl.cycle_of(max(log))[0] if log else 1)
        first = (cycle - 1) * fl.CYCLE_DAYS + 1
        wanted = list(range(first, first + fl.CYCLE_DAYS))
        title = "cycle {} (D{} to D{})".format(cycle, first, first + fl.CYCLE_DAYS - 1)
    days, backlog, done_items = gather(wanted)
    out = ["MY WEEK IN FOCUS  -  {}".format(title), ""]
    add = out.append
    if not days:
        add("No days started in this stretch yet.")
        return out
    talk = []

    add("DAY BY DAY")
    add("  day   energy  promised  done  extra  focus ended      tasks  points  routines")
    for d in days:
        if d["did"] is None:
            ended = "left open"
        elif d["did"] >= d["planned"]:
            ended = "kept"
        else:
            ended = "early"
        add("  D{:<4} {:<7} {:<9} {:<5} {:<6} {:<5} {:<10} {:<6} {:<7} {} of {}".format(
            d["day"], ENERGY.get(d["energy"], "?"), d["planned"], d["pomos"], d["extras"],
            "{:.1f}".format(average(d["focus"])) if d["focus"] else "-", ended,
            d["tasks"], d["points"], d["routines"][0], d["routines"][1]))
    add("")

    add("ENERGY AND PROMISES")
    for level in (1, 2, 3):
        group = [d for d in days if d["energy"] == level]
        if not group:
            add("  {:<7} days: none".format(ENERGY[level]))
            continue
        kept = len([d for d in group if d["did"] is not None and d["did"] >= d["planned"]])
        focus = [f for d in group for f in d["focus"]]
        add("  {:<7} days: {}   promised {:.1f} on average, did {:.1f}, kept {} of {}, focus {}".format(
            ENERGY[level], len(group), average([d["planned"] for d in group]),
            average([d["pomos"] for d in group]), kept, len(group),
            "{:.1f}".format(average(focus)) if focus else "-"))
        if level == 1 and average([d["planned"] for d in group]) > 1.5:
            talk.append("On low-energy days you promised {:.1f} pomodoros on average and did {:.1f}. "
                        "The script suggests 1 on a low day. What made you choose more, and how did "
                        "those days feel afterwards?".format(
                            average([d["planned"] for d in group]), average([d["pomos"] for d in group])))
    add("")

    add("WHERE THE WORK WENT")
    wanted_days = set(d["day"] for d in days)
    by_tag = {}
    for item in done_items:
        if item["day"] in wanted_days:
            for tag in item["tags"] or ["(no category)"]:
                entry = by_tag.setdefault(tag, [0, 0])
                entry[0] += item["points"] or 0
                entry[1] += 1
    for tag in sorted(by_tag, key=lambda t: -by_tag[t][0]):
        add("  {:<18} {:>3} points   {} task{}".format(
            tag if tag.startswith("(") else "#" + tag, by_tag[tag][0], by_tag[tag][1],
            "" if by_tag[tag][1] == 1 else "s"))
    if not by_tag:
        add("  nothing finished yet")
    waiting = {}
    for section in fl.SECTIONS[:-1]:
        for line in backlog[section]:
            for tag in fl.parse_item(line)["tags"]:
                waiting[tag] = waiting.get(tag, 0) + 1
    untouched = sorted(tag for tag in waiting if tag not in by_tag)
    if untouched:
        add("  nothing finished, but tasks waiting, in: " + ", ".join("#" + tag for tag in untouched))
        talk.append("Nothing was finished in {} although tasks are waiting there. Are those still "
                    "goals you want, or is something making them hard to start?".format(
                        ", ".join("#" + tag for tag in untouched)))
    add("")

    add("ROUTINES")
    ticks = fl.read_ticks()
    for name, times in fl.load_routines():
        full = len([d for d in days if ticks.get(d["day"], {}).get(name, 0) >= times])
        add("  {:<22} fully done on {} of {} days".format(name[:22], full, len(days)))
        if len(days) >= 3 and full * 2 < len(days):
            talk.append("'{}' was fully done on {} of {} days. Is the routine the problem, or "
                        "remembering to tick it?".format(name, full, len(days)))
    cycles = sorted(set(fl.cycle_of(d["day"])[0] for d in days))
    wticks = fl.read_weekly_ticks()
    for name, times in fl.load_weekly():
        hit = len([c for c in cycles if wticks.get(c, {}).get(name, 0) >= times])
        add("  {:<22} done in {} of {} cycle{}  (weekly)".format(
            name[:22], hit, len(cycles), "" if len(cycles) == 1 else "s"))
    if not fl.load_routines() and not fl.load_weekly():
        add("  none set up")
    add("")

    add("PRACTICE")
    state = practice.load()
    for name in practice.ORDER:
        reps = [rep for rep in state[name]["reps"] if rep["day"] in wanted_days]
        hard = [practice.HARD.get(rep.get("hard"), "?") for rep in reps]
        add("  {:<12} rung {}   reps {}   {}".format(name, state[name]["rung"], len(reps),
                                                    ", ".join(hard)))
        for rep in reps:
            add("      did: {}  ->  {}".format(rep.get("did", ""), rep.get("outcome", ""))[:110])
    total, happened, partly = practice.fear_counts(state)
    if total:
        add("  feared outcomes (all time): feared {}, happened {}, partly {}".format(total, happened, partly))
    else:
        talk.append("No practice reps yet. Which ladder feels worst, and what is the smallest "
                    "rung-1 rep you could do this week?")
    add("")

    add("WHAT YOU WROTE")
    wrote = False
    for d in days:
        for intent, note in d["notes"]:
            if note:
                add("  D{} {}: {}".format(d["day"], intent, note)[:110])
                wrote = True
        for fields in d["review"]:
            for key in ("worked", "blocked", "change"):
                if fields.get(key):
                    add("  D{} review, {}: {}".format(d["day"], key, fields[key])[:110])
                    wrote = True
    if not wrote:
        add("  no notes yet")
    add("")

    open_days = [d["day"] for d in days if d["did"] is None]
    early = [d["day"] for d in days if d["did"] is not None and d["did"] < d["planned"]]
    if open_days:
        talk.append("Days left open (never closed): {}. What happened at the end of those days?".format(
            ", ".join("D{}".format(day) for day in open_days)))
    if early:
        talk.append("Days ended before the promise was met: {}. Was the promise too big, or did "
                    "the day change?".format(", ".join("D{}".format(day) for day in early)))
    off = sum(d["offscript"] for d in days)
    if off:
        talk.append("{} of {} pomodoros were recorded afterwards, not run with the timer. Does the "
                    "timer help, or do you work better without it?".format(off, sum(d["pomos"] for d in days)))
    low, high = [f for d in days if d["energy"] == 1 for f in d["focus"]], \
                [f for d in days if d["energy"] == 3 for f in d["focus"]]
    if low and high:
        talk.append("Average focus was {:.1f} on low-energy days and {:.1f} on high-energy days.".format(
            average(low), average(high)))
    add("THINGS TO TALK ABOUT")
    for line in talk or ["Nothing stands out yet. Keep going and look again in a few days."]:
        first = True
        for piece in textwrap.wrap(line, 72):
            add(("  - " if first else "    ") + piece)
            first = False
    return out


def write(scope=None):
    lines = build(scope)
    fl.write_lines("reflect.txt", lines)
    return lines


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    args = [arg.lower() for arg in sys.argv[1:]]
    scope = "all" if "all" in args else None
    numbers = [arg for arg in args if arg.isdigit()]
    if numbers:
        scope = int(numbers[0])
    screen = fl.Screen(fl.load_settings()["display"])
    for line in write(scope):
        screen.line(line, "bold" if line and not line.startswith(" ") else None)
    screen.line("")
    screen.line("Saved as reflect.txt. focus backup puts it on the USB stick.", "grey")


if __name__ == "__main__":
    main()
