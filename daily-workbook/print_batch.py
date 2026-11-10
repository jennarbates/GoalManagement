#!/usr/bin/env python3
"""
Build several days of workbooks ahead of time and turn each into a file the
HP ENVY Inspire 7900 can print directly (PCLm), ready for the ESP32 to send
on the morning it's for.

The HP doesn't accept PDF over IPP, so each PDF is converted with Ghostscript
(brew install ghostscript). Days are generated in order, one at a time,
because each day's HSK / LeetCode / reading / Italian progress builds on the
day before.

Run it with the venv Python so MLX is available:
    ../.venv/bin/python print_batch.py                  # the next 7 days, starting tomorrow
    ../.venv/bin/python print_batch.py --start 2026-11-10 --days 3
    ../.venv/bin/python print_batch.py --convert-only   # just (re)convert existing PDFs

Output: workbooks/print_queue/YYYY-MM-DD.pclm plus manifest.json listing them.
A day whose PDF already exists is not regenerated (that would advance the
progress files twice) unless you pass --force.
"""

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "workbooks" / "dailyWorkbookLocal.py"
WORKBOOK_DIR = HERE / "workbooks"
QUEUE_DIR = WORKBOOK_DIR / "print_queue"

# What the HP reports it accepts (ipptool get-printer-attributes):
#   pclm-source-resolution-supported = 300dpi,600dpi; pclm-strip-height-preferred = 32
# 300dpi keeps a ~54-page day around 13 MB; 600dpi is roughly 4x that.
RESOLUTION = 300
STRIP_HEIGHT = 32


def pdf_for(day: date) -> Path:
    return WORKBOOK_DIR / f"daily-workbook-{day.isoformat()}.pdf"


def pclm_for(day: date) -> Path:
    return QUEUE_DIR / f"{day.isoformat()}.pclm"


def find_gs() -> str:
    # launchd jobs don't get Homebrew on PATH, so check its usual spots too
    for c in (shutil.which("gs"), "/opt/homebrew/bin/gs", "/usr/local/bin/gs"):
        if c and Path(c).exists():
            return c
    sys.exit("✗ Ghostscript not found. Install it with: brew install ghostscript")


def page_count(pdf: Path, gs: str) -> int | None:
    r = subprocess.run(
        [gs, "-q", "-dNODISPLAY", "-dNOSAFER", "-c",
         f"({pdf}) (r) file runpdfbegin pdfpagecount = quit"],
        capture_output=True, text=True)
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def generate(day: date) -> bool:
    print(f"\n━━ Generating {day:%a %Y-%m-%d} ━━", flush=True)
    r = subprocess.run([sys.executable, str(GENERATOR), "--date", day.isoformat(), "--no-open"],
                       cwd=GENERATOR.parent)
    return r.returncode == 0 and pdf_for(day).exists()


def convert(day: date, gs: str) -> Path:
    src, dst = pdf_for(day), pclm_for(day)
    tmp = dst.with_suffix(".pclm.part")
    subprocess.run(
        [gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
         "-sDEVICE=pclm", f"-r{RESOLUTION}", f"-dStripHeight={STRIP_HEIGHT}",
         "-sPAPERSIZE=letter", "-dFIXEDMEDIA", "-dPDFFitPage",
         "-o", str(tmp), str(src)],
        check=True, capture_output=True)
    tmp.replace(dst)  # only a finished file ever has the .pclm name
    return dst


def write_manifest(gs: str) -> None:
    today = date.today()
    days = []
    for f in sorted(QUEUE_DIR.glob("*.pclm")):
        d = datetime.strptime(f.stem, "%Y-%m-%d").date()
        if d < today:
            f.unlink()  # already printed (or missed); the PDF is still in workbooks/
            continue
        days.append({"date": f.stem, "file": f.name, "bytes": f.stat().st_size,
                     "pages": page_count(pdf_for(d), gs) if pdf_for(d).exists() else None})
    manifest = {"generated": datetime.now().isoformat(timespec="seconds"),
                "format": "application/PCLm", "media": "na_letter_8.5x11in",
                "days": days}
    (QUEUE_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", help="first day, YYYY-MM-DD (default: tomorrow)")
    ap.add_argument("--days", type=int, default=7, help="how many days to build (default 7)")
    ap.add_argument("--force", action="store_true",
                    help="regenerate days whose PDF already exists (advances progress again)")
    ap.add_argument("--convert-only", action="store_true",
                    help="skip generation; convert whatever PDFs already exist")
    args = ap.parse_args()

    start = (datetime.strptime(args.start, "%Y-%m-%d").date() if args.start
             else date.today() + timedelta(days=1))
    days = [start + timedelta(days=i) for i in range(args.days)]
    gs = find_gs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    failed: list[date] = []
    # Generation is sequential (progress files chain day to day); conversion is
    # slow (~2–3 min a day) but independent, so it runs alongside.
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {}
        for d in days:
            have_pdf = pdf_for(d).exists()
            if not args.convert_only and (args.force or not have_pdf):
                if not generate(d):
                    print(f"✗ {d}: generation failed — stopping here so later days "
                          f"don't build on a missing day")
                    failed.append(d)
                    break
            elif not have_pdf:
                print(f"· {d}: no PDF, skipping")
                continue
            else:
                print(f"· {d}: PDF already exists, not regenerating")

            out = pclm_for(d)
            if out.exists() and out.stat().st_mtime >= pdf_for(d).stat().st_mtime:
                print(f"· {d}: print file up to date")
                continue
            print(f"⏳ {d}: converting to PCLm in the background", flush=True)
            jobs[d] = pool.submit(convert, d, gs)

        for d, job in jobs.items():
            try:
                f = job.result()
                print(f"✓ {d}: {f.name} ({f.stat().st_size / 1e6:.1f} MB)")
            except subprocess.CalledProcessError as e:
                print(f"✗ {d}: conversion failed\n{e.stderr.decode(errors='replace')[-800:]}")
                failed.append(d)

    write_manifest(gs)
    print(f"\nPrint queue: {QUEUE_DIR}")
    if failed:
        print("Failed: " + ", ".join(str(d) for d in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
