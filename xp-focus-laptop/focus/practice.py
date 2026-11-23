# Practice ladders: uncertainty, failure, conflict. One small rep per ladder
# per cycle, a short log after each, and up a rung only when it gets boring.
# Run:  focus practice
import re
import textwrap

import focuslib as fl

HELP = """
practice.py - the three practice ladders

  focus practice

Three ladders for one skill: tolerating an outcome you cannot control or
do not like. Each has five rungs. Aim for one rep per ladder per cycle.

  1 / 2 / 3   log a rep you did (uncertainty / failure / conflict)
  p           plan your next rep: what you will do, and what you are
              afraid will happen
  u / d       move a ladder up or down a rung
  l           read a whole ladder

After a rep it asks what you did, what you felt, the outcome, whether the
feared thing happened, how hard it was, and whether you used the escape.
The outcome is the part that matters: over time it shows that the feared
result mostly does not happen, or happens and is survivable.
Move up only when a rung feels boring - the script offers it after two
boring reps in a row. Moving down, or skipping a cycle, is fine.
You set the pace. If you have a therapist, show them this.
To stop the daily question: ask_practice=off in settings.txt.
"""

ORDER = ["uncertainty", "failure", "conflict"]
LADDERS = {
    "uncertainty": {
        "move": "Act without resolving the unknown.",
        "rule": "Reassurance-seeking and over-researching are the escapes.",
        "escape": "Did you seek reassurance or research it anyway?",
        "rungs": [
            "Make a low-stakes decision fast: 2-minute limit, then commit.",
            "Do not look it up: when you want reassurance, wait 10 minutes first.",
            "Make a medium decision with incomplete information. Write: I am deciding without knowing X.",
            "Send the thing before you know how it lands, then do something else for an hour.",
            "Live with a real open question for a week: write best and worst case, then stop researching.",
        ],
    },
    "failure": {
        "move": "Fail on purpose, small and often, so it loses its charge.",
        "rule": "Separate the event from the verdict. 'That went badly' is a fact; 'I am bad at this' is a story.",
        "escape": "Did you replay it, or turn it into a verdict about yourself?",
        "rungs": [
            "Do something you are bad at, alone, for 15 minutes. Expect it to be bad.",
            "Do something you are bad at in front of one person.",
            "Set a goal you might really miss, and tell someone before you start.",
            "Submit work at 80%, not 100%. Notice that nothing collapses.",
            "After a real failure, write one line within 24 hours: what happened, what I would change, done.",
        ],
    },
    "conflict": {
        "move": "Say the true thing, calmly, and stay in the room afterward.",
        "rule": "Over-explaining, apologising or softening afterward is the escape.",
        "escape": "Did you over-explain, apologise or soften afterward?",
        "rungs": [
            "State a minor preference out loud. No cushioning.",
            "Disagree on something trivial, in one sentence, without backpedalling.",
            "Say no to a request without a long explanation.",
            "Raise a small issue within 48 hours: When X happened, I did not like it. I would like Y.",
            "Have the hard conversation: write the one sentence first, say it, then let there be a pause.",
        ],
    },
}
HARD = {"1": "boring", "2": "uncomfortable", "3": "very hard"}


def say(screen, first, text, color=None, width=76):
    """Print text wrapped under a prefix, so long rungs are never cut off."""
    lines = textwrap.wrap(text, width - len(first)) or [""]
    screen.line(first + lines[0], color)
    for more in lines[1:]:
        screen.line(" " * len(first) + more, color)


def label(text):
    return ("bold", "  {:<12}".format(text))


def load():
    """{ladder: {"rung": n, "reps": [fields], "plan": fields or None}} from the log."""
    state = dict((name, {"rung": 1, "reps": [], "plan": None}) for name in ORDER)
    for line in fl.read_lines("log.txt"):
        match = re.match(r"^D(\d+) \| (repplan|rep|rung) \| (.*)$", line.strip())
        if not match:
            continue
        fields = {"day": int(match.group(1))}
        for part in match.group(3).split(" | "):
            if ": " in part:
                key, value = part.split(": ", 1)
                fields[key.strip()] = value.strip()
        ladder = state.get(fields.get("ladder"))
        if ladder is None:
            continue
        kind = match.group(2)
        if kind == "rung" and fields.get("rung", "").isdigit():
            ladder["rung"] = max(1, min(5, int(fields["rung"])))
        elif kind == "repplan":
            ladder["plan"] = fields
        elif kind == "rep":
            ladder["reps"].append(fields)
            ladder["plan"] = None
    return state


def done_this_cycle(ladder, day):
    cycle = fl.cycle_of(day)[0]
    return any(fl.cycle_of(rep["day"])[0] == cycle for rep in ladder["reps"])


def rows(day):
    """Rows for the day page: where each ladder stands this cycle."""
    state = load()
    out = []
    for i, name in enumerate(ORDER):
        ladder = state[name]
        if ladder["plan"]:
            status = ("yellow", "planned: " + ladder["plan"].get("do", "")[:38])
        elif done_this_cycle(ladder, day):
            status = ("green", "rep done this cycle")
        else:
            status = ("grey", "no rep planned yet  (focus practice)")
        out.append([label("PRACTICE" if i == 0 else ""),
                    ("plain", "{:<12}r{}  ".format(name, ladder["rung"])), status])
    return out


def dash_rows(day):
    """Rows for the dashboard: rungs climbed, reps, and the feared-outcome count."""
    state = load()
    out, total, happened = [], 0, 0
    for i, name in enumerate(ORDER):
        ladder = state[name]
        cells = [label("PRACTICE" if i == 0 else ""), ("plain", "{:<12}".format(name))]
        for rung in range(1, 6):
            cells.append(("on_green", "##") if rung <= ladder["rung"] else ("grey", ".."))
            cells.append(("plain", " "))
        cells.append(("plain", " rung {}  reps {:<3}".format(ladder["rung"], len(ladder["reps"]))))
        cells.append(("green", "done this cycle") if done_this_cycle(ladder, day)
                     else ("grey", "not yet this cycle"))
        out.append(cells)
        for rep in ladder["reps"]:
            if rep.get("feared_happened") in ("y", "n", "partly"):
                total += 1
                happened += rep["feared_happened"] == "y"
    if total:
        out.append([label(""), ("yellow", "the feared outcome happened in {} of {} reps".format(
            happened, total))])
    return out


def show_ladder(screen, name, rung):
    info = LADDERS[name]
    screen.line("")
    screen.line("  {}  -  {}".format(name.upper(), info["move"]), "bold")
    for number, text in enumerate(info["rungs"], 1):
        marker = "->" if number == rung else "  "
        say(screen, "  {} {}. ".format(marker, number), text,
            "green" if number == rung else ("grey" if number > rung else None))
    say(screen, "  Rule: ", info["rule"], "yellow")


def overview(screen, day):
    state = load()
    screen.line("")
    screen.line("== PRACTICE LADDERS ==", "yellow")
    for number, name in enumerate(ORDER, 1):
        ladder = state[name]
        screen.line("")
        screen.row([("bold", "  {}  {:<12}".format(number, name.upper())),
                    ("plain", "rung {} of 5   reps so far: {}   ".format(ladder["rung"], len(ladder["reps"]))),
                    ("green", "done this cycle") if done_this_cycle(ladder, day)
                    else ("grey", "not yet this cycle")])
        say(screen, "     ", LADDERS[name]["rungs"][ladder["rung"] - 1])
        if ladder["plan"]:
            say(screen, "     planned: ", ladder["plan"].get("do", ""), "yellow")
    return state


def pick(screen, prompt):
    answer = fl.ask(screen, prompt + "  1 uncertainty  2 failure  3 conflict (Enter = cancel):")
    return ORDER[int(answer) - 1] if answer in ("1", "2", "3") else None


def plan_rep(screen, day, name):
    """Decide the next rep: what you will do, and what you fear will happen."""
    ladder = load()[name]
    show_ladder(screen, name, ladder["rung"])
    do = fl.ask(screen, "What will your rep be? Something small and specific (Enter = later):")
    if not do:
        return False
    feared = fl.ask(screen, "What are you afraid will happen? (Enter to skip):")
    fl.log(day, "repplan", "ladder: " + name, "rung: {}".format(ladder["rung"]), "do: " + do,
           "feared: " + feared if feared else "")
    screen.line("Planned. It will show on your day page until you log the rep.", "green")
    return True


def log_rep(screen, day, name):
    """Record a rep that was done, then check whether the rung has become boring."""
    ladder = load()[name]
    rung, info, plan = ladder["rung"], LADDERS[name], ladder["plan"] or {}
    screen.line("")
    say(screen, "  {} - rung {}: ".format(name.upper(), rung), info["rungs"][rung - 1], "bold")
    if plan.get("do"):
        say(screen, "  You planned: ", plan["do"], "grey")
    did = fl.ask_required(screen, "What did you do?")
    felt = fl.ask(screen, "What did you feel, in your body or mind? (Enter to skip):")
    outcome = fl.ask_required(screen, "What actually happened - the outcome?")
    feared = plan.get("feared", "")
    if feared:
        say(screen, "  You were afraid of: ", feared, "grey")
    happened = ""
    while happened not in ("y", "n", "partly"):
        happened = fl.ask(screen, "Did the thing you feared happen?  y  n  p = partly:").lower()[:1]
        happened = {"y": "y", "n": "n", "p": "partly"}.get(happened, "")
    hard = str(fl.ask_int(screen, "How hard was it?  1 boring  2 uncomfortable  3 very hard:", 1, 3))
    escaped = fl.ask_yes(screen, info["escape"], False)
    fl.log(day, "rep", "ladder: " + name, "rung: {}".format(rung), "did: " + did,
           "felt: " + felt if felt else "", "outcome: " + outcome,
           "feared: " + feared if feared else "", "feared_happened: " + happened,
           "hard: " + hard, "escaped: " + ("y" if escaped else "n"))
    screen.line("")
    screen.line("Logged. That is a rep.", "green")
    if happened == "n":
        screen.line("The feared thing did not happen. That is what this log is for.", "green")
    elif happened in ("y", "partly"):
        screen.line("It happened, and you are here writing this. That counts just as much.", "green")
    if escaped:
        screen.line("You noticed the escape. Noticing is the first half; next time, skip it.", "grey")
    previous = [rep for rep in ladder["reps"] if rep.get("rung") == str(rung)]
    if hard == "1" and previous and previous[-1].get("hard") == "1" and rung < 5:
        screen.line("This rung has felt boring twice in a row.", "yellow")
        if fl.ask_yes(screen, "Move up to rung {}?".format(rung + 1), False):
            set_rung(screen, day, name, rung + 1)
    elif hard == "3":
        screen.line("Very hard is fine. Stay on this rung, or step down a rung with d.", "grey")


def set_rung(screen, day, name, rung):
    rung = max(1, min(5, rung))
    if rung == load()[name]["rung"]:
        screen.line("{} is already on rung {}.".format(name.capitalize(), rung), "grey")
        return
    fl.log(day, "rung", "ladder: " + name, "rung: {}".format(rung))
    say(screen, "{} is now on rung {}: ".format(name.capitalize(), rung),
        LADDERS[name]["rungs"][rung - 1], "green")


def cycle_plan(screen, day):
    """Cycle planning: offer to choose one rep per ladder for the coming cycle."""
    state = load()
    screen.line("")
    screen.line("== PRACTICE - one rep per ladder this cycle ==", "yellow")
    screen.line("Small and specific. Enter skips a ladder; you can plan it later.", "grey")
    for name in ORDER:
        if not state[name]["plan"]:
            plan_rep(screen, day, name)
        else:
            screen.line("  {} already planned: {}".format(name, state[name]["plan"].get("do", ""))[:78])


def end_of_day(screen, day):
    """One question at the end of the day; Enter moves on."""
    while True:
        answer = fl.ask(screen, "A practice rep today?  1 uncertainty  2 failure  3 conflict  (Enter = no):")
        if answer not in ("1", "2", "3"):
            return
        log_rep(screen, day, ORDER[int(answer) - 1])


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    screen = fl.Screen(fl.load_settings()["display"])
    day = fl.current_day()
    if not day:
        screen.line("Start your first day with  focus  - reps are logged against a focus day.", "grey")
        return
    try:
        while True:
            state = overview(screen, day)
            screen.line("")
            screen.line("  1/2/3 log a rep    p plan one    u up a rung    d down    l read a ladder", "grey")
            answer = fl.ask(screen, "Your choice (Enter = done):").lower()
            if answer in ("1", "2", "3"):
                log_rep(screen, day, ORDER[int(answer) - 1])
            elif answer == "p":
                name = pick(screen, "Plan a rep for:")
                if name:
                    plan_rep(screen, day, name)
            elif answer in ("u", "d"):
                name = pick(screen, "Which ladder?")
                if name:
                    set_rung(screen, day, name, state[name]["rung"] + (1 if answer == "u" else -1))
            elif answer == "l":
                name = pick(screen, "Read which ladder?")
                if name:
                    show_ladder(screen, name, state[name]["rung"])
            elif not answer:
                return
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
