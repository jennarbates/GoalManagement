#!/usr/bin/env python3
"""Generate workbook_tasks.json: CS311 practice and HSK 1 study tasks.

Run this to (re)generate upcoming study tasks for the receipt printer, then
use taskprinter.py to print them:

  python generate_workbook_tasks.py
  python vibeCode/taskprinter.py print-window \\
      --file workbook_tasks.json --printer <your-printer> --days 1

CS311 topics come from cs311.py, the same source the workbook uses.
"""
from __future__ import annotations

import argparse
import json
import os
import unicodedata
from datetime import date, timedelta

import cs311  # daily-workbook/cs311.py


CERT_START = date(2026, 5, 12)


HSK1_VOCAB = [
    {"char": "你",   "pinyin": "ni3",      "meaning": "you"},
    {"char": "好",   "pinyin": "hao3",     "meaning": "good"},
    {"char": "你好", "pinyin": "ni3 hao3", "meaning": "hello"},
    {"char": "我",   "pinyin": "wo3",      "meaning": "I, me"},
    {"char": "是",   "pinyin": "shi4",     "meaning": "to be"},
    {"char": "不",   "pinyin": "bu4",      "meaning": "not, no"},
    {"char": "吗",   "pinyin": "ma",       "meaning": "question particle"},
    {"char": "呢",   "pinyin": "ne",       "meaning": "question particle"},
    {"char": "很",   "pinyin": "hen3",     "meaning": "very"},
    {"char": "也",   "pinyin": "ye3",      "meaning": "also"},
    {"char": "都",   "pinyin": "dou1",     "meaning": "all, both"},
    {"char": "在",   "pinyin": "zai4",     "meaning": "at, in, on"},
    {"char": "有",   "pinyin": "you3",     "meaning": "to have"},
    {"char": "这",   "pinyin": "zhe4",     "meaning": "this"},
    {"char": "那",   "pinyin": "na4",      "meaning": "that"},
    {"char": "哪",   "pinyin": "na3",      "meaning": "which, where"},
    {"char": "个",   "pinyin": "ge4",      "meaning": "general measure word"},
    {"char": "人",   "pinyin": "ren2",     "meaning": "person"},
    {"char": "他",   "pinyin": "ta1",      "meaning": "he, him"},
    {"char": "她",   "pinyin": "ta1",      "meaning": "she, her"},
    {"char": "们",   "pinyin": "men",      "meaning": "plural marker"},
    {"char": "叫",   "pinyin": "jiao4",    "meaning": "to be called"},
    {"char": "什么", "pinyin": "shen2 me", "meaning": "what"},
    {"char": "名字", "pinyin": "ming2 zi", "meaning": "name"},
    {"char": "学生", "pinyin": "xue2 sheng", "meaning": "student"},
    {"char": "老师", "pinyin": "lao3 shi1",  "meaning": "teacher"},
    {"char": "学校", "pinyin": "xue2 xiao4", "meaning": "school"},
    {"char": "中国", "pinyin": "zhong1 guo2", "meaning": "China"},
    {"char": "北京", "pinyin": "bei3 jing1",  "meaning": "Beijing"},
    {"char": "家",   "pinyin": "jia1",     "meaning": "home, family"},
    {"char": "爸爸", "pinyin": "ba4 ba",   "meaning": "dad"},
    {"char": "妈妈", "pinyin": "ma1 ma",   "meaning": "mom"},
    {"char": "儿子", "pinyin": "er2 zi",   "meaning": "son"},
    {"char": "女儿", "pinyin": "nu3 er2",  "meaning": "daughter"},
    {"char": "朋友", "pinyin": "peng2 you", "meaning": "friend"},
    {"char": "医生", "pinyin": "yi1 sheng1", "meaning": "doctor"},
    {"char": "工作", "pinyin": "gong1 zuo4", "meaning": "work, job"},
    {"char": "吃",   "pinyin": "chi1",     "meaning": "to eat"},
    {"char": "喝",   "pinyin": "he1",      "meaning": "to drink"},
    {"char": "看",   "pinyin": "kan4",     "meaning": "to look, watch"},
    {"char": "听",   "pinyin": "ting1",    "meaning": "to listen"},
    {"char": "说",   "pinyin": "shuo1",    "meaning": "to speak, say"},
    {"char": "读",   "pinyin": "du2",      "meaning": "to read"},
    {"char": "写",   "pinyin": "xie3",     "meaning": "to write"},
    {"char": "学",   "pinyin": "xue2",     "meaning": "to study, learn"},
    {"char": "会",   "pinyin": "hui4",     "meaning": "can, know how to"},
    {"char": "喜欢", "pinyin": "xi3 huan", "meaning": "to like"},
    {"char": "爱",   "pinyin": "ai4",      "meaning": "to love"},
    {"char": "想",   "pinyin": "xiang3",   "meaning": "to think, want"},
    {"char": "去",   "pinyin": "qu4",      "meaning": "to go"},
    {"char": "来",   "pinyin": "lai2",     "meaning": "to come"},
    {"char": "回",   "pinyin": "hui2",     "meaning": "to return"},
    {"char": "买",   "pinyin": "mai3",     "meaning": "to buy"},
    {"char": "开",   "pinyin": "kai1",     "meaning": "to open, drive"},
    {"char": "坐",   "pinyin": "zuo4",     "meaning": "to sit"},
    {"char": "住",   "pinyin": "zhu4",     "meaning": "to live, reside"},
    {"char": "睡觉", "pinyin": "shui4 jiao4", "meaning": "to sleep"},
    {"char": "认识", "pinyin": "ren4 shi",    "meaning": "to know, recognize"},
    {"char": "谢谢", "pinyin": "xie4 xie",    "meaning": "thank you"},
    {"char": "不客气", "pinyin": "bu2 ke4 qi", "meaning": "you're welcome"},
    {"char": "对不起", "pinyin": "dui4 bu qi3", "meaning": "sorry"},
    {"char": "没关系", "pinyin": "mei2 guan1 xi", "meaning": "no problem"},
    {"char": "再见", "pinyin": "zai4 jian4", "meaning": "goodbye"},
    {"char": "请",   "pinyin": "qing3",    "meaning": "please"},
    {"char": "一",   "pinyin": "yi1",      "meaning": "one"},
    {"char": "二",   "pinyin": "er4",      "meaning": "two"},
    {"char": "三",   "pinyin": "san1",     "meaning": "three"},
    {"char": "四",   "pinyin": "si4",      "meaning": "four"},
    {"char": "五",   "pinyin": "wu3",      "meaning": "five"},
    {"char": "六",   "pinyin": "liu4",     "meaning": "six"},
    {"char": "七",   "pinyin": "qi1",      "meaning": "seven"},
    {"char": "八",   "pinyin": "ba1",      "meaning": "eight"},
    {"char": "九",   "pinyin": "jiu3",     "meaning": "nine"},
    {"char": "十",   "pinyin": "shi2",     "meaning": "ten"},
    {"char": "几",   "pinyin": "ji3",      "meaning": "how many"},
    {"char": "多少", "pinyin": "duo1 shao", "meaning": "how many/much"},
    {"char": "岁",   "pinyin": "sui4",     "meaning": "years old"},
    {"char": "今天", "pinyin": "jin1 tian1", "meaning": "today"},
    {"char": "明天", "pinyin": "ming2 tian1", "meaning": "tomorrow"},
    {"char": "昨天", "pinyin": "zuo2 tian1", "meaning": "yesterday"},
    {"char": "现在", "pinyin": "xian4 zai4", "meaning": "now"},
    {"char": "点",   "pinyin": "dian3",    "meaning": "o'clock"},
    {"char": "时候", "pinyin": "shi2 hou", "meaning": "time, moment"},
    {"char": "上午", "pinyin": "shang4 wu3", "meaning": "morning"},
    {"char": "下午", "pinyin": "xia4 wu3",  "meaning": "afternoon"},
    {"char": "晚上", "pinyin": "wan3 shang", "meaning": "evening"},
    {"char": "月",   "pinyin": "yue4",     "meaning": "month, moon"},
    {"char": "日",   "pinyin": "ri4",      "meaning": "day, date"},
    {"char": "年",   "pinyin": "nian2",    "meaning": "year"},
    {"char": "星期", "pinyin": "xing1 qi1", "meaning": "week"},
    {"char": "星期一", "pinyin": "xing1 qi1 yi1", "meaning": "Monday"},
    {"char": "星期二", "pinyin": "xing1 qi1 er4", "meaning": "Tuesday"},
    {"char": "星期三", "pinyin": "xing1 qi1 san1", "meaning": "Wednesday"},
    {"char": "星期四", "pinyin": "xing1 qi1 si4", "meaning": "Thursday"},
    {"char": "星期五", "pinyin": "xing1 qi1 wu3", "meaning": "Friday"},
    {"char": "星期六", "pinyin": "xing1 qi1 liu4", "meaning": "Saturday"},
    {"char": "星期天", "pinyin": "xing1 qi1 tian1", "meaning": "Sunday"},
]

HSK_WORD_INDEX = {w["char"]: w for w in HSK1_VOCAB}

# ── HSK progress ──────────────────────────────────────────────────────────────

HSK_PROGRESS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsk1_progress.json")
LESSONS_PER_DAY = 4



def load_hsk_progress() -> dict:
    try:
        with open(HSK_PROGRESS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "days": [], "introduced_chars": []}


def practice_char_for_day(target_date: date, progress: dict) -> str | None:
    """Return the practice char label (ascii-safe) for a given date."""
    date_str = target_date.isoformat()

    # Check if this date already has a recorded entry
    for day in progress.get("days", []):
        if day.get("date") == date_str:
            char = day.get("char_practice_char")
            if char and char in HSK_WORD_INDEX:
                w = HSK_WORD_INDEX[char]
                return f"{w['pinyin']} - {w['meaning']}"
            return None

    # Simulate forward from introduced_chars
    introduced = set(progress.get("introduced_chars", []))
    vocab_queue = [w for w in HSK1_VOCAB if w["char"] not in introduced]

    # Number of days since the last recorded day in progress
    recorded_dates = sorted(d["date"] for d in progress.get("days", []))
    if recorded_dates:
        last_date = date.fromisoformat(recorded_dates[-1])
    else:
        last_date = CERT_START - timedelta(days=1)

    sim_date = last_date + timedelta(days=1)
    while sim_date <= target_date:
        if not vocab_queue:
            return None
        lesson = vocab_queue[:LESSONS_PER_DAY]
        practice = lesson[0]
        vocab_queue = vocab_queue[LESSONS_PER_DAY:]
        if sim_date == target_date:
            return f"{practice['pinyin']} - {practice['meaning']}"
        sim_date += timedelta(days=1)

    return None


# ── Item generation ───────────────────────────────────────────────────────────

def cert_day_for(d: date) -> int:
    return max(1, (d - CERT_START).days + 1)


def items_for_date(d: date, hsk_progress: dict) -> list[dict]:
    cday = cert_day_for(d)
    date_str = d.isoformat()

    algo = cs311.daily_set(d)

    hsk_label = practice_char_for_day(d, hsk_progress)

    items = [] if not algo["course_order"] else [
        {
            "id": f"cs311-{date_str}",
            "type": "assignment",
            "course": "CS311",
            "title": (", ".join(f"{q['topic']} Q{q['question_number']}" for q in algo["course_order"])
                      + f" + random: {algo['random']['topic']} Q{algo['random']['question_number']}"
                      + (f" + {len(algo['review'])} review" if algo.get("review") else "")),
            "due": date_str,
            "all_day": True,
        },
    ]

    if hsk_label:
        items.append({
            "id": f"hsk-{date_str}",
            "type": "assignment",
            "course": "HSK 1",
            "title": f"Practice: {hsk_label}",
            "due": date_str,
            "all_day": True,
        })

    return items


# ── Main ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRINTER_CONFIG = os.path.join(SCRIPT_DIR, ".printer")


def load_saved_printer() -> str | None:
    try:
        return open(PRINTER_CONFIG).read().strip() or None
    except FileNotFoundError:
        return None


def save_printer(name: str) -> None:
    with open(PRINTER_CONFIG, "w") as f:
        f.write(name)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate workbook tasks and print today's receipts in one step."
    )
    ap.add_argument("--printer", default=None,
                    help="CUPS printer queue name. Saved after first use.")
    ap.add_argument("--days", type=int, default=7,
                    help="Days of tasks to generate (default 7).")
    ap.add_argument("--output", default=None,
                    help="Output JSON path (default: workbook_tasks.json next to this script).")
    ap.add_argument("--timezone", default="America/New_York",
                    help="Timezone (default America/New_York).")
    ap.add_argument("--preview", action="store_true",
                    help="Show what would print without sending to printer.")
    ap.add_argument("--no-print", action="store_true",
                    help="Generate the JSON only, skip printing.")
    args = ap.parse_args()

    out_path = args.output or os.path.join(SCRIPT_DIR, "workbook_tasks.json")

    # ── Generate ──
    progress = load_hsk_progress()
    today = date.today()

    all_items: list[dict] = []
    for offset in range(args.days):
        d = today + timedelta(days=offset)
        all_items.extend(items_for_date(d, progress))

    if args.preview:
        for it in all_items:
            print(f"{it['due']}  [{it['course']}]  {it['title']}")
        return 0

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"timezone": args.timezone, "items": all_items}, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(all_items)} items ({today} – {today + timedelta(days=args.days - 1)})")

    if args.no_print:
        return 0

    # ── Print ──
    printer = args.printer or load_saved_printer()
    if not printer:
        print("\nNo printer configured. Run with --printer <name> once to save it.")
        print("Find your printer name with:  lpstat -p")
        return 1

    if args.printer:
        save_printer(args.printer)

    import subprocess
    taskprinter = os.path.join(SCRIPT_DIR, "taskprinter.py")
    cmd = [
        "python3", taskprinter,
        "print-window",
        "--file", out_path,
        "--printer", printer,
        "--days", "1",
    ]
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
