#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ---------- Printer / receipt settings ----------
LINE_WIDTH = 32                  # common for 58mm paper
TITLE_SCALE_W = 2                # big title width multiplier
TITLE_SCALE_H = 2                # big title height multiplier
TITLE_WRAP_WIDTH = LINE_WIDTH // 2  # big text fits fewer chars
DEFAULT_ALLDAY_TIME = "23:59"    # only used if you store date-only due without all_day true


# ---------- ESC/POS helpers ----------
def esc_align(n: int) -> bytes:  # 0=left 1=center 2=right
    return b"\x1ba" + bytes([n])

def esc_bold(on: bool) -> bytes:
    return b"\x1bE" + (b"\x01" if on else b"\x00")

def esc_size(width_mult: int, height_mult: int) -> bytes:
    w = max(1, min(8, width_mult))
    h = max(1, min(8, height_mult))
    n = ((w - 1) << 4) | (h - 1)
    return b"\x1d!" + bytes([n])

def esc_reset_text() -> bytes:
    return esc_size(1, 1) + esc_bold(False) + esc_align(0)

def esc_full_cut() -> bytes:
    return b"\x1dV\x00"

def esc_partial_cut() -> bytes:
    return b"\x1dV\x01"


# ---------- Data model ----------
@dataclass(frozen=True)
class Item:
    id: str
    type: str
    course: str
    title: str
    due_dt: datetime | None      # for assignments/quizzes/projects/discussions
    start_dt: datetime | None    # for exams/events
    end_dt: datetime | None
    all_day: bool
    late_dt: datetime | None
    raw: dict


def safe_text(s: str) -> str:
    # Replace common non-ASCII chars that ESC/POS fonts often can't render
    repl = {
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "•": "*",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


def parse_dt(s: str, tz: ZoneInfo) -> datetime:
    """
    Accepts:
      - "YYYY-MM-DD"
      - "YYYY-MM-DD HH:MM"
    Returns timezone-aware datetime.
    """
    s = s.strip()
    if len(s) == 10:  # date only
        s = f"{s} {DEFAULT_ALLDAY_TIME}"
    # allow " " separator
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def fmt_due(d: datetime, all_day: bool) -> str:
    # If all-day, print date only; else print date + time.
    if all_day:
        return d.strftime("%a %b ") + str(d.day) + d.strftime(", %Y")
    ampm = d.strftime("%I:%M%p").lower()
    if ampm.startswith("0"):
        ampm = ampm[1:]
    return f"{d.strftime('%a %b')} {d.day}, {ampm}"


def wrap_kv(key: str, value: str, width: int = LINE_WIDTH) -> str:
    prefix = f"{key}: "
    available = max(1, width - len(prefix))
    lines = textwrap.wrap(value, width=available) or [""]
    out = [prefix + lines[0]]
    indent = " " * len(prefix)
    for line in lines[1:]:
        out.append(indent + line)
    return "\n".join(out)


# ---------- Ledger ----------
def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def ledger_path_for(tasks_path: str) -> str:
    # Keep ledger next to tasks.json
    base_dir = os.path.dirname(os.path.abspath(tasks_path))
    return os.path.join(base_dir, "printed_ledger.json")

def load_ledger(path: str) -> dict:
    if not os.path.exists(path):
        return {"printed": {}}  # id -> timestamp
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_ledger(path: str, ledger: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)


# ---------- Loading tasks ----------
def load_items(tasks_json_path: str, tz: ZoneInfo) -> list[Item]:
    data = load_json(tasks_json_path)
    items = data.get("items", [])
    out: list[Item] = []

    for r in items:
        item_id = r.get("id")
        itype = r.get("type", "task")
        course = r.get("course", "").strip()
        title = r.get("title", "").strip()
        all_day = bool(r.get("all_day", False))

        due_dt = None
        start_dt = None
        end_dt = None
        late_dt = None

        if "late_due" in r and r["late_due"]:
            late_dt = parse_dt(str(r["late_due"]), tz)

        if "due" in r and r["due"]:
            # If due is date-only and all_day isn't set, we treat it as end-of-day
            s = str(r["due"])
            if len(s.strip()) == 10:
                all_day = True if r.get("all_day", False) else True  # date-only => treat as all-day
            due_dt = parse_dt(s, tz)

        if "start" in r and r["start"]:
            start_dt = parse_dt(str(r["start"]), tz)
        if "end" in r and r["end"]:
            end_dt = parse_dt(str(r["end"]), tz)

        out.append(
            Item(
                id=item_id,
                type=itype,
                course=course,
                title=title,
                due_dt=due_dt,
                start_dt=start_dt,
                end_dt=end_dt,
                all_day=all_day,
                late_dt=late_dt,
                raw=r,
            )
        )

    return out


def effective_datetime(item: Item) -> datetime | None:
    # Used for sorting & filtering windows
    return item.due_dt or item.start_dt


# ---------- Tagging ----------
def compute_tag(item: Item, now: datetime, mode: str) -> str:
    if "tag" in item.raw and item.raw["tag"]:
        return str(item.raw["tag"])

    if mode == "type":
        return item.type.upper()

    # urgency mode (default)
    d = effective_datetime(item)
    if d is None:
        return item.type.upper()

    # all-day comparisons should be by date
    if item.all_day:
        d_date = d.date()
        n_date = now.date()
        if d_date < n_date:
            return "PAST DUE"
        if d_date == n_date:
            return "TODAY"
        # this week vs next week
        sow = (now - timedelta(days=now.weekday())).date()
        eow = sow + timedelta(days=6)
        if sow <= d_date <= eow:
            return "THIS WEEK"
        return "UPCOMING"

    # timed tasks
    if d < now:
        return "PAST DUE"
    if d.date() == now.date():
        return "TODAY"
    sow = (now - timedelta(days=now.weekday())).date()
    eow = sow + timedelta(days=6)
    if sow <= d.date() <= eow:
        return "THIS WEEK"
    return "UPCOMING"


# ---------- Receipt rendering ----------
def make_receipt_bytes(item: Item, now: datetime, tag_mode: str, cut: str, cut_feed: int) -> bytes:
    title = safe_text(item.title).strip()
    course = safe_text(item.course).strip()
    tag = safe_text(compute_tag(item, now, tag_mode)).strip()

    # Due line
    if item.type == "exam" and item.start_dt:
        if item.end_dt:
            due_str = f"{fmt_due(item.start_dt, False)}–{item.end_dt.strftime('%I:%M%p').lower().lstrip('0')}"
        else:
            due_str = fmt_due(item.start_dt, False)
    else:
        # assignments/quizzes/etc
        if item.due_dt is None:
            due_str = "—"
        else:
            due_str = fmt_due(item.due_dt, item.all_day)
            if item.late_dt:
                due_str += f" (Late: {fmt_due(item.late_dt, item.all_day)})"

    # Build ESC/POS payload
    b = b""

    # Big, prominent title
    b += esc_align(1)
    b += esc_bold(True)
    b += esc_size(TITLE_SCALE_W, TITLE_SCALE_H)
    for line in textwrap.wrap(title.upper(), width=TITLE_WRAP_WIDTH) or [""]:
        b += line.encode("ascii", "replace") + b"\n"

    b += esc_reset_text()
    b += esc_align(0)

    # Body fields (your chosen minimal receipt fields + Tag)
    b += wrap_kv("Due", due_str).encode("ascii", "replace") + b"\n"
    b += wrap_kv("Class", course).encode("ascii", "replace") + b"\n"
    b += wrap_kv("Tag", tag).encode("ascii", "replace") + b"\n"
    b += (b"-" * LINE_WIDTH) + b"\n"

    # Feed before cut
    b += b"\n" * max(0, cut_feed)

    # Cut
    b += esc_partial_cut() if cut == "partial" else esc_full_cut()
    b += b"\n"
    return b


# ---------- Printing ----------
def list_printers() -> None:
    subprocess.run(["lpstat", "-p"], check=False)

def lp_print_raw(printer: str, payload: bytes, copies: int) -> None:
    cmd = ["lp", "-d", printer, "-n", str(copies), "-o", "raw"]
    subprocess.run(cmd, input=payload, check=True)


# ---------- Selection logic ----------
def select_window(
    items: list[Item],
    now: datetime,
    start: datetime | None,
    end: datetime | None,
    include_past_due: bool,
) -> list[Item]:
    sel: list[Item] = []
    for it in items:
        d = effective_datetime(it)
        if d is None:
            continue

        if start and d < start:
            continue
        if end and d > end:
            continue

        if not include_past_due and d < now:
            continue

        sel.append(it)

    sel.sort(key=lambda x: (effective_datetime(x), x.course, x.title))
    return sel


def monday_of_week(ref: datetime) -> datetime:
    return (ref - timedelta(days=ref.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

def sunday_end_of_week(ref: datetime) -> datetime:
    return monday_of_week(ref) + timedelta(days=6, hours=23, minutes=59, seconds=59)


# ---------- CLI ----------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Print task receipts from a JSON master list (ESC/POS big title + cutter)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # list-printers
    sub.add_parser("list-printers", help="Show CUPS printer queues (lpstat -p).")

    # status
    p_status = sub.add_parser("status", help="Show summary of tasks + what would print in a window.")
    p_status.add_argument("--file", required=True, help="Path to tasks JSON (e.g., tasks.json).")
    p_status.add_argument("--days", type=int, default=7, help="Window length from now (default 7).")
    p_status.add_argument("--include-past-due", action="store_true", help="Include tasks already past due.")
    p_status.add_argument("--as-of", help="Override 'now' (YYYY-MM-DD or YYYY-MM-DD HH:MM).")

    # print-window
    p_pw = sub.add_parser("print-window", help="Print NEW receipts due in the next N days (avoids duplicates).")
    p_pw.add_argument("--file", required=True, help="Path to tasks JSON (e.g., tasks.json).")
    p_pw.add_argument("--printer", required=True, help="CUPS printer queue (e.g., LifeChangingPrinterGuy).")
    p_pw.add_argument("--days", type=int, default=7, help="Window length from now (default 7).")
    p_pw.add_argument("--include-past-due", action="store_true", help="Also include past-due items not yet printed.")
    p_pw.add_argument("--force", action="store_true", help="Print even if already printed before.")
    p_pw.add_argument("--preview", action="store_true", help="Preview in terminal (no printing).")
    p_pw.add_argument("--copies", type=int, default=1, help="Copies (default 1).")
    p_pw.add_argument("--cut", choices=["full", "partial"], default="full", help="Cut mode (default full).")
    p_pw.add_argument("--cut-feed", type=int, default=4, help="Blank lines before cut (default 4).")
    p_pw.add_argument("--tag-mode", choices=["urgency", "type"], default="urgency",
                      help="Tag field content: urgency (THIS WEEK/TODAY/...) or type (QUIZ/EXAM/...).")
    p_pw.add_argument("--as-of", help="Override 'now' (YYYY-MM-DD or YYYY-MM-DD HH:MM).")

    # print-week
    p_wk = sub.add_parser("print-week", help="Print NEW receipts due Mon–Sun of a given week (avoids duplicates).")
    p_wk.add_argument("--file", required=True, help="Path to tasks JSON (e.g., tasks.json).")
    p_wk.add_argument("--printer", required=True, help="CUPS printer queue (e.g., LifeChangingPrinterGuy).")
    p_wk.add_argument("--week-offset", type=int, default=0, help="0=this week, 1=next week, -1=last week.")
    p_wk.add_argument("--include-past-due", action="store_true",
                      help="Include past-due items too (still avoids duplicates unless --force).")
    p_wk.add_argument("--force", action="store_true", help="Print even if already printed before.")
    p_wk.add_argument("--preview", action="store_true", help="Preview in terminal (no printing).")
    p_wk.add_argument("--copies", type=int, default=1, help="Copies (default 1).")
    p_wk.add_argument("--cut", choices=["full", "partial"], default="full", help="Cut mode (default full).")
    p_wk.add_argument("--cut-feed", type=int, default=4, help="Blank lines before cut (default 4).")
    p_wk.add_argument("--tag-mode", choices=["urgency", "type"], default="urgency",
                      help="Tag field content: urgency or type.")
    p_wk.add_argument("--as-of", help="Override 'now' (YYYY-MM-DD or YYYY-MM-DD HH:MM).")

    # reprint (by id)
    p_rp = sub.add_parser("reprint", help="Reprint specific task IDs (ignores duplicate prevention).")
    p_rp.add_argument("--file", required=True, help="Path to tasks JSON (e.g., tasks.json).")
    p_rp.add_argument("--printer", required=True, help="CUPS printer queue (e.g., LifeChangingPrinterGuy).")
    p_rp.add_argument("--id", action="append", required=True, help="Task ID to print (repeatable).")
    p_rp.add_argument("--preview", action="store_true", help="Preview in terminal (no printing).")
    p_rp.add_argument("--copies", type=int, default=1, help="Copies (default 1).")
    p_rp.add_argument("--cut", choices=["full", "partial"], default="full", help="Cut mode (default full).")
    p_rp.add_argument("--cut-feed", type=int, default=4, help="Blank lines before cut (default 4).")
    p_rp.add_argument("--tag-mode", choices=["urgency", "type"], default="urgency",
                      help="Tag field content: urgency or type.")
    p_rp.add_argument("--as-of", help="Override 'now' (YYYY-MM-DD or YYYY-MM-DD HH:MM).")

    args = ap.parse_args()

    if args.cmd == "list-printers":
        list_printers()
        return 0

    # Load timezone from JSON if present, else default to America/New_York
    data = load_json(args.file)
    tz_name = data.get("timezone", "America/New_York")
    tz = ZoneInfo(tz_name)

    now = datetime.now(tz)
    if getattr(args, "as_of", None):
        now = parse_dt(args.as_of, tz)

    items = load_items(args.file, tz)
    led_path = ledger_path_for(args.file)
    ledger = load_ledger(led_path)
    printed: dict = ledger.get("printed", {})

    def not_printed(it: Item) -> bool:
        return it.id not in printed

    def preview_list(sel: list[Item]) -> None:
        print(f"Timezone: {tz_name}")
        print(f"As-of: {now.isoformat(sep=' ', timespec='minutes')}")
        print("-" * LINE_WIDTH)
        for it in sel:
            d = effective_datetime(it)
            when = d.isoformat(sep=" ", timespec="minutes") if d else "—"
            print(f"{it.id} | {it.course} | {it.title} | {when}")

    if args.cmd == "status":
        end = now + timedelta(days=args.days)
        sel = select_window(items, now, start=None, end=end, include_past_due=args.include_past_due)
        sel_new = [it for it in sel if not_printed(it)]
        print(f"Total items in file: {len(items)}")
        print(f"Printed (in ledger): {len(printed)}  (ledger: {led_path})")
        print(f"Window: now → +{args.days} days ({end.date()})")
        print(f"Would print (new only): {len(sel_new)}")
        print("-" * LINE_WIDTH)
        preview_list(sel_new[:30])
        if len(sel_new) > 30:
            print(f"... and {len(sel_new) - 30} more")
        return 0

    def do_print(selection: list[Item], printer: str, copies: int, cut: str, cut_feed: int,
                 tag_mode: str, force: bool, preview: bool, update_ledger: bool) -> int:
        # Filter duplicates unless force
        to_print = selection if force else [it for it in selection if not_printed(it)]

        if preview:
            print(f"Preview only. Items to print: {len(to_print)}")
            print("-" * LINE_WIDTH)
            preview_list(to_print)
            return 0

        if not to_print:
            print("Nothing to print (either empty window or everything already printed).")
            return 0

        payload = b""
        for it in to_print:
            payload += make_receipt_bytes(it, now, tag_mode, cut, cut_feed)

        lp_print_raw(printer, payload, copies)

        if update_ledger:
            stamp = now.isoformat(sep=" ", timespec="seconds")
            for it in to_print:
                printed[it.id] = stamp
            ledger["printed"] = printed
            save_ledger(led_path, ledger)

        print(f"Printed {len(to_print)} receipts to {printer} (copies={copies}, cut={cut}).")
        print(f"Ledger updated: {led_path}")
        return 0

    if args.cmd == "print-window":
        end = now + timedelta(days=args.days)
        sel = select_window(items, now, start=None, end=end, include_past_due=args.include_past_due)
        return do_print(sel, args.printer, args.copies, args.cut, args.cut_feed, args.tag_mode,
                        args.force, args.preview, update_ledger=True)

    if args.cmd == "print-week":
        ref = now + timedelta(days=7 * args.week_offset)
        wk_start = monday_of_week(ref)
        wk_end = sunday_end_of_week(ref)
        sel = select_window(items, now, start=wk_start, end=wk_end, include_past_due=args.include_past_due)
        return do_print(sel, args.printer, args.copies, args.cut, args.cut_feed, args.tag_mode,
                        args.force, args.preview, update_ledger=True)

    if args.cmd == "reprint":
        want = set(args.id)
        sel = [it for it in items if it.id in want]
        sel.sort(key=lambda x: (effective_datetime(x), x.course, x.title))
        # reprint should NOT update ledger (you already printed it before, and this is intentional)
        return do_print(sel, args.printer, args.copies, args.cut, args.cut_feed, args.tag_mode,
                        force=True, preview=args.preview, update_ledger=False)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

