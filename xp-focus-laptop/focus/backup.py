# Copy the whole focus folder to the USB stick, plus progress.json for the Mac.
# Run:  focus backup      (or: python backup.py)
import json
import os
import shutil

import focuslib as fl

try:
    import ctypes
except ImportError:
    ctypes = None

HELP = """
backup.py - copy C:\\focus to the USB stick

  focus backup

Finds the USB stick, then copies every file in C:\\focus into a folder
called focus-backup on it (replacing the last backup). It also writes
progress.json: your days, pomodoros and finished tasks in a form the
Mac can read later for the workbook.
Plug the stick in first. Use "Safely Remove Hardware" afterwards.
"""


def removable_drives():
    """Drive letters of USB sticks (Windows only)."""
    found = []
    if os.name != "nt" or ctypes is None:
        return found
    try:
        kernel = ctypes.windll.kernel32
        mask = kernel.GetLogicalDrives()
        for i in range(2, 26):                      # skip A: and B:
            root = "{}:\\".format(chr(65 + i))
            if mask & (1 << i) and kernel.GetDriveTypeW(root) == 2:
                found.append(root)
    except Exception:
        pass
    return found


def progress():
    days = fl.read_log()
    backlog = fl.load_backlog()
    done = [fl.parse_item(line) for line in backlog["DONE"]]
    return {
        "days": [dict(info, day=day) for day, info in days.items()],
        "done": done,
        "open": dict((name, backlog[name]) for name in fl.SECTIONS[:-1]),
        "routines": [{"name": name, "times": times} for name, times in fl.load_routines()],
        "ticks": dict((str(day), ticked) for day, ticked in fl.read_ticks().items()),
        "totals": {
            "focus_days": len(days),
            "pomodoros": sum(len(info["focus"]) for info in days.values()),
            "points_done": sum(item["points"] or 0 for item in done),
        },
    }


def copy_to(target):
    with open(fl.path("progress.json"), "w", encoding="utf-8") as handle:
        json.dump(progress(), handle, indent=1, sort_keys=True)
    if not os.path.isdir(target):
        os.makedirs(target)
    copied = 0
    for name in sorted(os.listdir(fl.HERE)):
        source = os.path.join(fl.HERE, name)
        if os.path.isfile(source) and not name.endswith((".pyc", ".pyo")):
            shutil.copy2(source, os.path.join(target, name))
            copied += 1
    return copied


def run(screen, target=None):
    if target is None:
        drives = removable_drives()
        if len(drives) == 1:
            root = drives[0]
            screen.line("  Found the USB stick at {}".format(root))
        else:
            if drives:
                screen.line("  USB sticks found: {}".format("  ".join(drives)))
            else:
                screen.line("  No USB stick found. Plug it in, or type its letter.", "yellow")
            letter = fl.ask(screen, "  Drive letter of the stick, like E (Enter = cancel):")
            if not letter:
                screen.line("  No backup made.", "grey")
                return False
            root = letter if len(letter) > 2 else "{}:\\".format(letter[0].upper())
        if not os.path.isdir(root):
            screen.line("  Cannot open {} - no backup made.".format(root), "red")
            return False
        target = os.path.join(root, "focus-backup")
    try:
        copied = copy_to(target)
    except (IOError, OSError) as error:
        screen.line("  Backup failed: {}".format(error), "red")
        return False
    screen.line("  Backed up {} files to {}".format(copied, target), "green")
    screen.line("  Use Safely Remove Hardware before unplugging.", "grey")
    return True


def main():
    if fl.help_requested(HELP):
        return
    fl.fix_streams()
    try:
        run(fl.Screen(fl.load_settings()["display"]))
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
