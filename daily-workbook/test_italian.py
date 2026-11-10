#!/usr/bin/env python3
"""Quick checks for italian.py and italian_course.json.

    python3 test_italian.py            # data, day plan, progress, rendering
    python3 test_italian.py --rebuild  # also re-extract from the Quaderno (needs node) and compare
    python3 test_italian.py --pdf DIR  # also print days 1 and 3 with headless Chrome into DIR
                                       # and check every printed sheet has exactly one footer

Never touches the real italian_progress.json (uses a temporary file).
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import italian  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OPTIONS = {"rebuild": False, "pdf_dir": None}


def plain(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


class CourseData(unittest.TestCase):
    def setUp(self):
        self.course = italian.load_course()

    def test_counts_match_source(self):
        src, out = self.course["source_counts"], self.course["counts"]
        self.assertEqual((src["chapters"], src["sections"], src["exercises"], src["vocab_items"]),
                         (out["chapters"], out["sections"], out["exercises"], out["vocab_items"]))
        self.assertEqual((out["chapters"], out["sections"], out["exercises"]), (6, 42, 168))

    def test_sections_in_order_and_complete(self):
        ids = [s["id"] for c in self.course["chapters"] for s in c["sections"]]
        self.assertEqual(ids[0], "1.1")
        self.assertEqual(ids, sorted(ids, key=lambda x: tuple(map(int, x.split(".")))))
        for c in self.course["chapters"]:
            self.assertTrue(c["vocab"] and c["goals"])
            for s in c["sections"]:
                self.assertTrue(s["lesson"], s["id"])
                self.assertTrue(s["exercises"], s["id"])

    def test_exercises_have_answers(self):
        for c in self.course["chapters"]:
            for s in c["sections"]:
                for e in s["exercises"]:
                    t = e["type"]
                    if t == "choice":
                        for it in e["items"]:
                            self.assertIn(it["answer"], it["options"], e["id"])
                    elif t == "fill":
                        for it in e["items"]:
                            blanks = [p for p in it["parts"] if isinstance(p, dict)]
                            self.assertTrue(blanks and all(b["blank"] for b in blanks), e["id"])
                    elif t == "open":
                        self.assertTrue(e["prompts"] and e["example"], e["id"])
                    elif t == "conjugation":
                        self.assertTrue(all(len(v["forms"]) == 6 for v in e["verbs"]), e["id"])
                    elif t == "match":
                        self.assertEqual(sorted(e["right_order"]), list(range(len(e["pairs"]))), e["id"])
                    elif t == "clock":
                        self.assertTrue(all(x["answers"] for x in e["items"]), e["id"])

    def test_spot_checks_against_printed_days(self):
        ex = {e["id"]: e for c in self.course["chapters"] for s in c["sections"] for e in s["exercises"]}
        # 2.2 A La storia di Martina (printed Day 1): innamorata … triste
        self.assertEqual([i["answer"] for i in ex["2.2-1"]["items"]],
                         ["innamorata", "felice", "malata", "nervosa", "arrabbiata", "birichina", "annoiata", "triste"])
        # 2.7 C Date a raffica: fixed dates as on printed Day 2
        self.assertEqual(ex["2.7-3"]["items"][1]["parts"][0], "1/2 →")
        self.assertEqual(ex["2.7-3"]["items"][1]["parts"][1]["blank"][:2], ["il primo febbraio", "il 1° febbraio"])
        # 3.3 H dice: 12 rolls, cominciare -> cominciano
        self.assertEqual(ex["3.3-8"]["items"][9]["parts"][1]["blank"], ["cominciano"])
        # 3.5 C clock: 1:35 am style answers, first is a full phrase
        self.assertTrue(ex["3.5-3"]["items"][0]["answers"][0].startswith("sono le nove"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_rebuild_matches_file(self):
        if not OPTIONS["rebuild"]:
            self.skipTest("pass --rebuild")
        import extract_italian_course as ex
        fresh = ex.build(ex.DEFAULT_SOURCE)
        self.assertEqual(ex.check(fresh), [])
        self.assertEqual(json.loads(json.dumps(fresh, ensure_ascii=False)), self.course)


class DayPlan(unittest.TestCase):
    def test_plan(self):
        course = italian.load_course()
        plan = italian.plan_days(course)
        all_ids = [s["id"] for c in course["chapters"] for s in c["sections"]]
        self.assertEqual([i for p in plan for i in p["section_ids"]], all_ids)   # whole sections, in order
        self.assertEqual(plan[0]["section_ids"][0], "1.1")
        for p in plan:
            self.assertLessEqual(p["exercise_count"], italian.MAX_EXERCISES_PER_DAY)
            self.assertLessEqual(len(p["section_ids"]), italian.MAX_SECTIONS_PER_DAY)
        # The chapter 2-3 days split exactly like the printed Day 1-4 PDFs.
        self.assertIn(["2.1", "2.2", "2.3", "2.4"], [p["section_ids"] for p in plan])
        self.assertIn(["2.5", "2.6", "2.7", "2.8", "3.1"], [p["section_ids"] for p in plan])
        self.assertIn(["3.2", "3.3"], [p["section_ids"] for p in plan])
        # Short day 6 reaches into chapter 4 now that the Quaderno has chapters 4-6.
        self.assertIn(["3.4", "3.5", "3.6", "4.1"], [p["section_ids"] for p in plan])
        self.assertEqual(plan[-1]["section_ids"][-1], "6.6")
        # Every vocabulary group lands on exactly one day; every chapter gets a review.
        groups = sorted((c, g) for p in plan for c, g in p["vocab"])
        expect = sorted((c["number"], i) for c in course["chapters"] for i in range(len(c["vocab"])))
        self.assertEqual(groups, expect)
        self.assertEqual(sorted(c for p in plan for c in p["finishes_chapters"]), [c["number"] for c in course["chapters"]])


class Progress(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = italian.PROGRESS_FILE
        italian.PROGRESS_FILE = Path(self.tmp.name) / "italian_progress.json"
        self.real = HERE / "italian_progress.json"
        self.real_existed = self.real.exists()

    def tearDown(self):
        italian.PROGRESS_FILE = self.old
        self.tmp.cleanup()
        self.assertEqual(self.real.exists(), self.real_existed, "test touched the real progress file")

    def test_sequence(self):
        total = len(italian.plan_days())
        d0 = date(2026, 11, 9)
        self.assertEqual(italian.daily_set(d0, mark=False)["day"], 1)
        self.assertFalse(italian.PROGRESS_FILE.exists())               # mark=False saves nothing
        self.assertEqual(italian.daily_set(d0)["day"], 1)
        self.assertEqual(italian.daily_set(d0)["day"], 1)              # stable on rerun
        self.assertEqual(italian.daily_set(d0 + timedelta(days=1), mark=False)["day"], 2)
        for i in range(1, total):
            self.assertEqual(italian.daily_set(d0 + timedelta(days=i))["day"], i + 1)
        self.assertEqual(italian.daily_set(d0)["day"], 1)              # old dates keep their day
        done = italian.daily_set(d0 + timedelta(days=total))
        self.assertTrue(done["done"])
        r = italian.render(done)
        self.assertEqual(len(r["lesson_pages"]), 1)
        self.assertEqual(r["answer_pages"], [])
        saved = json.loads(italian.PROGRESS_FILE.read_text())
        self.assertEqual(sorted(saved["by_date"].values()), list(range(1, total + 1)))


class Rendering(unittest.TestCase):
    def test_every_day(self):
        course = italian.load_course()
        for p in italian.plan_days(course):
            ds = italian.day_set_for(p["day"], date(2026, 11, 12), course)
            r = italian.render(ds)
            self.assertIn("<style>", r["css"])
            self.assertTrue(r["lesson_pages"] and r["answer_pages"])
            for page in r["lesson_pages"] + r["answer_pages"]:
                self.assertTrue(page.startswith('<div class="page flow"><div class="frame">'))
                self.assertTrue(page.endswith("</div></div>"))
                self.assertEqual(page.count("<div"), page.count("</div>"))
                self.assertIn(italian.ATTRIBUTION, plain(page))
                self.assertNotIn("@weekday", page)
            lessons = "".join(r["lesson_pages"])
            answers = "".join(r["answer_pages"])
            first = plain(r["lesson_pages"][0])
            self.assertIn(f"sections {', '.join(ds['section_ids'])} · {ds['exercise_count']} exercises · about 60–90 minutes",
                          first)
            self.assertNotIn("Example answer", lessons)
            self.assertIn("Vocabolario", plain(lessons))
            self.assertIn("Before you stop", plain(lessons))
            # each exercise has a key entry; reasons ("why") and examples only in the answers
            for s in ds["sections"]:
                for i, e in enumerate(s["exercises"]):
                    self.assertIn(f"<b>{s['id']} {chr(65 + i)}</b>", answers)
                    for it in e.get("items", []):
                        if isinstance(it, dict) and it.get("why") and len(plain(it["why"])) > 12:
                            self.assertNotIn(plain(it["why"]), plain(lessons))
                    if e["type"] == "open":
                        self.assertNotIn(plain(html.escape(e["example"]))[:40], plain(lessons))

    def test_weekday_answer_follows_print_date(self):
        course = italian.load_course()
        n = next(p["day"] for p in italian.plan_days(course) if "2.6" in p["section_ids"])
        r = italian.render(italian.day_set_for(n, date(2026, 11, 12), course))   # a Thursday
        self.assertIn("giovedì, venerdì, sabato", plain("".join(r["answer_pages"])))

    def test_pdf(self):
        out = OPTIONS["pdf_dir"]
        if not out:
            self.skipTest("pass --pdf DIR")
        if not (Path(CHROME).exists() and shutil.which("pdftotext") and shutil.which("pdfinfo")):
            self.skipTest("needs Chrome and poppler")
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        pages = []
        for n, d in [(1, date(2026, 11, 9)), (3, date(2026, 11, 11))]:
            r = italian.render(italian.day_set_for(n, d))
            pages += r["lesson_pages"] + r["answer_pages"]
        src = out / "italian-sample.html"
        pdf = out / "italian-sample.pdf"
        src.write_text(italian.standalone_html(pages, r["css"], "Italiano sample"), encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", src.as_uri()], capture_output=True, timeout=120)
        n_sheets = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                                                                     text=True).stdout).group(1))
        self.assertEqual(n_sheets, len(pages), "a page ran onto a second sheet")
        for i in range(1, n_sheets + 1):
            t = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(pdf), "-"], capture_output=True,
                               text=True).stdout
            self.assertEqual(t.count("Adapted from"), 1, f"sheet {i}")
        print(f"\n  sample PDF: {pdf} ({n_sheets} sheets)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--rebuild" in args:
        OPTIONS["rebuild"] = True
        args.remove("--rebuild")
    if "--pdf" in args:
        i = args.index("--pdf")
        OPTIONS["pdf_dir"] = args[i + 1]
        del args[i:i + 2]
    unittest.main(argv=[sys.argv[0]] + args, verbosity=2)
