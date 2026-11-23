#!/usr/bin/env python3
"""
Build the next few workbooks ahead of time and turn each into a file the
HP ENVY Inspire 7900 can print directly (PCLm), ready for the ESP32 to print
one at a time, whenever you ask for the next one.

Workbooks are numbered, not dated: workbook 4 follows workbook 3 whether
that's tomorrow or next month. The HP doesn't accept PDF over IPP, so each PDF
is converted with Ghostscript (brew install ghostscript). Workbooks are
generated in order, one at a time, because each one's HSK / LeetCode /
reading / Italian progress builds on the one before.

Run it with the venv Python so MLX is available:
    ../.venv/bin/python print_batch.py                  # the next 7 workbooks
    ../.venv/bin/python print_batch.py --count 3        # the next 3
    ../.venv/bin/python print_batch.py --rebuild 5      # redo workbook 5 (same content)
    ../.venv/bin/python print_batch.py --convert-only   # just (re)convert the queued PDFs

Output: workbooks/print_queue/NNN.pclm plus manifest.json listing them.
"""

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import progression

HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "workbooks" / "dailyWorkbookLocal.py"
WORKBOOK_DIR = HERE / "workbooks"
QUEUE_DIR = WORKBOOK_DIR / "print_queue"

# What the HP reports it accepts (ipptool get-printer-attributes):
#   pclm-source-resolution-supported = 300dpi,600dpi; pclm-strip-height-preferred = 32
# 300dpi keeps a ~54-page workbook around 13 MB; 600dpi is roughly 4x that.
RESOLUTION = 300
STRIP_HEIGHT = 32


def pdf_for(n: int) -> Path:
    return WORKBOOK_DIR / f"workbook-{progression.label(n)}.pdf"


def pclm_for(n: int) -> Path:
    return QUEUE_DIR / f"{progression.label(n)}.pclm"


def queued_numbers() -> list[int]:
    return sorted(int(f.stem) for f in QUEUE_DIR.glob("*.pclm") if f.stem.isdigit())


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


def generate(n: int, rebuild: bool = False) -> bool:
    print(f"\n━━ Generating workbook {n} ━━", flush=True)
    cmd = [sys.executable, str(GENERATOR), "--no-open"] + (["--number", str(n)] if rebuild else [])
    r = subprocess.run(cmd, cwd=GENERATOR.parent)
    return r.returncode == 0 and pdf_for(n).exists()


def convert(n: int, gs: str) -> Path:
    src, dst = pdf_for(n), pclm_for(n)
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
    books = []
    for n in queued_numbers():
        f = pclm_for(n)
        books.append({"number": n, "file": f.name, "bytes": f.stat().st_size,
                      "pages": page_count(pdf_for(n), gs) if pdf_for(n).exists() else None})
    manifest = {"generated": datetime.now().isoformat(timespec="seconds"),
                "format": "application/PCLm", "media": "na_letter_8.5x11in",
                "workbooks": books}
    (QUEUE_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=7, help="how many new workbooks to build (default 7)")
    ap.add_argument("--rebuild", type=int, metavar="N",
                    help="rebuild workbook N with the same content instead of building new ones")
    ap.add_argument("--convert-only", action="store_true",
                    help="skip generation; (re)convert the PDFs of the workbooks in the queue")
    args = ap.parse_args()

    gs = find_gs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    if args.convert_only:
        todo = [(n, None) for n in queued_numbers()]
    elif args.rebuild:
        todo = [(args.rebuild, True)]
    else:
        first = progression.next_number()
        todo = [(n, False) for n in range(first, first + args.count)]

    failed: list[int] = []
    # Generation is sequential (progress files chain from one workbook to the
    # next); conversion is slow (~2–3 min each) but independent, so it runs alongside.
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {}
        for n, rebuild in todo:
            if rebuild is not None and not generate(n, rebuild):
                print(f"✗ workbook {n}: generation failed — stopping here so later "
                      f"workbooks don't build on a missing one")
                failed.append(n)
                break
            if not pdf_for(n).exists():
                print(f"· workbook {n}: no PDF, skipping")
                continue
            out = pclm_for(n)
            if out.exists() and out.stat().st_mtime >= pdf_for(n).stat().st_mtime:
                print(f"· workbook {n}: print file up to date")
                continue
            print(f"⏳ workbook {n}: converting to PCLm in the background", flush=True)
            jobs[n] = pool.submit(convert, n, gs)

        for n, job in jobs.items():
            try:
                f = job.result()
                print(f"✓ workbook {n}: {f.name} ({f.stat().st_size / 1e6:.1f} MB)")
            except subprocess.CalledProcessError as e:
                print(f"✗ workbook {n}: conversion failed\n{e.stderr.decode(errors='replace')[-800:]}")
                failed.append(n)

    write_manifest(gs)
    print(f"\nPrint queue: {QUEUE_DIR}")
    if failed:
        print("Failed: " + ", ".join(f"workbook {n}" for n in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
