#!/usr/bin/env python3
"""
Send the week's print files (made by print_batch.py) to the ESP32 workbook
printer, which prints each one on its morning.

    python3 push_to_esp.py                 # upload new/changed days, drop old ones
    python3 push_to_esp.py status          # what the ESP32 has and did last
    python3 push_to_esp.py test-print 2026-11-10 --pages 1-1
                                           # print one page right now, to check it works
    python3 push_to_esp.py check-printer   # ask the HP (from the Mac, no ESP32 needed)
                                           # whether it accepts the job the ESP32 sends;
                                           # nothing prints

Needs the Mac and the ESP32 on the same Wi-Fi. Standard library only.
"""

import argparse
import http.client
import json
import struct
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

QUEUE_DIR = Path(__file__).resolve().parent / "workbooks" / "print_queue"
DEFAULT_HOST = "workbook-printer.local"
PRINTER_HOST = "HP846993D5E29E.local"   # keep in sync with esp32-printer/include/config.h


def ipp_request(op: int, pages: tuple[int, int] | None, sides: str, fmt: str) -> bytes:
    """Same bytes as printJobRequest() in esp32-printer/src/main.cpp (op 2 = Print-Job)."""
    def attr(tag, name, val):
        n, v = name.encode(), val.encode()
        return bytes([tag]) + struct.pack(">H", len(n)) + n + struct.pack(">H", len(v)) + v
    b = bytes([2, 0]) + struct.pack(">HI", op, 1) + b"\x01"
    b += attr(0x47, "attributes-charset", "utf-8") + attr(0x48, "attributes-natural-language", "en")
    b += attr(0x45, "printer-uri", f"ipp://{PRINTER_HOST}:631/ipp/print")
    b += attr(0x42, "requesting-user-name", "workbook") + attr(0x42, "job-name", "Workbook check")
    b += attr(0x49, "document-format", fmt)
    b += b"\x02" + attr(0x44, "media", "na_letter_8.5x11in") + attr(0x44, "sides", sides)
    if pages:
        n = b"page-ranges"
        b += b"\x33" + struct.pack(">H", len(n)) + n + struct.pack(">Hii", 8, *pages)
    return b + b"\x03"


def check_printer() -> int:
    """Validate-Job (op 4): the printer checks the request but prints nothing."""
    cases = [("PCLm, all pages", None, "one-sided", "application/PCLm", True),
             ("PCLm, one page (test-print)", (1, 1), "one-sided", "application/PCLm", True),
             ("PCLm, two-sided", None, "two-sided-long-edge", "application/PCLm", True),
             ("PDF (expected: refused)", None, "one-sided", "application/pdf", False)]
    bad = 0
    for label, pages, sides, fmt, should_pass in cases:
        try:
            c = http.client.HTTPConnection(PRINTER_HOST, 631, timeout=15)
            c.request("POST", "/ipp/print", ipp_request(4, pages, sides, fmt), {"Content-Type": "application/ipp"})
            r = c.getresponse(); d = r.read()
        except OSError as e:
            sys.exit(f"✗ Can't reach the printer at {PRINTER_HOST} ({e}). Is it on and awake?")
        st = struct.unpack(">H", d[2:4])[0] if len(d) >= 4 else 0xFFFF
        ok = r.status == 200 and st < 0x100
        bad += ok != should_pass
        print(f"{'✓' if ok == should_pass else '✗'} {label:30} HTTP {r.status}, IPP status 0x{st:04x}")
    return 1 if bad else 0


def call(host: str, method: str, path: str, body_path: Path | None = None, timeout: float = 30):
    url = f"http://{host}{path}"
    if body_path:
        f = body_path.open("rb")
        req = urllib.request.Request(url, data=f, method=method, headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(body_path.stat().st_size)})
    else:
        f = None
        req = urllib.request.Request(url, data=b"" if method != "GET" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}") | {"http_error": e.code}
    finally:
        if f:
            f.close()


def status(host: str) -> dict:
    try:
        return call(host, "GET", "/status", timeout=10)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        sys.exit(f"✗ Can't reach the ESP32 at {host} ({e}).\n"
                 f"  Is it powered and on the same Wi-Fi? Try its IP with --host.")


def show_status(s: dict) -> None:
    print(f"Clock:        {s['clock']}")
    print(f"Prints at:    {s['print_time']}  →  {s['printer']}")
    print(f"Last printed: {s['last_printed'] or '—'}")
    print(f"Last result:  {s['last_result']}")
    print(f"SD card:      {'ok' if s['sd_ok'] else 'NOT FOUND'}, {s['free_bytes'] / 1e9:.1f} GB free")
    files = [f for f in s["files"] if f["name"].endswith(".pclm")]
    print("Days loaded:  " + (", ".join(f["name"][:10] for f in sorted(files, key=lambda f: f["name"])) or "none"))


def push(host: str) -> int:
    manifest_path = QUEUE_DIR / "manifest.json"
    if not manifest_path.exists():
        sys.exit("✗ No print queue yet. Run print_batch.py first.")
    manifest = json.loads(manifest_path.read_text())
    today = date.today().isoformat()

    s = status(host)
    if not s["sd_ok"]:
        sys.exit("✗ The ESP32 has no SD card (or can't read it).")
    on_device = {f["name"]: f["bytes"] for f in s["files"]}

    failed = 0
    for day in manifest["days"]:
        name, size = day["file"], day["bytes"]
        if day["date"] < today:
            continue
        if on_device.get(name) == size:
            print(f"· {day['date']}: already there")
            continue
        print(f"⏳ {day['date']}: uploading {size / 1e6:.1f} MB …", end="", flush=True)
        r = call(host, "PUT", f"/files/{name}", QUEUE_DIR / name, timeout=600)
        if r.get("bytes") == size:
            print(" ✓")
        else:
            print(f" ✗ {r}")
            failed += 1

    for name in on_device:
        if name.endswith(".pclm") and name[:10] < today:
            call(host, "DELETE", f"/files/{name}")
            print(f"· removed old {name}")

    call(host, "PUT", "/files/manifest.json", manifest_path)
    print()
    show_status(status(host))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="push",
                    choices=["push", "status", "test-print", "check-printer"])
    ap.add_argument("date", nargs="?", help="for test-print: YYYY-MM-DD")
    ap.add_argument("--pages", default="1-1", help='for test-print: e.g. "1-2", or "all" (default 1-1)')
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"ESP32 address (default {DEFAULT_HOST})")
    args = ap.parse_args()

    if args.command == "check-printer":
        return check_printer()
    if args.command == "status":
        show_status(status(args.host))
        return 0
    if args.command == "test-print":
        if not args.date:
            sys.exit("test-print needs a date, e.g. test-print 2026-11-10")
        status(args.host)  # exits with a clear message if the ESP32 isn't reachable
        print(f"⏳ Asking the ESP32 to print {args.date}, pages {args.pages} …")
        r = call(args.host, "POST", f"/print/{args.date}/{args.pages}", timeout=900)
        print(("✓ " if r.get("ok") else "✗ ") + r.get("result", str(r)))
        return 0 if r.get("ok") else 1
    return push(args.host)


if __name__ == "__main__":
    sys.exit(main())
