#!/usr/bin/env python3
"""
Receipt Task Manager — Rongta RP331
Manages daily tasks and prints them to a thermal receipt printer.

Setup:
    pip install python-escpos pyusb
    brew install libusb
    python3 receipt_tasks.py setup

Usage:
    python3 receipt_tasks.py sync               # pull today's cert + chore tasks from workbook
    python3 receipt_tasks.py add "buy oat milk" # add a custom task
    python3 receipt_tasks.py done 3             # mark task 3 complete
    python3 receipt_tasks.py list               # show today's tasks in terminal
    python3 receipt_tasks.py print              # print to receipt printer
    python3 receipt_tasks.py print --preview    # print to terminal without printer
    python3 receipt_tasks.py remove 5           # delete a task
    python3 receipt_tasks.py online             # show the online list
    python3 receipt_tasks.py online add "renew library card"
    python3 receipt_tasks.py online clear       # empty the list after your online time
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# ── Paths & constants ─────────────────────────────────────────────────────────

DATA_FILE    = Path.home() / ".receipt_tasks.json"
CONFIG_FILE  = Path.home() / ".receipt_printer.json"
WORKBOOK_DIR = Path(__file__).resolve().parent.parent / "daily-workbook" / "workbooks"
PAPER_WIDTH  = 48  # characters at default font on 80mm paper

WORKBOOK_SOURCES = {"cs311", "leetcode", "pcap", "math", "portfolio", "chore_weekly", "chore"}


# ── Data helpers ──────────────────────────────────────────────────────────────

def today_key() -> str:
    return date.today().isoformat()

def load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def get_today(data: dict) -> dict:
    key = today_key()
    if key not in data:
        data[key] = {"tasks": [], "next_id": 1}
    day = data[key]
    if "next_id" not in day:
        day["next_id"] = max((t["id"] for t in day["tasks"]), default=0) + 1
    return day

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}

def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


# ── Workbook integration ──────────────────────────────────────────────────────

def _import_workbook():
    sys.path.insert(0, str(WORKBOOK_DIR))
    try:
        from dailyWorkbookLocal import CHORE_SCHEDULE
        import cs311  # daily-workbook/cs311.py, on the path via dailyWorkbookLocal
        import leetcode
        return CHORE_SCHEDULE, cs311, leetcode
    except ImportError as e:
        print(f"⚠  Could not import workbook: {e}")
        return None

def get_workbook_tasks() -> list:
    result = _import_workbook()
    if not result:
        return []
    CHORE_SCHEDULE, cs311, leetcode = result

    algo = cs311.daily_set()
    weekday = datetime.now().weekday()
    weekly_task, _, weekly_time = CHORE_SCHEDULE[weekday]

    tasks = []
    if algo["course_order"]:
        topics = list(dict.fromkeys(q["topic"] for q in algo["course_order"]))
        n = len(algo["course_order"]) + (1 if algo["random"] else 0)
        tasks.append({"section": "CERT", "text": f"CS311: {' + '.join(topics)}",
                      "note": f"{n} questions + {len(algo['review'])} review", "source": "cs311"})
    lc = leetcode.daily_set(mark=False)  # the workbook records progress, not the receipt
    if lc["problem"]:
        p = lc["problem"]
        tasks.append({"section": "CERT", "text": f"LeetCode #{p['lc']}: {p['title']}",
                      "note": f"{lc['level']} · {p['pattern']} · {lc['minutes']} min, then submit online",
                      "source": "leetcode"})
    tasks += [
        {"section": "CHORE", "text": f"★ {weekly_task}", "note": weekly_time, "source": "chore_weekly"},
        {"section": "CHORE", "text": "Clear one visible surface",  "note": "5 min", "source": "chore"},
        {"section": "CHORE", "text": "Put away 10 stray items",    "note": "5 min", "source": "chore"},
        {"section": "CHORE", "text": "Reset dishes or sink area",  "note": "5 min", "source": "chore"},
    ]
    return tasks


# ── Offline plan (daily-workbook/offline_plan.py) ─────────────────────────────

def _offline_plan():
    sys.path.insert(0, str(WORKBOOK_DIR.parent))
    try:
        import offline_plan
        return offline_plan
    except ImportError as e:
        print(f"⚠  Could not load offline plan: {e}")
        return None


def _offline_lines() -> list[tuple[str, bool]]:
    """Receipt lines for the offline block, as (text, bold)."""
    op = _offline_plan()
    if op is None:
        return []
    s = op.today_summary()
    lines: list[tuple[str, bool]] = [("", False), (" OFFLINE TODAY", True), ("-" * W, False)]
    lines += [(l, True) for l in _wrap(s["headline"], " ", 1)]
    lines.append(("", False))
    lines.append((" Online list:", False))
    for item in s["online_list"]:
        lines += [(l, False) for l in _wrap(item, " [ ] ", 7)]
    lines += [(" [ ] " + "_" * (W - 6), False) for _ in range(3)]
    if s["exceptions"]:
        lines.append(("", False))
        lines += [(l, False) for l in _wrap(", ".join(s["exceptions"]), " OK online for: ", 2)]
    lines.append(("", False))
    lines.append((" [ ] Stayed offline outside my plan", False))
    lines.append(("     Minutes online today: ______", False))
    return lines


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_online(args):
    op = _offline_plan()
    if op is None:
        return
    action = args.action[0] if args.action else "list"
    if action == "add" and len(args.action) > 1:
        op.add_online_item(" ".join(args.action[1:]))
        print(f"✓ Added to online list: {' '.join(args.action[1:])}")
    elif action == "clear":
        op.save_online_list([])
        print("✓ Online list cleared")
    elif action == "list":
        s = op.today_summary()
        print(f"\n── {s['headline']} ──")
        for i, item in enumerate(s["online_list"], 1):
            print(f"  {i:>2}.  {item}")
        if not s["online_list"]:
            print("  (empty)  Add with:  python3 receipt_tasks.py online add \"...\"")
        print()
    else:
        print('Usage: online | online add "text" | online clear')


def cmd_sync(args):
    data  = load_data()
    today = get_today(data)
    today["tasks"] = [t for t in today["tasks"] if t.get("source") not in WORKBOOK_SOURCES]

    tasks = get_workbook_tasks()
    for wt in tasks:
        today["tasks"].append({
            "id":      today["next_id"],
            "text":    wt["text"],
            "note":    wt.get("note", ""),
            "section": wt["section"],
            "source":  wt["source"],
            "done":    False,
        })
        today["next_id"] += 1

    save_data(data)
    print(f"✓ Synced {len(tasks)} workbook tasks for {today_key()}")


def cmd_add(args):
    data  = load_data()
    today = get_today(data)
    text  = " ".join(args.task)
    task  = {
        "id":      today["next_id"],
        "text":    text,
        "note":    "",
        "section": "CUSTOM",
        "source":  "custom",
        "done":    False,
    }
    today["tasks"].append(task)
    today["next_id"] += 1
    save_data(data)
    print(f"✓ [{task['id']}] {text}")


def cmd_done(args):
    data  = load_data()
    today = get_today(data)
    for t in today["tasks"]:
        if t["id"] == args.id:
            t["done"] = True
            save_data(data)
            print(f"✓ Done: {t['text']}")
            return
    print(f"⚠  No task with id {args.id}")


def cmd_undone(args):
    data  = load_data()
    today = get_today(data)
    for t in today["tasks"]:
        if t["id"] == args.id:
            t["done"] = False
            save_data(data)
            print(f"↩  Reopened: {t['text']}")
            return
    print(f"⚠  No task with id {args.id}")


def cmd_remove(args):
    data  = load_data()
    today = get_today(data)
    before = len(today["tasks"])
    today["tasks"] = [t for t in today["tasks"] if t["id"] != args.id]
    if len(today["tasks"]) < before:
        save_data(data)
        print(f"✓ Removed task {args.id}")
    else:
        print(f"⚠  No task with id {args.id}")


def cmd_list(args):
    data  = load_data()
    today = get_today(data)
    tasks = today["tasks"]

    if not tasks:
        print("No tasks today. Run:  python3 receipt_tasks.py sync")
        return

    done_count = sum(1 for t in tasks if t["done"])
    print(f"\n── {today_key()} · {done_count}/{len(tasks)} done ──")

    for section_key, label in [("CERT","STUDY"), ("CHORE","CHORES"), ("CUSTOM","CUSTOM")]:
        section_tasks = [t for t in tasks if t.get("section") == section_key]
        if not section_tasks:
            continue
        print(f"\n  {label}")
        for t in section_tasks:
            box  = "✓" if t["done"] else " "
            note = f"  ·  {t['note']}" if t["note"] else ""
            print(f"  [{box}] {t['id']:>2}.  {t['text']}{note}")
    print()


# ── Receipt formatting ────────────────────────────────────────────────────────

W = PAPER_WIDTH

def _wrap(text: str, first_prefix: str, cont_indent: int) -> list[str]:
    """Wrap text to PAPER_WIDTH with a prefix on the first line."""
    available = W - len(first_prefix)
    if len(text) <= available:
        return [first_prefix + text]
    lines, words = [], text.split()
    cur = ""
    for word in words:
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= available:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
            available = W - cont_indent
    if cur:
        lines.append(cur)
    result = [first_prefix + lines[0]] if lines else [first_prefix + text]
    for l in lines[1:]:
        result.append(" " * cont_indent + l)
    return result


def _build_receipt(tasks: list) -> list[str]:
    now       = datetime.now().strftime("%-I:%M %p")
    day_str   = datetime.now().strftime("%a %d %b %Y").upper()
    done      = sum(1 for t in tasks if t["done"])
    lines     = []

    lines.append("=" * W)
    lines.append("DAILY TASKS".center(W))
    lines.append(day_str.center(W))
    lines.append("=" * W)

    for section_key, label in [("CERT","STUDY"), ("CHORE","CHORES"), ("CUSTOM","CUSTOM")]:
        section_tasks = [t for t in tasks if t.get("section") == section_key]
        if not section_tasks:
            continue
        lines.append("")
        lines.append(f" {label}")
        lines.append("-" * W)
        for t in section_tasks:
            box    = "X" if t["done"] else " "
            prefix = f" [{box}] "
            indent = len(prefix) + 2
            for l in _wrap(t["text"], prefix, indent):
                lines.append(l)
            if t.get("note"):
                note_prefix = " " * indent
                for l in _wrap(t["note"], note_prefix, indent):
                    lines.append(l)

    lines += [text for text, _ in _offline_lines()]

    lines.append("")
    lines.append("=" * W)
    lines.append(f"{done} of {len(tasks)} done".center(W))
    lines.append(f"printed {now}".center(W))
    lines.append("=" * W)
    lines.append("")
    lines.append("")
    return lines


# ── Printer ───────────────────────────────────────────────────────────────────

def _get_printer():
    cfg = load_config()
    if not cfg:
        print("⚠  Printer not configured. Run:  python3 receipt_tasks.py setup")
        return None
    try:
        from escpos import printer as ep
        conn = cfg.get("connection", "usb")
        if conn == "usb":
            return ep.Usb(cfg["vendor_id"], cfg["product_id"],
                          profile=cfg.get("profile", "TM-T88II"))
        if conn == "file":
            return ep.File(cfg["device"])
        if conn == "cups":
            return ep.CupsPrinter(cfg["printer_name"])
    except ImportError:
        print("⚠  python-escpos not installed.\n   Run: pip install python-escpos pyusb")
    except Exception as e:
        print(f"⚠  Printer connection failed: {e}")
    return None


def cmd_print(args):
    data  = load_data()
    today = get_today(data)
    tasks = today["tasks"]

    if not tasks:
        print("No tasks to print. Run 'sync' first.")
        return

    receipt = _build_receipt(tasks)

    if getattr(args, "preview", False):
        for l in receipt:
            print(l)
        return

    p = _get_printer()
    if p is None:
        print("\n── Receipt preview (no printer) ──")
        for l in receipt:
            print(l)
        return

    try:
        done = sum(1 for t in tasks if t["done"])
        day_str = datetime.now().strftime("%a %d %b %Y").upper()
        now     = datetime.now().strftime("%-I:%M %p")

        p.set(align="center", bold=True, double_height=True, double_width=True)
        p.text("DAILY TASKS\n")
        p.set(align="center", bold=False, double_height=False, double_width=False)
        p.text(f"{day_str}\n")
        p.text("=" * W + "\n")

        for section_key, label in [("CERT","STUDY"), ("CHORE","CHORES"), ("CUSTOM","CUSTOM")]:
            section_tasks = [t for t in tasks if t.get("section") == section_key]
            if not section_tasks:
                continue
            p.text("\n")
            p.set(bold=True)
            p.text(f" {label}\n")
            p.set(bold=False)
            p.text("-" * W + "\n")
            for t in section_tasks:
                box    = "X" if t["done"] else " "
                prefix = f" [{box}] "
                indent = len(prefix) + 2
                for l in _wrap(t["text"], prefix, indent):
                    p.text(l + "\n")
                if t.get("note"):
                    for l in _wrap(t["note"], " " * indent, indent):
                        p.text(l + "\n")

        for text, bold in _offline_lines():
            p.set(bold=bold)
            p.text(text + "\n")
        p.set(bold=False)

        p.text("\n" + "=" * W + "\n")
        p.set(align="center")
        p.text(f"{done} of {len(tasks)} done\n")
        p.text(f"printed {now}\n")
        p.text("=" * W + "\n\n")
        p.cut()
        print(f"✓ Printed {len(tasks)} tasks")
    except Exception as e:
        print(f"⚠  Print failed: {e}")


# ── Setup: auto-detect printer ────────────────────────────────────────────────

def cmd_setup(args):
    print("Scanning USB devices...")
    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPUSBDataType", "-json"],
            text=True, timeout=15,
        )
        usb_data = json.loads(raw)
    except Exception as e:
        print(f"⚠  Could not scan USB: {e}")
        usb_data = {}

    found = None

    def walk(node):
        nonlocal found
        if isinstance(node, dict):
            name = node.get("_name", "")
            if any(k in name.lower() for k in ["rongta", "rp331", "printer", "pos", "receipt"]):
                vid = node.get("vendor_id", "")
                pid = node.get("product_id", "")
                if vid and pid:
                    found = {"name": name, "vendor_id": vid, "product_id": pid}
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(usb_data)

    if found:
        def parse_hex(s: str) -> int:
            return int(s.strip().lower().replace("0x", ""), 16)

        vid = parse_hex(found["vendor_id"])
        pid = parse_hex(found["product_id"])
        cfg = {"connection": "usb", "vendor_id": vid, "product_id": pid, "profile": "TM-T88II"}
        save_config(cfg)
        print(f"✓ Found: {found['name']}")
        print(f"  Vendor ID:   0x{vid:04x}  ({vid})")
        print(f"  Product ID:  0x{pid:04x}  ({pid})")
        print(f"✓ Config saved → {CONFIG_FILE}")
        print("\nNext steps:")
        print("  pip install python-escpos pyusb")
        print("  brew install libusb")
        print("  python3 receipt_tasks.py sync && python3 receipt_tasks.py print --preview")
    else:
        print("⚠  Printer not auto-detected.")
        print("   Make sure it's plugged in and powered on, then try again.")
        print()
        print("   Or set manually — common Rongta values:")
        print(f"   echo '{{\"connection\":\"usb\",\"vendor_id\":1155,\"product_id\":1803,\"profile\":\"TM-T88II\"}}' > {CONFIG_FILE}")
        print("   (1155 = 0x0483, 1803 = 0x070b)")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="receipt_tasks",
        description="Receipt task manager for Rongta RP331",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 receipt_tasks.py sync\n"
            "  python3 receipt_tasks.py add 'call dentist'\n"
            "  python3 receipt_tasks.py done 2\n"
            "  python3 receipt_tasks.py print\n"
            "  python3 receipt_tasks.py print --preview"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("sync",   help="Pull today's cert + chore tasks from the workbook")
    sub.add_parser("list",   help="Show today's tasks in the terminal")
    sub.add_parser("setup",  help="Auto-detect and configure the receipt printer")

    p_print = sub.add_parser("print", help="Print today's tasks to the receipt printer")
    p_print.add_argument("--preview", action="store_true", help="Print to terminal instead of printer")

    p_add = sub.add_parser("add", help="Add a custom task")
    p_add.add_argument("task", nargs="+", help="Task description")

    p_done = sub.add_parser("done", help="Mark a task complete")
    p_done.add_argument("id", type=int, metavar="ID")

    p_undone = sub.add_parser("undone", help="Reopen a completed task")
    p_undone.add_argument("id", type=int, metavar="ID")

    p_rm = sub.add_parser("remove", help="Delete a task")
    p_rm.add_argument("id", type=int, metavar="ID")

    p_online = sub.add_parser("online", help="Show or edit the online list (things to do in your online time)")
    p_online.add_argument("action", nargs="*", help='nothing to list, add "text", or clear')

    args = parser.parse_args()

    dispatch = {
        "sync":   cmd_sync,
        "add":    cmd_add,
        "done":   cmd_done,
        "undone": cmd_undone,
        "list":   cmd_list,
        "remove": cmd_remove,
        "print":  cmd_print,
        "setup":  cmd_setup,
        "online": cmd_online,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
