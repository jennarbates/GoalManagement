#!/usr/bin/env python3
"""
Daily Workbook Generator — Whimsical Edition
Base: stable local MLX + email version.
Added: day-type awareness, dog care, morning routine, exercise, stretch/yoga,
       dinner suggestions, life admin, parking lot, full chore schedule,
       CS311 algorithms practice + HSK 1 + offline plan.

Day types:
  Mon/Wed/Fri = Work days  → lighter study blocks
  Tue         = Free day   → deep study session
  Thu         = Therapy    → light day, minimal tasks
  Sat/Sun     = Weekend    → medium study, your pace

Setup:
    python3 -m venv .venv
    source .venv/bin/activate
    pip install mlx-lm huggingface_hub

Optional:
    export HF_TOKEN="hf_your_token"

Required for email:
    export GMAIL_APP_PASSWORD="your_16_char_gmail_app_password"

Run:
    python3 dailyWorkbookLocal.py
"""

import html as py_html
import sys
import urllib.request
import urllib.error
import json
import math
import os
import random
import shutil
import smtplib
import subprocess
import traceback
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

# offline_plan.py lives one folder up, in daily-workbook/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import offline_plan
except ImportError:
    offline_plan = None
try:
    import cs311
except ImportError:
    cs311 = None
try:
    import reading
except ImportError:
    reading = None
try:
    import leetcode
except ImportError:
    leetcode = None
try:
    import hanzi
except ImportError:
    hanzi = None
try:
    import cs311_visuals
except ImportError:
    cs311_visuals = None
try:
    import italian
except ImportError:
    italian = None


# ── Config ────────────────────────────────────────────────────────────────────

LOCAL_MODEL_ID   = "mlx-community/LFM2-8B-A1B-8bit-MLX"
TRUST_REMOTE_CODE = False

SENDER_EMAIL    = os.environ.get("WORKBOOK_SENDER_EMAIL", "")
RECIPIENT_EMAIL = os.environ.get("WORKBOOK_RECIPIENT_EMAIL", SENDER_EMAIL)
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

# Data (progress files, lists) lives in daily-workbook/; generated workbooks go
# next to this script in daily-workbook/workbooks/ (HTML/PDF are gitignored).
DATA_DIR        = Path(__file__).resolve().parent.parent
OUTPUT_DIR      = Path(__file__).resolve().parent
PROGRESS_FILE   = DATA_DIR / "hsk1_progress.json"
PARKING_LOT_FILE = Path(__file__).resolve().parent.parent / "parking_lot.txt"  # daily-workbook/parking_lot.txt

MAX_TOKENS      = 1800
MAX_JSON_RETRIES = 1

NEW_WORDS_PER_DAY    = 4
REVIEW_WORDS_PER_DAY = 6
LESSON_WORDS_PER_DAY = 6

_MODEL     = None
_TOKENIZER = None

# ── Schedule constants ────────────────────────────────────────────────────────

WORK_DAYS    = {0, 2, 4}   # Mon, Wed, Fri — lighter study blocks
THERAPY_DAY  = 3            # Thu — minimal tasks
WEEKEND_DAYS = {5, 6}       # Sat, Sun — medium study
# Tuesday (1) = free day — deep study session

# Weekly chore assignments — same big task each day, predictable
CHORE_SCHEDULE = {
    0: ("Bathroom 1 deep clean",       "Toilet, sink, mirror, floor — the works.",                           "~25 min"),
    1: ("Laundry",                      "Wash + dry a full load. Put it away — don't leave it in the machine.", "~15 min active"),
    2: ("Floors",                       "Vacuum all rooms, mop/sweep hard floors. Dog hair edition.",          "~30 min"),
    3: ("Dishes + quick kitchen wipe",  "Therapy day — just the basics, keep it easy.",                       "~10 min"),
    4: ("Trash + recycling out",        "Quick clutter sweep of one room too.",                               "~15 min"),
    5: ("Bathroom 2 + clutter purge",   "Second bathroom deep clean + 15 min clutter sort.",                  "~40 min"),
    6: ("Kitchen deep reset",           "Stovetop, microwave, surfaces clear. Set the week up right.",        "~30 min"),
}

# ─────────────────────────────────────────────────────────────────────────────


def day_type(weekday: int) -> str:
    if weekday in WORK_DAYS:    return "work"
    if weekday == THERAPY_DAY:  return "therapy"
    if weekday in WEEKEND_DAYS: return "weekend"
    return "free"  # Tuesday


def esc(text) -> str:
    return py_html.escape("" if text is None else str(text))

# The day this workbook is for. None = today. Set by --date so a batch can
# build future days ahead of time; everything date-dependent reads wb_now().
WORKBOOK_DATE = None

def wb_now() -> datetime:
    if WORKBOOK_DATE is None:
        return datetime.now()
    return datetime.combine(WORKBOOK_DATE, datetime.now().time())

def today_stamp() -> str:
    return wb_now().strftime("%Y-%m-%d")

def today_label() -> str:
    return wb_now().strftime("%A, %B %d, %Y")

def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_local_model():
    global _MODEL, _TOKENIZER
    if _MODEL is None or _TOKENIZER is None:
        from mlx_lm import load
        load_kwargs = {}
        if TRUST_REMOTE_CODE:
            load_kwargs["tokenizer_config"] = {"trust_remote_code": True}
        _MODEL, _TOKENIZER = load(LOCAL_MODEL_ID, **load_kwargs)
    return _MODEL, _TOKENIZER


# ── HSK 1 vocabulary ──────────────────────────────────────────────────────────

HSK1_VOCAB = [
    {"char": "你", "pinyin": "nǐ", "meaning": "you"},
    {"char": "好", "pinyin": "hǎo", "meaning": "good; well"},
    {"char": "你好", "pinyin": "nǐ hǎo", "meaning": "hello"},
    {"char": "我", "pinyin": "wǒ", "meaning": "I; me"},
    {"char": "是", "pinyin": "shì", "meaning": "to be"},
    {"char": "不", "pinyin": "bù", "meaning": "not; no"},
    {"char": "吗", "pinyin": "ma", "meaning": "question particle"},
    {"char": "呢", "pinyin": "ne", "meaning": "question particle"},
    {"char": "很", "pinyin": "hěn", "meaning": "very"},
    {"char": "也", "pinyin": "yě", "meaning": "also"},
    {"char": "都", "pinyin": "dōu", "meaning": "all; both"},
    {"char": "在", "pinyin": "zài", "meaning": "at; in; on"},
    {"char": "有", "pinyin": "yǒu", "meaning": "to have"},
    {"char": "这", "pinyin": "zhè", "meaning": "this"},
    {"char": "那", "pinyin": "nà", "meaning": "that"},
    {"char": "哪", "pinyin": "nǎ", "meaning": "which; where"},
    {"char": "个", "pinyin": "gè", "meaning": "general measure word"},
    {"char": "人", "pinyin": "rén", "meaning": "person"},
    {"char": "他", "pinyin": "tā", "meaning": "he; him"},
    {"char": "她", "pinyin": "tā", "meaning": "she; her"},
    {"char": "们", "pinyin": "men", "meaning": "plural marker"},
    {"char": "叫", "pinyin": "jiào", "meaning": "to be called; to call"},
    {"char": "什么", "pinyin": "shén me", "meaning": "what"},
    {"char": "名字", "pinyin": "míng zi", "meaning": "name"},
    {"char": "学生", "pinyin": "xué sheng", "meaning": "student"},
    {"char": "老师", "pinyin": "lǎo shī", "meaning": "teacher"},
    {"char": "学校", "pinyin": "xué xiào", "meaning": "school"},
    {"char": "中国", "pinyin": "Zhōng guó", "meaning": "China"},
    {"char": "北京", "pinyin": "Běi jīng", "meaning": "Beijing"},
    {"char": "家", "pinyin": "jiā", "meaning": "home; family"},
    {"char": "爸爸", "pinyin": "bà ba", "meaning": "dad"},
    {"char": "妈妈", "pinyin": "mā ma", "meaning": "mom"},
    {"char": "儿子", "pinyin": "ér zi", "meaning": "son"},
    {"char": "女儿", "pinyin": "nǚ ér", "meaning": "daughter"},
    {"char": "朋友", "pinyin": "péng you", "meaning": "friend"},
    {"char": "医生", "pinyin": "yī shēng", "meaning": "doctor"},
    {"char": "工作", "pinyin": "gōng zuò", "meaning": "work; job"},
    {"char": "吃", "pinyin": "chī", "meaning": "to eat"},
    {"char": "喝", "pinyin": "hē", "meaning": "to drink"},
    {"char": "看", "pinyin": "kàn", "meaning": "to look; to watch"},
    {"char": "听", "pinyin": "tīng", "meaning": "to listen"},
    {"char": "说", "pinyin": "shuō", "meaning": "to speak; to say"},
    {"char": "读", "pinyin": "dú", "meaning": "to read"},
    {"char": "写", "pinyin": "xiě", "meaning": "to write"},
    {"char": "学", "pinyin": "xué", "meaning": "to study; to learn"},
    {"char": "会", "pinyin": "huì", "meaning": "can; know how to"},
    {"char": "喜欢", "pinyin": "xǐ huan", "meaning": "to like"},
    {"char": "爱", "pinyin": "ài", "meaning": "to love"},
    {"char": "想", "pinyin": "xiǎng", "meaning": "to think; to want"},
    {"char": "去", "pinyin": "qù", "meaning": "to go"},
    {"char": "来", "pinyin": "lái", "meaning": "to come"},
    {"char": "回", "pinyin": "huí", "meaning": "to return"},
    {"char": "买", "pinyin": "mǎi", "meaning": "to buy"},
    {"char": "开", "pinyin": "kāi", "meaning": "to open; to drive"},
    {"char": "坐", "pinyin": "zuò", "meaning": "to sit"},
    {"char": "住", "pinyin": "zhù", "meaning": "to live; reside"},
    {"char": "睡觉", "pinyin": "shuì jiào", "meaning": "to sleep"},
    {"char": "认识", "pinyin": "rèn shi", "meaning": "to know; recognize"},
    {"char": "谢谢", "pinyin": "xiè xie", "meaning": "thank you"},
    {"char": "不客气", "pinyin": "bú kè qi", "meaning": "you're welcome"},
    {"char": "对不起", "pinyin": "duì bu qǐ", "meaning": "sorry"},
    {"char": "没关系", "pinyin": "méi guān xi", "meaning": "it's okay; no problem"},
    {"char": "再见", "pinyin": "zài jiàn", "meaning": "goodbye"},
    {"char": "请", "pinyin": "qǐng", "meaning": "please"},
    {"char": "一", "pinyin": "yī", "meaning": "one"},
    {"char": "二", "pinyin": "èr", "meaning": "two"},
    {"char": "三", "pinyin": "sān", "meaning": "three"},
    {"char": "四", "pinyin": "sì", "meaning": "four"},
    {"char": "五", "pinyin": "wǔ", "meaning": "five"},
    {"char": "六", "pinyin": "liù", "meaning": "six"},
    {"char": "七", "pinyin": "qī", "meaning": "seven"},
    {"char": "八", "pinyin": "bā", "meaning": "eight"},
    {"char": "九", "pinyin": "jiǔ", "meaning": "nine"},
    {"char": "十", "pinyin": "shí", "meaning": "ten"},
    {"char": "几", "pinyin": "jǐ", "meaning": "how many"},
    {"char": "多少", "pinyin": "duō shao", "meaning": "how many; how much"},
    {"char": "岁", "pinyin": "suì", "meaning": "years old"},
    {"char": "今天", "pinyin": "jīn tiān", "meaning": "today"},
    {"char": "明天", "pinyin": "míng tiān", "meaning": "tomorrow"},
    {"char": "昨天", "pinyin": "zuó tiān", "meaning": "yesterday"},
    {"char": "现在", "pinyin": "xiàn zài", "meaning": "now"},
    {"char": "点", "pinyin": "diǎn", "meaning": "o'clock"},
    {"char": "时候", "pinyin": "shí hou", "meaning": "time; moment"},
    {"char": "上午", "pinyin": "shàng wǔ", "meaning": "morning"},
    {"char": "下午", "pinyin": "xià wǔ", "meaning": "afternoon"},
    {"char": "晚上", "pinyin": "wǎn shang", "meaning": "evening"},
    {"char": "月", "pinyin": "yuè", "meaning": "month; moon"},
    {"char": "日", "pinyin": "rì", "meaning": "day; date"},
    {"char": "年", "pinyin": "nián", "meaning": "year"},
    {"char": "星期", "pinyin": "xīng qī", "meaning": "week"},
    {"char": "星期一", "pinyin": "xīng qī yī", "meaning": "Monday"},
    {"char": "星期二", "pinyin": "xīng qī èr", "meaning": "Tuesday"},
    {"char": "星期三", "pinyin": "xīng qī sān", "meaning": "Wednesday"},
    {"char": "星期四", "pinyin": "xīng qī sì", "meaning": "Thursday"},
    {"char": "星期五", "pinyin": "xīng qī wǔ", "meaning": "Friday"},
    {"char": "星期六", "pinyin": "xīng qī liù", "meaning": "Saturday"},
    {"char": "星期天", "pinyin": "xīng qī tiān", "meaning": "Sunday"},
]

WORD_INDEX = {item["char"]: item for item in HSK1_VOCAB}


# ── HSK progress tracking (unchanged from original) ───────────────────────────

def load_hsk_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"version": 1, "days": [], "introduced_chars": []}
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "days": [], "introduced_chars": []}

def save_hsk_progress(progress: dict) -> None:
    ensure_output_dir()
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

def dedupe_words(words):
    seen, out = set(), []
    for w in words:
        if not isinstance(w, dict): continue
        ch = w.get("char")
        if not ch or ch in seen: continue
        seen.add(ch); out.append(w)
    return out

def vocab_by_char(char: str):
    return WORD_INDEX.get(char)

def words_from_chars(chars):
    return dedupe_words([item for ch in chars if (item := vocab_by_char(ch))])

def get_existing_day_pack(progress: dict, date_str: str):
    for day in progress.get("days", []):
        if day.get("date") == date_str:
            return {
                "new_words":       words_from_chars(day.get("new_chars", [])),
                "review_words":    words_from_chars(day.get("review_chars", [])),
                "lesson_words":    words_from_chars(day.get("lesson_chars", [])),
                "char_practice":   vocab_by_char(day.get("char_practice_char", "")) or HSK1_VOCAB[0],
                "all_learned_words": words_from_chars(day.get("all_learned_chars", [])),
            }
    return None

def choose_hsk_words_for_today(progress: dict, date_str: str):
    existing = get_existing_day_pack(progress, date_str)
    if existing: return existing

    introduced_chars = progress.get("introduced_chars", [])
    introduced_set   = set(introduced_chars)
    unseen = [w for w in HSK1_VOCAB if w["char"] not in introduced_set]
    seen   = words_from_chars(introduced_chars)

    new_words    = unseen[:NEW_WORDS_PER_DAY]
    review_words = list(reversed(seen[-REVIEW_WORDS_PER_DAY:]))
    lesson_words = dedupe_words(new_words + review_words[:max(0, LESSON_WORDS_PER_DAY - len(new_words))])

    if len(lesson_words) < LESSON_WORDS_PER_DAY:
        for item in dedupe_words(seen + unseen):
            if item["char"] not in {x["char"] for x in lesson_words}:
                lesson_words.append(item)
            if len(lesson_words) >= LESSON_WORDS_PER_DAY: break

    all_learned_words = dedupe_words(seen + new_words)
    char_practice     = new_words[0] if new_words else lesson_words[0]

    return {
        "new_words": new_words,
        "review_words": review_words[:4],
        "lesson_words": lesson_words[:LESSON_WORDS_PER_DAY],
        "char_practice": char_practice,
        "all_learned_words": all_learned_words,
    }

def update_hsk_progress(progress: dict, day_num: int, date_str: str, today_pack: dict) -> None:
    new_chars = [w["char"] for w in today_pack["new_words"]]
    introduced = progress.get("introduced_chars", [])
    for ch in new_chars:
        if ch not in introduced: introduced.append(ch)
    progress["introduced_chars"] = introduced

    replacement = {
        "day_num": day_num, "date": date_str,
        "new_chars":        new_chars,
        "review_chars":     [w["char"] for w in today_pack["review_words"]],
        "lesson_chars":     [w["char"] for w in today_pack["lesson_words"]],
        "all_learned_chars":[w["char"] for w in today_pack["all_learned_words"]],
        "char_practice_char": today_pack["char_practice"]["char"],
    }
    days = progress.setdefault("days", [])
    for i, day in enumerate(days):
        if day.get("date") == date_str:
            days[i] = replacement
            save_hsk_progress(progress); return
    days.append(replacement)
    save_hsk_progress(progress)


# ── JSON helpers (unchanged from original) ────────────────────────────────────

def extract_json_object(text: str) -> str:
    text = text.strip().replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    if start == -1: raise ValueError("No JSON object found.")
    depth, in_string, escape_next = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape_next: escape_next = False
            elif ch == "\\": escape_next = True
            elif ch == '"':  in_string = False
            continue
        if ch == '"':  in_string = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: return text[start:i+1]
    raise ValueError("Incomplete JSON object.")

def as_dict_item(item, default_key="text") -> dict:
    return item if isinstance(item, dict) else {default_key: str(item)}

def normalize_list_of_strings(value) -> list:
    if not isinstance(value, list): return []
    out = []
    for item in value:
        if isinstance(item, str): out.append(item)
        elif isinstance(item, dict): out.append(str(item.get("text") or item.get("name") or item.get("task") or item))
        else: out.append(str(item))
    return out

def normalize_vocab_item(item) -> dict:
    if isinstance(item, dict):
        return {"char": str(item.get("char","")), "pinyin": str(item.get("pinyin","")), "meaning": str(item.get("meaning",""))}
    known = WORD_INDEX.get(str(item))
    return known or {"char": str(item), "pinyin": "", "meaning": ""}


# ── Model generation ──────────────────────────────────────────────────────────

def generate_text_local(prompt: str, max_tokens: int | None = None) -> str:
    model, tokenizer = get_local_model()
    try:
        messages = [{"role": "user", "content": prompt}]
        if getattr(tokenizer, "chat_template", None) is not None:
            formatted_prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        else:
            formatted_prompt = f"USER: {prompt}\n\nASSISTANT:"
    except Exception:
        formatted_prompt = f"USER: {prompt}\n\nASSISTANT:"

    print("✓ Model loaded, generating...")
    from mlx_lm import generate
    text = generate(model, tokenizer, prompt=formatted_prompt,
                    max_tokens=max_tokens or MAX_TOKENS, verbose=False)
    print("✓ Done")
    return text.strip()

_PLACEHOLDER_LITERALS = {"quick chore", "reward 1", "reward 2", "reward 3", "reward 4",
                         "playful timed challenge", "tiny reward", "tiny reward idea",
                         "action verb", "past-tense action verb"}

def _is_placeholder(s: str) -> bool:
    """True if string is a bare schema key like 'q1', 'g1', or a known literal template stub."""
    import re
    stripped = s.strip()
    return bool(re.match(r'^[a-z]\d+$', stripped)) or stripped.lower() in _PLACEHOLDER_LITERALS

def _filter_placeholders(lst: list, fallbacks: list) -> list:
    """Replace placeholder items with fallback strings."""
    fb = iter(fallbacks)
    return [next(fb, item) if _is_placeholder(item) else item for item in lst]

def generate_json_object(section_name, prompt, required_keys, fallback, max_tokens=1200) -> dict:
    retry_prompts = [prompt, prompt + "\n\nReturn ONLY one complete valid JSON object. No markdown. No prose."]
    last_error = None
    for attempt, attempt_prompt in enumerate(retry_prompts[:MAX_JSON_RETRIES+1], 1):
        raw = ""
        try:
            print(f"⏳ {section_name} (attempt {attempt})")
            raw = generate_text_local(attempt_prompt, max_tokens=max_tokens)
            data = json.loads(extract_json_object(raw))
            if not isinstance(data, dict): raise ValueError("Not a dict")
            for key in required_keys:
                if key not in data: raise ValueError(f"Missing key: {key}")
            print(f"✓ {section_name}")
            return data
        except Exception as e:
            last_error = e
            ensure_output_dir()
            (OUTPUT_DIR / f"debug_{section_name}.txt").write_text(raw, encoding="utf-8")
            print(f"⚠ {section_name} failed: {e}")
    print(f"⚠ Using fallback for {section_name}")
    return fallback

def ctx_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)



# ── Moon phase (pure Python, no API needed) ───────────────────────────────────

# Named full moons by month
FULL_MOON_NAMES = {
    1:  ("Wolf Moon",      "The deep of winter. A time for stillness, rest, and tending to your inner world."),
    2:  ("Snow Moon",      "The coldest moon. What do you need to let go of before spring can arrive?"),
    3:  ("Worm Moon",      "The earth begins to stir. A time to plan what you want to grow."),
    4:  ("Pink Moon",      "First blooms. Let what has been dormant inside you begin to emerge."),
    5:  ("Flower Moon",    "Full abundance. What seeds you planted are beginning to show themselves."),
    6:  ("Strawberry Moon","The sweetest moon. Celebrate what is already good in your life right now."),
    7:  ("Buck Moon",      "A time of rapid growth. What needs your most focused energy this month?"),
    8:  ("Sturgeon Moon",  "Late summer abundance. What are you harvesting from this year's efforts?"),
    9:  ("Harvest Moon",   "The great reaping. What have you built? What are you proud of?"),
    10: ("Hunter's Moon",  "Preparation for the dark. What do you need to gather before winter comes?"),
    11: ("Beaver Moon",    "Time to build shelter. Tend to your home, your relationships, your resources."),
    12: ("Cold Moon",      "The longest night. Rest is not laziness — it is preparation."),
}

PHASE_SPIRITUAL = {
    "New Moon":        ("New beginnings, intention setting, planting seeds",
                        "A reset point. What do you want to call in this cycle? Write one clear intention."),
    "Waxing Crescent": ("Growth, momentum, taking first steps",
                        "The momentum is building. What small action today moves you toward your intention?"),
    "First Quarter":   ("Decision, commitment, pushing through resistance",
                        "The halfway point to full. What is getting in your way, and what do you choose despite it?"),
    "Waxing Gibbous":  ("Refinement, patience, trust the process",
                        "Almost there. What needs adjusting before things come to fruition?"),
    "Full Moon":       ("Culmination, release, illumination, celebration",
                        "What has come to light? What are you releasing? What are you grateful for?"),
    "Waning Gibbous":  ("Gratitude, sharing, integration",
                        "The peak has passed. What did you learn? Who can you share it with?"),
    "Last Quarter":    ("Letting go, forgiveness, clearing",
                        "Time to release what no longer serves. What habit, thought, or weight do you put down?"),
    "Waning Crescent": ("Rest, surrender, preparation",
                        "The cycle is closing. Rest without guilt. The new moon is coming."),
}


_SYNODIC_MONTH = 29.530588861  # mean days between new moons
_J2000_UTC = datetime(2000, 1, 1, 12)  # Julian Day 2451545.0


def _moon_event_utc(k: float) -> datetime:
    """Exact time (UTC, naive) of lunation k: integer k = new moon, k+0.5 = full moon.

    Meeus, Astronomical Algorithms ch. 49, with the largest periodic terms —
    good to within roughly half an hour, versus up to ~14 h for a mean cycle.
    k = 0 is the new moon of 2000-01-06.
    """
    rad = math.radians
    T = k / 1236.85
    jde = (2451550.09766 + _SYNODIC_MONTH * k
           + 0.00015437 * T**2 - 0.000000150 * T**3 + 0.00000000073 * T**4)
    E  = 1 - 0.002516 * T - 0.0000074 * T**2
    M  = rad(2.5534 + 29.10535670 * k - 0.0000014 * T**2)            # sun's anomaly
    Mp = rad(201.5643 + 385.81693528 * k + 0.0107582 * T**2)         # moon's anomaly
    F  = rad(160.7108 + 390.67050284 * k - 0.0016118 * T**2)         # moon's latitude arg
    if k % 1 == 0:  # new moon
        c = (-0.40720, 0.17241, 0.01608, 0.01039, 0.00739, -0.00514, 0.00208)
    else:           # full moon
        c = (-0.40614, 0.17302, 0.01614, 0.01043, 0.00734, -0.00515, 0.00209)
    jde += (c[0] * math.sin(Mp) + c[1] * E * math.sin(M) + c[2] * math.sin(2 * Mp)
            + c[3] * math.sin(2 * F) + c[4] * E * math.sin(Mp - M)
            + c[5] * E * math.sin(Mp + M) + c[6] * E**2 * math.sin(2 * M))
    return _J2000_UTC + timedelta(days=jde - 2451545.0)


def get_moon_phase(dt: datetime | None = None) -> dict:
    """Calculate moon phase purely from math. No network required.

    `dt` is local wall-clock time (what wb_now() returns). "New Moon" and
    "Full Moon" mean that exact moment falls on this local calendar date, so
    the phase name and the "new moon today" banner always agree.
    """
    if dt is None:
        dt = wb_now()
    utc_offset = dt.astimezone().utcoffset() or timedelta(0)
    dt_utc     = dt - utc_offset
    to_local   = lambda u: u + utc_offset

    # Bracket dt between the new moon before it and the one after it
    k = math.floor((dt_utc - _moon_event_utc(0)).total_seconds() / 86400 / _SYNODIC_MONTH)
    while _moon_event_utc(k) > dt_utc:     k -= 1
    while _moon_event_utc(k + 1) <= dt_utc: k += 1
    prev_new, next_new = _moon_event_utc(k), _moon_event_utc(k + 1)
    full_this = _moon_event_utc(k + 0.5)

    lunar_cycle  = (next_new - prev_new).total_seconds() / 86400
    phase_day    = (dt_utc - prev_new).total_seconds() / 86400
    illumination = (1 - math.cos(2 * math.pi * phase_day / lunar_cycle)) / 2

    today    = dt.date()
    is_new   = to_local(prev_new).date() == today or to_local(next_new).date() == today
    is_full  = to_local(full_this).date() == today
    quarter  = lambda frac: abs(phase_day - lunar_cycle * frac) < 0.5  # within the day

    if is_new:                    phase_name, emoji = "New Moon",        "🌑"
    elif is_full:                 phase_name, emoji = "Full Moon",       "🌕"
    elif quarter(0.25):           phase_name, emoji = "First Quarter",   "🌓"
    elif quarter(0.75):           phase_name, emoji = "Last Quarter",    "🌗"
    elif phase_day < lunar_cycle * 0.25: phase_name, emoji = "Waxing Crescent", "🌒"
    elif full_this > dt_utc:      phase_name, emoji = "Waxing Gibbous",  "🌔"
    elif phase_day < lunar_cycle * 0.75: phase_name, emoji = "Waning Gibbous", "🌖"
    else:                         phase_name, emoji = "Waning Crescent", "🌘"

    # Next full moon (this lunation's, unless it has already passed)
    next_full = full_this if (full_this > dt_utc or is_full) else _moon_event_utc(k + 1.5)
    days_to_full = max(0.0, (next_full - dt_utc).total_seconds() / 86400)

    # Full moon date
    full_moon_dt   = to_local(next_full)
    full_moon_month = full_moon_dt.month
    moon_name, moon_lore = FULL_MOON_NAMES.get(full_moon_month, ("Full Moon", "A time of completion and release."))
    full_moon_label = f"{moon_name} — {full_moon_dt.strftime('%B %d')}"

    # Spiritual meaning for current phase
    keywords, reflection_prompt = PHASE_SPIRITUAL.get(phase_name, ("Mystery", "Sit with the unknown."))

    full_moon_soon  = days_to_full <= 3 and not is_full

    # Next new moon (today's, if it happens today)
    if is_new:
        days_to_new = 0.0
        new_moon_dt = to_local(prev_new if to_local(prev_new).date() == today else next_new)
    else:
        days_to_new = (next_new - dt_utc).total_seconds() / 86400
        new_moon_dt = to_local(next_new)
    new_moon_soon = days_to_new <= 3 and not is_new

    NEW_MOON_LORE = (
        "The new moon is a blank page. Intentions set now are planted in fertile darkness — "
        "they don't need to be seen yet to be real. What do you want to grow this cycle?"
    )

    return {
        "phase_name":         phase_name,
        "emoji":              emoji,
        "phase_day":          round(phase_day, 1),
        "illumination_pct":   round(illumination * 100),
        "days_to_full":       round(days_to_full, 1),
        "days_to_new":        round(days_to_new, 1),
        "is_full":            is_full,
        "is_new":             is_new,
        "full_moon_soon":     full_moon_soon,
        "new_moon_soon":      new_moon_soon,
        "full_moon_label":    full_moon_label,
        "full_moon_name":     moon_name,
        "full_moon_lore":     moon_lore,
        "full_moon_date_str": full_moon_dt.strftime("%B %d, %Y"),
        "new_moon_date_str":  new_moon_dt.strftime("%B %d, %Y"),
        "new_moon_lore":      NEW_MOON_LORE,
        "keywords":           keywords,
        "reflection_prompt":  reflection_prompt,
    }



# ── Cycle tracking ────────────────────────────────────────────────────────────

CYCLE_FILE = DATA_DIR / "cycle_progress.json"


def _cycle_setting(key: str, default: int) -> int:
    """Personal cycle parameters live in CYCLE_FILE, which is gitignored."""
    try:
        return int(json.loads(CYCLE_FILE.read_text(encoding="utf-8"))[key])
    except Exception:
        return default


CYCLE_LENGTH_AVG  = _cycle_setting("cycle_length_avg",  28)
CYCLE_LENGTH_MIN  = _cycle_setting("cycle_length_min",  21)
CYCLE_LENGTH_MAX  = _cycle_setting("cycle_length_max",  35)
PERIOD_LENGTH_AVG = _cycle_setting("period_length_avg",  5)
OVULATION_DAY     = _cycle_setting("ovulation_day",     14)
FOLLICULAR_DAYS   = _cycle_setting("follicular_days",   14)
LUTEAL_DAYS       = _cycle_setting("luteal_days",       14)

CYCLE_PHASES = {
    "menstrual": {
        "name":        "Menstrual",
        "emoji":       "🌹",
        "bg_color":    "#2d0a0a",
        "accent":      "#C8697A",
        "days":        f"Days 1–{PERIOD_LENGTH_AVG}",
        "energy":      "Low & inward",
        "keywords":    "Rest, release, reflection, gentleness",
        "description": "Your body is doing significant work. This is a time for rest, not productivity guilt. The insights that come during bleeding are often the most honest ones.",
        "task_tone":   "Keep it light and optional. Sort, review, and plan rather than produce. Even one small thing moved forward is enough today.",
        "exercise":    "Gentle movement only — slow yoga, short walks, stretching. Listen to your body and stop when it says stop. The dog walks count.",
        "foods":       "Iron-rich foods to replenish: lentils, dark leafy greens, red meat if you eat it, dark chocolate, pumpkin seeds. Warm foods over cold. Bone broth if you have it.",
        "emotional":   "You may feel more emotional or tender than usual — that's information, not weakness. What is your body asking for today?",
                "tea": {
            "blend":   "Cramp bark + ginger + raspberry leaf",
            "why":     "Cramp bark relaxes uterine muscles, ginger warms and reduces inflammation, raspberry leaf tones the uterus and eases flow. A mug in the morning and one before bed.",
            "notes":   "Add a little honey — your body is craving warmth and sweetness right now. Steep 10 min for full benefit.",
        },
        "pms_warning": False,
    },
    "follicular": {
        "name":        "Follicular",
        "emoji":       "🌱",
        "bg_color":    "#0a1f15",
        "accent":      "#6BCB8B",
        "days":        f"Days {PERIOD_LENGTH_AVG + 1}–{OVULATION_DAY - 1}",
        "energy":      "Rising & curious",
        "keywords":    "New beginnings, creativity, momentum, optimism",
        "description": "Estrogen is rising and so is your energy. This is one of the best phases for starting new projects, brainstorming, and tackling things that felt hard last week.",
        "task_tone":   "Lean into new ideas. Good time to start a new project, tackle something you've been avoiding, or dig into a new cert section. Momentum feels easier now.",
        "exercise":    "Your body can handle more — cardio, strength training, trying something new at the gym. Energy is building so use it.",
        "foods":       "Light, fresh foods: salads, fermented foods (yogurt, kimchi), eggs, lean protein. Your digestion is strong right now.",
        "emotional":   "You may feel more social and optimistic. Good time to reach out to people, pitch ideas, or have conversations you've been putting off.",
                "tea": {
            "blend":   "Green tea + spearmint + peppermint",
            "why":     "Green tea gently supports rising estrogen without spiking cortisol. Spearmint has evidence for hormone balance and mental clarity. Peppermint is energising and uplifting — perfect for the follicular phase's rising energy. All three are safe with sertraline and Adderall.",
            "notes":   "Drink in the morning while your meds kick in — a natural focus companion. Brew light so the green tea caffeine doesn't compete with your Adderall.",
        },
        "pms_warning": False,
    },
    "ovulatory": {
        "name":        "Ovulatory",
        "emoji":       "☀️",
        "bg_color":    "#1f1700",
        "accent":      "#FFD166",
        "days":        f"Days {OVULATION_DAY - 1}–{OVULATION_DAY + 2}",
        "energy":      "Peak & magnetic",
        "keywords":    "Communication, confidence, visibility, connection",
        "description": "Peak estrogen and an LH surge mean you're likely at your most energetic, articulate, and socially confident. This window is only a few days — use it intentionally.",
        "task_tone":   "This is your power window. Photograph products, post on social media, reach out to shops or markets, price your work boldly, make sales calls. Do the things that require you to be seen.",
        "exercise":    "High intensity is great right now — HIIT, heavier lifting, longer runs. Your body is primed for it.",
        "foods":       "Raw and light foods, antioxidants: berries, vegetables, seeds, quinoa, salmon. Your metabolism is efficient right now.",
        "emotional":   "You likely feel more confident and warm toward others. Great day for a meaningful conversation with your partner or tackling something that requires courage.",
                "tea": {
            "blend":   "Hibiscus + rose + chamomile",
            "why":     "Hibiscus is cooling and supports circulation at peak body temp. Rose is the flower of the ovulatory phase — it opens the heart and supports confidence. Chamomile keeps the nervous system steady at peak energy.",
            "notes":   "Beautiful iced or hot. Hibiscus is tart — add honey if needed. Brew a big batch and keep it in the fridge.",
        },
        "pms_warning": False,
    },
    "luteal_early": {
        "name":        "Early Luteal",
        "emoji":       "🍂",
        "bg_color":    "#1a1200",
        "accent":      "#D4956A",
        "days":        f"Days {OVULATION_DAY + 3}–{CYCLE_LENGTH_AVG - 5}",
        "energy":      "Steady & detail-oriented",
        "keywords":    "Completion, organization, focus, nesting",
        "description": "Progesterone rises and energy turns inward. You may feel more focused on finishing things rather than starting them — that's useful. Use this phase to complete, organize, and refine.",
        "task_tone":   "Great time for detail work: reviewing study notes, working through practice problems, organizing your learning materials. Less ideal for starting brand new things.",
        "exercise":    "Moderate intensity — strength training, yoga, pilates. Avoid pushing too hard as fatigue builds through this phase.",
        "foods":       "Complex carbs and magnesium: sweet potato, brown rice, nuts, dark chocolate, leafy greens. Your body will start craving comfort foods — lean into the healthy versions.",
        "emotional":   "You may feel more critical of yourself and your work. Remember: that inner critic is partly hormonal right now, not fully accurate. Finish things without judging them too harshly.",
                "tea": {
            "blend":   "Dandelion root + oat straw + cinnamon",
            "why":     "Dandelion root supports liver function which helps process excess progesterone. Oat straw is deeply nourishing and supports the nervous system as energy starts to shift. Cinnamon balances blood sugar — important as cravings begin.",
            "notes":   "Dandelion root has a slightly earthy, almost coffee-like flavor. Good after meals. Add milk and cinnamon to make it cozy.",
        },
        "pms_warning": False,
    },
    "luteal_late": {
        "name":        "Late Luteal / PMS",
        "emoji":       "🌧️",
        "bg_color":    "#0f0a1a",
        "accent":      "#9B8EC4",
        "days":        f"Days {CYCLE_LENGTH_AVG - 4}–{CYCLE_LENGTH_AVG}",
        "energy":      "Low & tender",
        "keywords":    "Sensitivity, rest, compassion, preparation",
        "description": "Progesterone is dropping and your body knows bleeding is coming. You may feel more irritable, tired, or emotional — this is physiological, not personal failure.",
        "task_tone":   "Be extremely gentle with your expectations today. Even showing up is a win. Avoid big decisions, important emails, or anything requiring emotional steadiness. Sort, rest, and prepare.",
        "exercise":    "Light walks, gentle yoga, or swimming. Movement will help with mood but don't push. Rest if you need to — genuinely.",
        "foods":       "Magnesium and B6: dark chocolate, bananas, salmon, nuts, seeds. Reduce caffeine and salt if bloating is an issue. Warm, comforting meals — this is a good night to cook something cozy.",
        "emotional":   "You may feel more sensitive or reactive than usual. That's okay. Try not to catastrophize — most things will look different in a few days. What do you need right now to feel safe and cared for?",
                "tea": {
            "blend":   "Chamomile + passionflower + lavender + nettle",
            "why":     "Passionflower has solid research for PMS-related anxiety and irritability — it works on GABA receptors, not serotonin, so it's safe alongside sertraline. Chamomile reduces inflammation and soothes the gut. Lavender calms the nervous system. Nettle replenishes magnesium which drops before your period.",
            "notes":   "Brew 2 cups a day in the days before your period. Passionflower can be mildly sedating so better in the evening than morning. This blend won't interfere with your sertraline, Adderall, or propranolol.",
        },
        "pms_warning": True,
    },
}


def load_cycle_data() -> dict:
    if not CYCLE_FILE.exists():
        return {"last_period_start": None, "cycle_length_avg": CYCLE_LENGTH_AVG, "history": []}
    try:
        return json.loads(CYCLE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_period_start": None, "cycle_length_avg": CYCLE_LENGTH_AVG, "history": []}


def save_cycle_data(data: dict) -> None:
    ensure_output_dir()
    CYCLE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log_period_start(date_str: str | None = None) -> None:
    """Log today (or a given date) as period start. Run with --log-period."""
    data = load_cycle_data()
    date_str = date_str or today_stamp()
    history  = data.get("history", [])

    # Calculate last cycle length if we have a previous entry
    if data.get("last_period_start"):
        prev = datetime.strptime(data["last_period_start"], "%Y-%m-%d")
        curr = datetime.strptime(date_str, "%Y-%m-%d")
        actual_length = (curr - prev).days
        if CYCLE_LENGTH_MIN <= actual_length <= CYCLE_LENGTH_MAX + 5:
            history.append({"date": data["last_period_start"], "cycle_length": actual_length})
            # Update rolling average from last 3 cycles
            recent = [h["cycle_length"] for h in history[-3:]]
            data["cycle_length_avg"] = round(sum(recent) / len(recent))
            print(f"✓ Last cycle was {actual_length} days. Rolling avg now {data['cycle_length_avg']} days.")

    data["last_period_start"] = date_str
    data["history"] = history[-12:]  # Keep last 12 cycles
    save_cycle_data(data)
    print(f"✓ Period start logged: {date_str}")
    print(f"  Run the workbook tomorrow and the cycle section will be live.")


def get_cycle_info() -> dict:
    """Calculate current cycle phase from stored data."""
    data = load_cycle_data()
    last_start = data.get("last_period_start")
    avg_length = data.get("cycle_length_avg", CYCLE_LENGTH_AVG)

    if not last_start:
        return {
            "available":    False,
            "phase_key":    None,
            "phase":        None,
            "cycle_day":    None,
            "days_in_phase":None,
            "days_until_next_period": None,
            "days_until_ovulation":   None,
            "period_coming_soon":     False,
            "ovulation_soon":         False,
        }

    last_dt  = datetime.strptime(last_start, "%Y-%m-%d")
    today_dt = wb_now().replace(hour=0, minute=0, second=0, microsecond=0)
    cycle_day = (today_dt - last_dt).days + 1  # Day 1 = first day of period

    # Handle cycle rollover
    if cycle_day > avg_length + 5:
        cycle_day = cycle_day % avg_length or avg_length

    # Determine phase using her actual app data
    # Menstrual: days 1-4
    # Follicular: days 5-13 (follicular 14±2, ovulation day 15±2)
    # Ovulatory: days 13-17 (centered on day 15)
    # Luteal early: days 18-22
    # Luteal late / PMS: days 23-avg_length
    if cycle_day <= PERIOD_LENGTH_AVG:
        phase_key = "menstrual"
        days_in_phase = cycle_day
    elif cycle_day <= OVULATION_DAY - 2:
        phase_key = "follicular"
        days_in_phase = cycle_day - PERIOD_LENGTH_AVG
    elif cycle_day <= OVULATION_DAY + 2:
        phase_key = "ovulatory"
        days_in_phase = cycle_day - (OVULATION_DAY - 2)
    elif cycle_day <= avg_length - 5:
        phase_key = "luteal_early"
        days_in_phase = cycle_day - (OVULATION_DAY + 2)
    else:
        phase_key = "luteal_late"
        days_in_phase = cycle_day - (avg_length - 5)

    phase = CYCLE_PHASES[phase_key]
    days_until_next_period = max(0, avg_length - cycle_day + 1)
    days_until_ovulation   = max(0, OVULATION_DAY - cycle_day)
    period_coming_soon     = 0 < days_until_next_period <= 3
    ovulation_soon         = 0 < days_until_ovulation <= 2

    return {
        "available":              True,
        "phase_key":              phase_key,
        "phase":                  phase,
        "cycle_day":              cycle_day,
        "cycle_length_avg":       avg_length,
        "days_in_phase":          days_in_phase,
        "days_until_next_period": days_until_next_period,
        "days_until_ovulation":   days_until_ovulation,
        "period_coming_soon":     period_coming_soon,
        "ovulation_soon":         ovulation_soon,
        "last_period_start":      last_start,
    }



# ── Weather (NWS free API — no key needed) ────────────────────────────────────
# Amherst MA: 42.3732, -72.5199
# NWS pre-resolved grid: BOX 67,87 (Boston office)
# Forecast URL cached to avoid double round-trip every morning

NWS_FORECAST_URL = "https://api.weather.gov/gridpoints/BOX/67,87/forecast"
NWS_HOURLY_URL   = "https://api.weather.gov/gridpoints/BOX/67,87/forecast/hourly"
NWS_ALERTS_URL   = "https://api.weather.gov/alerts/active?point=42.3732,-72.5199"
NWS_HEADERS      = {"User-Agent": "DailyWorkbook/1.0 (personal use)"}
WEATHER_TIMEOUT  = 8  # seconds


def c_to_f(c):
    """Celsius to Fahrenheit."""
    if c is None: return None
    return round(c * 9/5 + 32)


def fetch_weather() -> dict:
    """Fetch today's weather from NWS for Amherst MA. Returns a safe dict always."""
    base = {
        "available":    False,
        "location":     "Amherst, MA",
        "today":        {},
        "tonight":      {},
        "tomorrow":     {},
        "hourly":       [],
        "alerts":       [],
        "error":        None,
    }

    try:
        # ── Fetch forecast (daily periods) ───────────────────────────────────
        req = urllib.request.Request(NWS_FORECAST_URL, headers=NWS_HEADERS)
        with urllib.request.urlopen(req, timeout=WEATHER_TIMEOUT) as resp:
            forecast_data = json.loads(resp.read().decode())

        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            base["error"] = "No forecast periods returned"
            return base

        def parse_period(p):
            return {
                "name":        p.get("name", ""),
                "is_daytime":  p.get("isDaytime", True),
                "temp_f":      p.get("temperature"),
                "temp_unit":   p.get("temperatureUnit", "F"),
                "wind_speed":  p.get("windSpeed", ""),
                "wind_dir":    p.get("windDirection", ""),
                "short_desc":  p.get("shortForecast", ""),
                "detail":      p.get("detailedForecast", ""),
                "precip_pct":  p.get("probabilityOfPrecipitation", {}).get("value") or 0,
                "icon":        p.get("icon", ""),
            }

        # First 3 periods cover today, tonight, tomorrow
        parsed = [parse_period(p) for p in periods[:4]]
        base["today"]    = parsed[0] if len(parsed) > 0 else {}
        base["tonight"]  = parsed[1] if len(parsed) > 1 else {}
        base["tomorrow"] = parsed[2] if len(parsed) > 2 else {}

        # ── Fetch alerts ──────────────────────────────────────────────────────
        try:
            req2 = urllib.request.Request(NWS_ALERTS_URL, headers=NWS_HEADERS)
            with urllib.request.urlopen(req2, timeout=WEATHER_TIMEOUT) as resp2:
                alerts_data = json.loads(resp2.read().decode())
            features = alerts_data.get("features", [])
            base["alerts"] = [
                {
                    "event":    f["properties"].get("event", ""),
                    "headline": f["properties"].get("headline", ""),
                    "severity": f["properties"].get("severity", ""),
                }
                for f in features[:3]  # max 3 alerts
            ]
        except Exception:
            pass  # alerts are nice-to-have, not critical

        # ── Fetch hourly for next 12 hours ────────────────────────────────────
        try:
            req3 = urllib.request.Request(NWS_HOURLY_URL, headers=NWS_HEADERS)
            with urllib.request.urlopen(req3, timeout=WEATHER_TIMEOUT) as resp3:
                hourly_data = json.loads(resp3.read().decode())
            hourly_periods = hourly_data.get("properties", {}).get("periods", [])[:12]
            base["hourly"] = [
                {
                    "time":       p.get("startTime", "")[-14:-9] if p.get("startTime") else "",
                    "temp_f":     p.get("temperature"),
                    "short_desc": p.get("shortForecast", ""),
                    "precip_pct": p.get("probabilityOfPrecipitation", {}).get("value") or 0,
                }
                for p in hourly_periods
            ]
        except Exception:
            pass  # hourly is nice-to-have

        base["available"] = True
        return base

    except Exception as e:
        base["error"] = str(e)
        return base


def weather_emoji(desc: str) -> str:
    """Short text label for weather — emoji fail in Chrome headless PDF export."""
    d = desc.lower()
    if "thunder" in d:                               return "Storm"
    if "snow" in d:                                  return "Snow"
    if "sleet" in d or "ice" in d:                   return "Sleet"
    if "rain" in d or "shower" in d:                 return "Rain"
    if "drizzle" in d:                               return "Drizzle"
    if "fog" in d:                                   return "Fog"
    if "partly cloudy" in d or "mostly sunny" in d:  return "Part. Cloudy"
    if "mostly cloudy" in d or "partly sunny" in d:  return "Mostly Cloudy"
    if "cloudy" in d:                                return "Cloudy"
    if "sunny" in d or "clear" in d:                 return "Sunny"
    if "wind" in d:                                  return "Windy"
    return "—"


# ── Day context ───────────────────────────────────────────────────────────────

def get_day_context() -> dict:
    date_str  = today_stamp()
    weekday   = wb_now().weekday()
    dtype     = day_type(weekday)
    seed      = random.randint(1, 99999)
    start      = datetime(2026, 5, 12)
    day_num    = max(1, (wb_now() - start).days + 1)
    cert_day   = day_num
    weekly_task, weekly_note, weekly_time = CHORE_SCHEDULE[weekday]
    progress  = load_hsk_progress()
    today_hsk = choose_hsk_words_for_today(progress, date_str)

    moon    = get_moon_phase()
    cycle   = get_cycle_info()
    weather = fetch_weather()

    return {
        "today_label": today_label(),
        "today_date":  date_str,
        "weekday":     weekday,
        "dtype":       dtype,
        "seed":        seed,
        "day_num":     day_num,
        "cert_day":    cert_day,
        "weekly_task": weekly_task,
        "weekly_note": weekly_note,
        "weekly_time": weekly_time,
        "today_hsk":   today_hsk,
        "progress":    progress,
        "moon":        moon,
        "cycle":       cycle,
        "weather":     weather,
    }


# ── Section generators ────────────────────────────────────────────────────────

def generate_theme_and_cover(ctx: dict) -> dict:
    fallback = {
        "theme": {"title": "Cozy Sparkle Workshop", "subtitle": "A tiny menu of focus, color, and calm", "mascot": "a little paper lantern fox"},
        "cover": {"welcome": "Welcome to today's workbook.", "pep_talk": "You don't need to finish everything. Pick one useful thing and start there.", "today_big_focus": "Make one cozy batch of progress", "focus_words": ["start", "finish", "review", "rest"], "sticker_caption": "Add a sticker or doodle here when the day begins."},
    }
    prompt = f"""Create ONLY this JSON object:
{{
  "theme": {{"title": "short whimsical title", "subtitle": "cute subtitle", "mascot": "cute object or animal mascot"}},
  "cover": {{"welcome": "2 short sentences", "pep_talk": "1 short encouraging paragraph", "today_big_focus": "one short phrase", "focus_words": ["word 1", "word 2", "word 3", "word 4"], "sticker_caption": "short invitation"}}
}}
Context: {ctx_json({"date": ctx["today_label"], "day_num": ctx["day_num"], "day_type": ctx["dtype"], "vibe": "whimsical, cozy, children's menu, coloring workbook"})}
Rules: JSON only. Concise. No markdown."""
    return generate_json_object("theme_cover", prompt, ["theme", "cover"], fallback, 900)


def generate_morning_page(ctx: dict) -> dict:
    dtype = ctx["dtype"]
    is_work    = dtype == "work"
    is_therapy = dtype == "therapy"

    stretch_types = [
        ("5-min morning spine wake-up", "Start lying down. Hug knees to chest for 30s. Roll to seated cat-cow x5. Standing forward fold 30s. Arms overhead side stretch each side."),
        ("Sun salutation flow", "Mountain pose → arms up → forward fold → plank → cobra → downward dog → forward fold → mountain. Repeat 3 times slowly."),
        ("Hip opener stretch", "Low lunge each side 45s. Seated pigeon each side 45s. Supine spinal twist each side 30s. Child's pose 1 min."),
        ("Desk worker reset", "Neck rolls each direction. Shoulder rolls. Chest opener arms behind back. Wrist circles. Standing quad stretch each side."),
        ("Breathwork + gentle stretch", "Box breathing 4 rounds (4 counts in, hold, out, hold). Seated forward fold. Supine knee-to-chest. End with 2 min savasana."),
    ]
    stretch_name, stretch_desc = random.choice(stretch_types)

    exercise_suggestions = {
        "work":    ["Quick 20-min gym session before or after work — push/pull supersets", "15-min bodyweight circuit at home before you leave — squats, push-ups, rows"],
        "free":    ["Full gym session — upper body focus", "Full gym session — lower body focus", "30-min run or walk outside + 10 min bodyweight"],
        "therapy": ["Just the dog walks count today — take them slow and breathe"],
        "weekend": ["Longer gym session — full body", "Outdoor activity — long walk, hike, or bike ride with the dog", "Home workout — dumbbell circuit 30 min"],
    }
    exercise = random.choice(exercise_suggestions.get(dtype, exercise_suggestions["free"]))

    dinner_suggestions = {
        "work":    ["Sheet pan chicken thighs + roasted broccoli + rice (30 min, mostly hands-off)", "Stir-fry beef + peppers + snap peas over rice (20 min)", "Turkey taco bowls — seasoned meat, black beans, salsa, avocado (25 min)"],
        "free":    ["Homemade ramen — broth, soft-boiled eggs, veggies, pork or tofu", "Stuffed bell peppers with ground beef + quinoa + tomato sauce", "Salmon en papillote + roasted sweet potato + salad"],
        "therapy": ["Simple pasta + marinara + rotisserie chicken + side salad (20 min)", "Eggs any style + toast + sliced veg — easy, low-effort, still good"],
        "weekend": ["Sunday roast chicken + roasted root veg + gravy", "Homemade pizza on naan or flatbread — whatever toppings you have", "Slow cooker chili — set it in the morning, done by dinner"],
    }
    dinner = random.choice(dinner_suggestions.get(dtype, dinner_suggestions["free"]))

    return {
        "stretch_name": stretch_name,
        "stretch_desc": stretch_desc,
        "exercise": exercise,
        "dinner": dinner,
        "is_therapy": is_therapy,
        "is_work": is_work,
    }


def generate_algorithms_page(ctx: dict) -> dict:
    """CS311: today's course-order questions + one random question (cs311.py)."""
    if cs311 is None:
        return {}
    return cs311.daily_set(datetime.strptime(ctx["today_date"], "%Y-%m-%d").date())


def generate_leetcode_page(ctx: dict) -> dict:
    """Today's LeetCode problem + re-solves due (leetcode.py)."""
    if leetcode is None:
        return {}
    return leetcode.daily_set(datetime.strptime(ctx["today_date"], "%Y-%m-%d").date())


def generate_reading_page(ctx: dict) -> dict:
    """Today's saved Substack article (reading.py) + five writing prompts."""
    if reading is None:
        return {}
    article = reading.article_for(datetime.strptime(ctx["today_date"], "%Y-%m-%d").date())
    if not article:
        return {}
    lenses = reading.PROMPT_LENSES
    prompts = article.get("prompts")
    if not prompts or len(prompts) != len(lenses):
        lens_lines = "\n".join(f'{i}. {name}. Must begin with: "{stem}"'
                               for i, (name, stem, _, _) in enumerate(lenses, 1))
        prompt = (
            "You write journaling prompts for someone reading an article on paper. "
            "The prompts should build critical thinking and a deeper understanding of "
            "the topic, not just ask for opinions.\n\n"
            f"Article: {article['title']}" + (f" by {article['author']}" if article.get("author") else "") + "\n\n"
            f"{reading.article_excerpt(article)}\n\n"
            "Write exactly 5 writing prompts, one for each lens below, in the same order. "
            "Each prompt must start with the exact words given, then name a specific "
            "claim, example or idea from THIS article. Each is 1 or 2 sentences and "
            "asks the reader to write, not just answer yes or no.\n"
            "- Lens 1 asks for a plain restatement of the argument, not a new insight.\n"
            "- Lens 2 names one unproven belief the article relies on.\n"
            "- Lens 3 asks the reader to argue the opposite side.\n"
            "- Lens 4 names a specific fact, study or history to look up.\n"
            "- Lens 5 connects to the reader's own life.\n\n"
            f"{lens_lines}\n\n"
            "Reply with only the 5 prompts, numbered 1. to 5., one per line."
        )
        prompts = None
        for attempt in (1, 2):
            try:
                print(f"⏳ reading_prompts (attempt {attempt})")
                got = _parse_numbered_prompts(generate_text_local(prompt, max_tokens=600), len(lenses))
            except Exception as e:
                print(f"⚠ reading_prompts failed: {e}")
                got = {}
            if len(got) >= 4:
                prompts = [got.get(i, lenses[i - 1][2]) for i in range(1, len(lenses) + 1)]
                print("✓ reading_prompts")
                reading.save_prompts(article, prompts)
                break
        if prompts is None:
            print("⚠ Using the general writing prompts")
            prompts = [fallback for _, _, fallback, _ in lenses]
    return {**article, "prompts": [{"lens": name, "text": text, "follow": follow}
                                   for (name, _, _, follow), text in zip(lenses, prompts)]}


def _parse_numbered_prompts(text: str, count: int) -> dict[int, str]:
    """Read '1. ...' lines from model output into {number: prompt}."""
    import re
    out: dict[int, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\s*\(?(\d+)[.):]\s*(.+)$", line)
        if not m:
            continue
        n, body = int(m.group(1)), m.group(2).strip().strip('"*')
        # Drop a lens label the model may have echoed, e.g. "Assumptions: ..."
        body = re.sub(r"^(In your own words|Assumptions|Push back|Go deeper|Connect)\s*[:\-–—]\s*", "", body, flags=re.I)
        if 1 <= n <= count and len(body) > 20 and n not in out:
            out[n] = body
    return out


def generate_chores_page(ctx: dict) -> dict:
    dtype      = ctx["dtype"]
    weekly_task= ctx["weekly_task"]
    weekly_note= ctx["weekly_note"]
    weekly_time= ctx["weekly_time"]
    is_therapy = dtype == "therapy"

    fallback = {
        "title": "Little Home Reset Quest",
        "weekly": {"task": weekly_task, "note": weekly_note, "time_estimate": weekly_time},
        "daily": [
            {"task": "Clear one visible surface.", "time_estimate": "5 min"},
            {"task": "Put away 10 stray items.", "time_estimate": "5 min"},
            {"task": "Reset dishes or sink area.", "time_estimate": "5 min"},
            {"task": "Take out trash or recycling if needed.", "time_estimate": "5 min"},
        ] if not is_therapy else [{"task": "Just the dishes. That's it.", "time_estimate": "5 min"}],
        "speed_run": "Set a 7-min timer and race one tiny mess — not the whole house.",
        "reward_ideas": ["boba point", "sticker", "sweet treat", "cozy show episode"],
    }

    num_daily = 1 if is_therapy else 4
    daily_list = ',\n    '.join(['{"task": "quick chore", "time_estimate": "5 min"}'] * num_daily)

    prompt = f"""Create ONLY this JSON object:
{{
  "title": "cute chore-quest title eg 'Laundry Love & Quick Wins'",
  "weekly": {{"task": "{weekly_task}", "note": "{weekly_note}", "time_estimate": "{weekly_time}"}},
  "daily": [{daily_list}],
  "speed_run": "a specific fun timed challenge eg 'Set a 5-min timer and clear the bathroom counter'",
  "reward_ideas": ["specific tiny reward eg 'boba point'", "specific tiny reward eg 'one show episode'", "specific tiny reward eg 'sweet treat'", "specific tiny reward eg 'cozy blanket time'"]
}}
Context: {ctx_json({"day_type": dtype, "is_therapy_day": is_therapy})}
Rules: JSON only. Daily chores under 10 min. Therapy day = minimal. reward_ideas must be real specific rewards, not placeholder text."""

    return generate_json_object("chores_page", prompt, ["title", "weekly", "daily", "speed_run", "reward_ideas"], fallback, 800)


def _load_parking_lot() -> list[str]:
    """Read parking lot ideas from parking_lot.txt, one idea per line."""
    try:
        lines = PARKING_LOT_FILE.read_text(encoding="utf-8").splitlines()
        items = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        if items:
            return items
    except FileNotFoundError:
        pass
    return ["Add ideas to parking_lot.txt — one per line"]


def generate_admin_parking(ctx: dict) -> dict:
    """Life admin task (free/weekend days) + parking lot for ideas."""
    dtype = ctx["dtype"]
    is_therapy = dtype == "therapy"

    admin_tasks = [
        "Reply to any unread emails that have been sitting more than 3 days",
        "Schedule that appointment you've been putting off",
        "Check and sort physical mail pile",
        "Back up your study notes and progress files",
        "Review your study schedule and adjust if needed",
        "Pick one CS311 lecture to rewatch or review during your online time",
    ]

    parking_items = _load_parking_lot()

    return {
        "admin_task": random.choice(admin_tasks) if not is_therapy else None,
        "parking_items": random.sample(parking_items, min(2, len(parking_items))),
    }


def build_chinese_pages(ctx: dict) -> dict:
    """Deterministic Chinese pages using HSK1 progress — same as original."""
    today_hsk = ctx["today_hsk"]
    lesson_words = today_hsk["lesson_words"][:LESSON_WORDS_PER_DAY]
    review_words = dedupe_words(today_hsk.get("review_words",[]) + today_hsk.get("lesson_words",[]))[:4]
    char_target  = today_hsk["char_practice"]

    helper_words = [
        WORD_INDEX.get("吗") or {"char":"吗","pinyin":"ma","meaning":"question particle"},
        WORD_INDEX.get("很") or {"char":"很","pinyin":"hěn","meaning":"very"},
        WORD_INDEX.get("也") or {"char":"也","pinyin":"yě","meaning":"also"},
        WORD_INDEX.get("是") or {"char":"是","pinyin":"shì","meaning":"to be"},
        WORD_INDEX.get("学生") or {"char":"学生","pinyin":"xué sheng","meaning":"student"},
        WORD_INDEX.get("老师") or {"char":"老师","pinyin":"lǎo shī","meaning":"teacher"},
    ]

    story_pairs = [
        ("你好。",         "nǐ hǎo.",              "Hello."),
        ("我好。",         "wǒ hǎo.",              "I am good."),
        ("你好吗？",       "nǐ hǎo ma?",           "Are you good?"),
        ("我很好。",       "wǒ hěn hǎo.",          "I am very good."),
        ("你也很好。",     "nǐ yě hěn hǎo.",       "You are also very good."),
        ("我是学生。",     "wǒ shì xué sheng.",    "I am a student."),
        ("你是老师吗？",   "nǐ shì lǎo shī ma?",  "Are you a teacher?"),
        ("我不是老师。",   "wǒ bú shì lǎo shī.",  "I am not a teacher."),
        ("我也是学生。",   "wǒ yě shì xué sheng.","I am also a student."),
        ("你好，学生。",   "nǐ hǎo, xué sheng.",  "Hello, student."),
        ("你好，老师。",   "nǐ hǎo, lǎo shī.",    "Hello, teacher."),
        ("我很好，你呢？", "wǒ hěn hǎo, nǐ ne?",  "I am very good. And you?"),
    ]

    char_examples = {"一":"一个","你":"你好","好":"你好","我":"我是学生","是":"我是学生","不":"不是","吗":"你好吗","很":"很好","也":"我也是学生"}

    return {
        "chinese_lesson_page": {
            "title": "Mandarin Mini Noodle Shop",
            "lesson_intro": "Today's Chinese page uses small HSK 1 words and lots of repetition.",
            "new_words_banner": "Today's word basket",
            "review_banner": "Review sprinkles",
            "vocab": lesson_words,
            "review_words": review_words,
            "character_practice": {
                "char": char_target["char"], "pinyin": char_target["pinyin"],
                "meaning": char_target["meaning"],
                "stroke_hint": "Write slowly and copy the shape like a tiny drawing.",
                "example_word": char_examples.get(char_target["char"], char_target["char"]),
            },
            "mini_dialogue": [
                {"speaker":"A","chinese":"你好。","pinyin":"nǐ hǎo.","meaning":"Hello."},
                {"speaker":"B","chinese":"你好。","pinyin":"nǐ hǎo.","meaning":"Hello."},
                {"speaker":"A","chinese":"你好吗？","pinyin":"nǐ hǎo ma?","meaning":"Are you good?"},
                {"speaker":"B","chinese":"我很好。","pinyin":"wǒ hěn hǎo.","meaning":"I am very good."},
            ],
            "tiny_game": "Circle every word you recognize. Copy your favourite line once.",
        },
        "chinese_reference_page": {
            "title": "Tiny Mandarin Menu Card",
            "reference_intro": "Use this page when the story feels slippery. Check the word bank, then go back.",
            "word_bank_title": "Today's HSK 1 word bank",
            "grammar_note": "吗 turns a statement into a yes/no question. 你好吗？ means 'Are you good?'",
            "reader_helper_words": helper_words,
            "reader_translation_title": "Story line helper",
            "reader_line_glosses": [{"line_no": i+1, "chinese": cn, "pinyin": py, "meaning": en} for i,(cn,py,en) in enumerate(story_pairs)],
            "review_quiz_prompts": ["Write the meaning of 你好.", "Which word means I or me?", "Add 吗 to make a question.", "Copy one sentence without looking, then check it."],
        },
        "chinese_reader_page": {
            "title": "Tiny HSK 1 Story",
            "reader_intro": "Read once with pinyin, then cover the pinyin and try again.",
            "story_title": "你好，小学生",
            "story_lines":  [cn for cn,_,_ in story_pairs],
            "pinyin_lines": [py for _,py,_ in story_pairs],
            "comprehension_questions": ["Who says hello?", "Is 我 a teacher?", "Which line asks a question?", "Copy the line that feels easiest."],
            "copywork_prompt": "Copy 3 short lines from the story. Add a sticker next to the neatest one.",
        },
    }


def generate_moon_page(ctx: dict) -> dict:
    """Generate spiritual/reflective moon content using local model."""
    moon = ctx["moon"]
    phase    = moon["phase_name"]
    keywords = moon["keywords"]
    prompt_q = moon["reflection_prompt"]
    is_full  = moon["is_full"]
    soon     = moon["full_moon_soon"]
    moon_name = moon["full_moon_name"]
    moon_lore = moon["full_moon_lore"]

    is_new  = moon.get("is_new", False)
    new_soon = moon.get("new_moon_soon", False)
    new_moon_date = moon.get("new_moon_date_str", "")
    days_to_new   = moon.get("days_to_new", 0)
    new_moon_lore = moon.get("new_moon_lore", "")

    full_moon_extra = ""
    if is_full:
        full_moon_extra = f"Tonight IS the {moon_name}. {moon_lore}"
    elif soon:
        days = moon["days_to_full"]
        full_moon_extra = f"The {moon_name} arrives in {days:.0f} day(s). {moon_lore}"

    new_moon_extra = ""
    if is_new:
        new_moon_extra = f"Tonight IS the New Moon — a powerful time for intention setting. {new_moon_lore}"
    elif new_soon:
        new_moon_extra = f"The New Moon arrives in {days_to_new:.0f} day(s) on {new_moon_date}. {new_moon_lore}"

    cycle_info = moon.get("_cycle_context", "")
    extra_context = " ".join(filter(None, [full_moon_extra, new_moon_extra]))

    fallback = {
        "phase_meaning":     f"The {phase} is a time of {keywords.lower()}.",
        "spiritual_note":    "Every phase of the moon mirrors a phase inside you. Nothing is wasted.",
        "reflection_q":      prompt_q,
        "ritual_suggestion": "Light a candle, take three slow breaths, and write one honest sentence about where you are right now.",
        "full_moon_message": full_moon_extra if (is_full or soon) else "",
        "new_moon_message":  new_moon_extra if (is_new or new_soon) else "",
    }

    prompt = f"""Create ONLY this JSON object:
{{
  "phase_meaning": "2-3 sentences about what the {phase} means spiritually and energetically",
  "spiritual_note": "one gentle poetic observation about this moon phase and inner life",
  "reflection_q": "one deep but accessible reflection question for this phase",
  "ritual_suggestion": "one simple 2-minute ritual or practice suited to this phase (no supplies needed)",
  "full_moon_message": "{full_moon_extra if (is_full or soon) else "leave this as an empty string"}",
  "new_moon_message": "{new_moon_extra if (is_new or new_soon) else "leave this as an empty string"}"
}}
Context: Phase is {phase} ({keywords}). {extra_context}
Rules: JSON only. Warm, spiritual but grounded. No toxic positivity. Short strings."""

    return generate_json_object("moon_page", prompt,
        ["phase_meaning","spiritual_note","reflection_q","ritual_suggestion","full_moon_message","new_moon_message"],
        fallback, 700)


def generate_creativity_page(ctx: dict) -> dict:
    fallback = {
        "title": "Sticker Soup Studio",
        "intro": "This page is for looseness, scribbles, and tiny visual ideas. No drawing has to be useful.",
        "doodle_prompts": ["Draw today's mascot holding a pencil.", "Draw a cozy mug with a Chinese word on it.", "Invent a sticker for finishing chores.", "Sketch a tiny trophy for completing a cert module.", "Draw a border of stars, vines, or noodles.", "Make a tiny badge design for CS311 or HSK 1."],
        "affirmations": ["Small starts count.", "Messy progress is still progress.", "I can make one useful thing.", "Done can be cute."],
        "sticker_labels": ["started", "finished", "reviewed", "tidied", "studied", "learned", "rested", "sparkled"],
        "coloring_caption": "Color, scribble, decorate, or ignore the rules.",
    }
    prompt = """Create ONLY this JSON object:
{
  "title": "cute whimsical page title eg 'Sparkle & Sway'",
  "intro": "1-2 concise sentences about this being a low-pressure creative page",
  "doodle_prompts": ["specific drawing prompt eg 'Draw today's mascot holding a pencil'", "specific drawing prompt", "specific drawing prompt", "specific drawing prompt", "specific drawing prompt", "specific drawing prompt"],
  "affirmations": ["short encouraging phrase eg 'Small starts count'", "short encouraging phrase", "short encouraging phrase", "short encouraging phrase"],
  "sticker_labels": ["past-tense verb eg 'started'", "past-tense verb eg 'learned'", "past-tense verb eg 'rested'", "past-tense verb eg 'made'", "past-tense verb", "past-tense verb", "past-tense verb", "past-tense verb"],
  "coloring_caption": "one short playful caption eg 'Cozy doodles await'"
}
Context: Whimsical ADHD-friendly workbook. Cozy, playful, low-pressure.
Rules: JSON only. Short strings. All values must be real content, not placeholder text."""
    return generate_json_object("creativity_page", prompt, ["title","intro","doodle_prompts","affirmations","sticker_labels","coloring_caption"], fallback, 800)


def generate_reflection_and_back(ctx: dict) -> dict:
    dtype = ctx["dtype"]
    fallback = {
        "reflection_page": {
            "title": "Evening Crumb Trail",
            "questions": ["What tiny thing moved forward today?", "What felt easier than expected?", "What needs a smaller next step?", "What should tomorrow-me see first?"],
            "wins_prompt": "List three small wins, even if they look silly.",
            "tomorrow_steps": ["Pick one task from the workbook.", "Set out one tool or supply.", "Review today's Chinese words once.", "Choose a tiny reward."],
            "gratitude_prompts": ["Something cozy", "Something useful", "Something funny"],
            "bedtime_note": "Close the workbook gently. The day does not need a perfect ending.",
        },
        "back_page": {
            "closing_note": "You collected proof that the day existed and had movement in it.",
            "tiny_rewards": ["tea", "boba", "sticker", "show", "snack", "cozy blanket"],
            "tomorrow_preview": "Tomorrow gets a fresh page and a smaller first step.",
        },
    }
    prompt = f"""Create ONLY this JSON object:
{{
  "reflection_page": {{
    "title": "cute title",
    "questions": ["evening reflection question", "evening reflection question", "evening reflection question", "evening reflection question"],
    "wins_prompt": "short prompt",
    "tomorrow_steps": ["tomorrow step", "tomorrow step", "tomorrow step", "tomorrow step"],
    "gratitude_prompts": ["gratitude prompt", "gratitude prompt", "gratitude prompt"],
    "bedtime_note": "gentle closing"
  }},
  "back_page": {{
    "closing_note": "closing note",
    "tiny_rewards": ["tiny reward", "tiny reward", "tiny reward", "tiny reward", "tiny reward", "tiny reward"],
    "tomorrow_preview": "preview prompt"
  }}
}}
Context: {ctx_json({"day_type": dtype})}
Rules: JSON only. Gentle and cozy."""
    return generate_json_object("reflection_back", prompt, ["reflection_page","back_page"], fallback, 900)


def generate_workbook_content() -> dict:
    ctx = get_day_context()
    print(f"\n📅 Day type: {ctx['dtype'].upper()} — {ctx['today_label']}")
    print("⏳ Generating workbook section by section...\n")

    wb = {"day_num": ctx["day_num"], "_dtype": ctx["dtype"], "_today_date": ctx["today_date"]}

    wb.update(generate_theme_and_cover(ctx))
    wb["_morning"]    = generate_morning_page(ctx)
    wb["_algorithms"] = generate_algorithms_page(ctx)
    wb["_leetcode"]   = generate_leetcode_page(ctx)
    wb["_italian"]    = italian.daily_set(datetime.strptime(ctx["today_date"], "%Y-%m-%d").date()) if italian else {}
    wb["_reading"]    = generate_reading_page(ctx)
    wb["chores_page"] = generate_chores_page(ctx)
    wb["_admin_parking"] = generate_admin_parking(ctx)
    wb["_offline"] = offline_plan.today_summary(wb_now().date()) if offline_plan else {}
    wb.update(build_chinese_pages(ctx))
    wb["_moon"]           = ctx["moon"]
    wb["_weather"]        = ctx["weather"]
    wb["_moon_page"]      = generate_moon_page(ctx)
    wb["_cycle"]          = ctx["cycle"]
    wb.update(generate_reflection_and_back(ctx))

    wb["_hsk_internal"] = ctx["today_hsk"]
    wb["_progress"]     = ctx["progress"]

    return wb


# ── Normalization (keeps original safety nets) ────────────────────────────────

def normalize(wb: dict) -> dict:
    wb.setdefault("theme", {})
    wb["theme"].setdefault("title", "Cozy Sparkle Workshop")
    wb["theme"].setdefault("subtitle", "A tiny menu of focus, color, and calm")
    wb["theme"].setdefault("mascot", "a little paper lantern fox")

    wb.setdefault("cover", {})
    wb["cover"].setdefault("welcome", "Welcome to today's workbook.")
    wb["cover"].setdefault("pep_talk", "Pick one useful thing and begin there.")
    wb["cover"].setdefault("today_big_focus", "Make one cozy batch of progress")
    import re as _re
    if _re.search(r'\bword\s*\d\b', wb["cover"]["today_big_focus"], _re.IGNORECASE):
        wb["cover"]["today_big_focus"] = "Make one cozy batch of progress"
    _fw_fallbacks = ["start", "finish", "review", "rest"]
    wb["cover"]["focus_words"] = _filter_placeholders(normalize_list_of_strings(wb["cover"].get("focus_words", [])), _fw_fallbacks)
    # Also strip any word that is literally "word N"
    wb["cover"]["focus_words"] = [_fw_fallbacks[i % 4] if _re.match(r'^word\s*\d', w, _re.IGNORECASE) else w for i, w in enumerate(wb["cover"]["focus_words"])]
    while len(wb["cover"]["focus_words"]) < 4:
        wb["cover"]["focus_words"].append(_fw_fallbacks[len(wb["cover"]["focus_words"])])
    wb["cover"].setdefault("sticker_caption", "Add a sticker or doodle here when the day begins.")

    # Certs

    # Chores
    wb.setdefault("chores_page", {})
    wb["chores_page"].setdefault("title","Little Home Reset Quest")
    wb["chores_page"].setdefault("weekly",{"task":"Kitchen reset","note":"Wipe surfaces.","time_estimate":"20 min"})
    wb["chores_page"]["weekly"] = as_dict_item(wb["chores_page"]["weekly"],"task")
    wb["chores_page"]["weekly"].setdefault("task","Kitchen reset")
    wb["chores_page"]["weekly"].setdefault("note","Wipe surfaces.")
    wb["chores_page"]["weekly"].setdefault("time_estimate","20 min")
    _chore_fallbacks = iter(["Clear one visible surface.", "Put away 10 stray items.", "Reset dishes or sink area.", "Take out trash or recycling if needed."])
    wb["chores_page"]["daily"] = [as_dict_item(t,"task") for t in wb["chores_page"].get("daily",[])]
    while len(wb["chores_page"]["daily"]) < 2:
        wb["chores_page"]["daily"].append({"task":"Clear one surface.","time_estimate":"5 min"})
    for t in wb["chores_page"]["daily"]:
        t.setdefault("task",""); t.setdefault("time_estimate","")
        if _is_placeholder(t["task"]):
            t["task"] = next(_chore_fallbacks, "Clear one surface.")
    _speed_run = wb["chores_page"].get("speed_run", "")
    if not _speed_run or _is_placeholder(_speed_run) or _speed_run.lower() in _PLACEHOLDER_LITERALS:
        wb["chores_page"]["speed_run"] = "Set a 7-min timer and race one tiny mess — not the whole house."
    _reward_fallbacks = ["boba point", "sticker", "sweet treat", "cozy show episode"]
    wb["chores_page"]["reward_ideas"] = _filter_placeholders(normalize_list_of_strings(wb["chores_page"].get("reward_ideas",[])), _reward_fallbacks)
    while len(wb["chores_page"]["reward_ideas"]) < 4:
        wb["chores_page"]["reward_ideas"].append(_reward_fallbacks[len(wb["chores_page"]["reward_ideas"]) % len(_reward_fallbacks)])

    # Chinese
    for page_key, list_key in [("chinese_lesson_page","vocab"),("chinese_lesson_page","review_words"),("chinese_reference_page","reader_helper_words")]:
        wb.setdefault(page_key,{})
        wb[page_key][list_key] = [normalize_vocab_item(i) for i in wb[page_key].get(list_key,[])]
    wb["chinese_lesson_page"].setdefault("title","Mandarin Mini Noodle Shop")
    wb["chinese_lesson_page"].setdefault("lesson_intro","HSK 1 words and repetition.")
    wb["chinese_lesson_page"].setdefault("new_words_banner","Today's word basket")
    wb["chinese_lesson_page"].setdefault("review_banner","Review sprinkles")
    while len(wb["chinese_lesson_page"]["vocab"]) < 4:
        wb["chinese_lesson_page"]["vocab"].append(HSK1_VOCAB[len(wb["chinese_lesson_page"]["vocab"])])
    wb["chinese_lesson_page"].setdefault("character_practice",{"char":"你","pinyin":"nǐ","meaning":"you","stroke_hint":"Copy slowly.","example_word":"你好"})
    cp = wb["chinese_lesson_page"]["character_practice"]
    cp.setdefault("char","你"); cp.setdefault("pinyin","nǐ"); cp.setdefault("meaning","you")
    cp.setdefault("stroke_hint","Copy slowly."); cp.setdefault("example_word","你好")
    wb["chinese_lesson_page"]["mini_dialogue"] = [as_dict_item(l,"chinese") for l in wb["chinese_lesson_page"].get("mini_dialogue",[])]
    while len(wb["chinese_lesson_page"]["mini_dialogue"]) < 4:
        wb["chinese_lesson_page"]["mini_dialogue"].append({"speaker":"A","chinese":"你好。","pinyin":"nǐ hǎo.","meaning":"Hello."})
    for l in wb["chinese_lesson_page"]["mini_dialogue"]:
        l.setdefault("speaker",""); l.setdefault("chinese",""); l.setdefault("pinyin",""); l.setdefault("meaning","")
    wb["chinese_lesson_page"].setdefault("tiny_game","Circle every word you recognize.")

    wb.setdefault("chinese_reference_page",{})
    wb["chinese_reference_page"].setdefault("title","Tiny Mandarin Menu Card")
    wb["chinese_reference_page"].setdefault("reference_intro","Use this page when the story feels slippery.")
    wb["chinese_reference_page"].setdefault("word_bank_title","Today's HSK 1 word bank")
    wb["chinese_reference_page"].setdefault("grammar_note","吗 turns a statement into a yes/no question.")
    wb["chinese_reference_page"].setdefault("reader_translation_title","Story line helper")
    wb["chinese_reference_page"].setdefault("reader_line_glosses",[])
    wb["chinese_reference_page"].setdefault("review_quiz_prompts",[])
    wb["chinese_reference_page"]["review_quiz_prompts"] = normalize_list_of_strings(wb["chinese_reference_page"]["review_quiz_prompts"])

    wb.setdefault("chinese_reader_page",{})
    wb["chinese_reader_page"].setdefault("title","Tiny HSK 1 Story")
    wb["chinese_reader_page"].setdefault("reader_intro","Read once with pinyin, then cover and try again.")
    wb["chinese_reader_page"].setdefault("story_title","你好，小学生")
    wb["chinese_reader_page"].setdefault("story_lines",[])
    wb["chinese_reader_page"].setdefault("pinyin_lines",[])
    wb["chinese_reader_page"].setdefault("comprehension_questions",[])
    wb["chinese_reader_page"].setdefault("copywork_prompt","Copy 3 short lines from the story.")

    # Creativity
    wb.setdefault("creativity_page",{})
    wb["creativity_page"].setdefault("title","Sticker Soup Studio")
    wb["creativity_page"].setdefault("intro","This page is for scribbles and tiny visual ideas.")
    _dp_fallbacks = ["Draw today's mascot holding a pencil.", "Draw a cozy mug with a Chinese word on it.", "Invent a sticker for finishing chores.", "Sketch a tiny trophy for completing a cert module.", "Draw a border of stars, vines, or noodles.", "Make a tiny badge design for CS311 or HSK 1."]
    wb["creativity_page"]["doodle_prompts"] = _filter_placeholders(normalize_list_of_strings(wb["creativity_page"].get("doodle_prompts",[])), _dp_fallbacks)
    while len(wb["creativity_page"]["doodle_prompts"]) < 6:
        wb["creativity_page"]["doodle_prompts"].append(_dp_fallbacks[len(wb["creativity_page"]["doodle_prompts"]) % len(_dp_fallbacks)])
    _aff_fallbacks = ["Small starts count.", "Messy progress is still progress.", "I can make one useful thing.", "Done can be cute."]
    wb["creativity_page"]["affirmations"] = _filter_placeholders(normalize_list_of_strings(wb["creativity_page"].get("affirmations",[])), _aff_fallbacks)
    while len(wb["creativity_page"]["affirmations"]) < 4:
        wb["creativity_page"]["affirmations"].append(_aff_fallbacks[len(wb["creativity_page"]["affirmations"]) % len(_aff_fallbacks)])
    _sl_fallbacks = ["started","finished","reviewed","tidied","studied","learned","rested","sparkled"]
    wb["creativity_page"]["sticker_labels"] = _filter_placeholders(normalize_list_of_strings(wb["creativity_page"].get("sticker_labels",[])), _sl_fallbacks)
    while len(wb["creativity_page"]["sticker_labels"]) < 8:
        wb["creativity_page"]["sticker_labels"].append(_sl_fallbacks[len(wb["creativity_page"]["sticker_labels"]) % len(_sl_fallbacks)])
    wb["creativity_page"].setdefault("coloring_caption","Color, scribble, decorate, or ignore the rules.")

    # Reflection
    wb.setdefault("reflection_page",{})
    wb["reflection_page"].setdefault("title","Evening Crumb Trail")
    _q_fallbacks = ["What tiny thing moved forward today?", "What felt easier than expected?", "What needs a smaller next step?", "What should tomorrow-me see first?"]
    wb["reflection_page"]["questions"] = _filter_placeholders(normalize_list_of_strings(wb["reflection_page"].get("questions",[])), _q_fallbacks)
    while len(wb["reflection_page"]["questions"]) < 4:
        wb["reflection_page"]["questions"].append(_q_fallbacks[len(wb["reflection_page"]["questions"])])
    wb["reflection_page"].setdefault("wins_prompt","List three small wins.")
    _s_fallbacks = ["Pick one task from the workbook.", "Set out one tool or supply.", "Review today's Chinese words once.", "Choose a tiny reward."]
    wb["reflection_page"]["tomorrow_steps"] = _filter_placeholders(normalize_list_of_strings(wb["reflection_page"].get("tomorrow_steps",[])), _s_fallbacks)
    while len(wb["reflection_page"]["tomorrow_steps"]) < 4:
        wb["reflection_page"]["tomorrow_steps"].append("Pick one small first step.")
    _g_fallbacks = ["Something cozy", "Something useful", "Something funny"]
    wb["reflection_page"]["gratitude_prompts"] = _filter_placeholders(normalize_list_of_strings(wb["reflection_page"].get("gratitude_prompts",[])), _g_fallbacks)
    while len(wb["reflection_page"]["gratitude_prompts"]) < 3:
        wb["reflection_page"]["gratitude_prompts"].append("Something cozy")
    wb["reflection_page"].setdefault("bedtime_note","Close the workbook gently.")

    wb.setdefault("back_page",{})
    wb["back_page"].setdefault("closing_note","You collected proof that the day existed and had movement in it.")
    _r_fallbacks = ["tea", "boba", "sticker", "show", "snack", "cozy blanket"]
    wb["back_page"]["tiny_rewards"] = _filter_placeholders(normalize_list_of_strings(wb["back_page"].get("tiny_rewards",[])), _r_fallbacks)
    while len(wb["back_page"]["tiny_rewards"]) < 6:
        wb["back_page"]["tiny_rewards"].append("sticker")
    wb["back_page"].setdefault("tomorrow_preview","Tomorrow gets a fresh page and a smaller first step.")

    return wb


# ── HTML rendering ────────────────────────────────────────────────────────────

STYLES = """
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family: Avenir, Helvetica, Arial, sans-serif; color:#3E302E; background:#fffdf9; }

  .page {
    width: 8.5in;
    height: 11in;
    overflow: hidden;
    padding: 0.45in;
    page-break-after: always;
    break-after: page;
    background:
      radial-gradient(circle at 8% 7%, rgba(255,226,194,0.55) 0 10%, transparent 11%),
      radial-gradient(circle at 92% 12%, rgba(207,235,255,0.45) 0 10%, transparent 11%),
      radial-gradient(circle at 12% 88%, rgba(222,246,229,0.45) 0 10%, transparent 11%),
      radial-gradient(circle at 90% 90%, rgba(251,222,245,0.35) 0 9%, transparent 10%),
      #fffdf8;
  }
  .page:last-child { page-break-after:auto; break-after:auto; }
  /* Pages that may run longer than one sheet (worked problems, articles). */
  .page.flow { height:auto; min-height:11in; overflow:visible; }
  .page.flow .frame { -webkit-box-decoration-break:clone; box-decoration-break:clone; }

  .frame {
    border:3px dashed #f0d9c7;
    border-radius:24px;
    min-height:10.1in;
    height: auto;
    padding:18px 20px;
    background:rgba(255,255,255,0.90);
    display:flex;
    flex-direction:column;
  }

  .eyebrow, .section-label { font-family:Menlo,Monaco,monospace; text-transform:uppercase; letter-spacing:0.12em; font-size:10px; color:#998a7f; margin-bottom:8px; }
  .main-title { font-size:30px; color:#e56d5c; line-height:1.1; margin-bottom:6px; font-weight:800; }
  .sub-title { font-size:14px; color:#77665f; margin-bottom:14px; }
  .section-head { margin-bottom:10px; }
  .section-title { font-size:21px; color:#4b3a35; margin-top:2px; font-weight:800; }
  .bubble { display:inline-block; font-size:11px; padding:4px 8px; border-radius:999px; background:#fff2cc; border:2px dashed #f4c87a; color:#71562d; vertical-align:middle; margin-left:6px; }

  .hero-card, .card { border:2px solid #f2e6d9; border-radius:18px; padding:14px 16px; background:rgba(255,255,255,0.97); box-shadow:0 3px 0 rgba(237,224,212,0.7); margin-bottom:12px; }
  .hero-card { border-style:dashed; }

  .split { overflow:hidden; }
  .split > * { float:left; width:48%; margin-right:2%; box-sizing:border-box; }
  .split-3 { overflow:hidden; }
  .split-3 > * { float:left; width:32%; margin-right:1%; box-sizing:border-box; }

  .mini-title { font-size:15px; color:#5b4841; margin-bottom:8px; font-weight:800; }
  .mini-note { font-size:12px; color:#7a665b; margin-top:4px; }
  .footer-note { font-size:12px; color:#7b6b61; line-height:1.45; }
  .cert-link { display:inline-block; margin-top:6px; font-size:10px; font-family:Menlo,Monaco,monospace; color:#5A8DAE; text-decoration:none; background:#EFF7FF; border-radius:5px; padding:2px 7px; border:1px solid #B8D8F0; word-break:break-all; }

  .check-card { display:flex; gap:10px; align-items:flex-start; border:2px dashed; border-radius:14px; padding:10px 12px; margin-bottom:10px; }
  .check-box { width:18px; height:18px; border:2px solid; border-radius:6px; background:white; flex-shrink:0; margin-top:2px; }
  .check-title { font-size:14px; font-weight:800; color:#4a3b35; line-height:1.35; }
  .chip { display:inline-block; padding:4px 8px; border-radius:999px; border:2px dashed; margin:3px 4px 3px 0; font-size:11px; font-weight:800; }

  .cover-focus { font-size:22px; color:#4d3f3a; margin-top:6px; font-weight:800; }
  .medium-blank, .tiny-blank { border:2px dashed #e6d5c4; border-radius:16px; background:#fff; padding:10px; }
  .medium-blank { min-height:90px; }
  .tiny-blank { min-height:58px; border-radius:12px; }
  .star-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
  .star { width:26px; height:26px; border:2px dashed #f4c87a; border-radius:8px; background:white; }

  .one-thing-box { border:3px solid #E56D5C; border-radius:18px; background:#FFF8F7; padding:16px 18px; margin-bottom:14px; }
  .one-thing-label { font-family:Menlo,Monaco,monospace; font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:#E56D5C; margin-bottom:6px; }
  .one-thing-title { font-size:18px; font-weight:800; color:#4b3a35; margin-bottom:12px; line-height:1.2; }
  .one-thing-line { border-bottom:2.5px solid #E56D5C; height:40px; margin-bottom:8px; }
  .brain-dump-box { border:2px dashed #C8A0E0; border-radius:16px; background:#FAF2FF; padding:14px 16px; margin-bottom:12px; }
  .brain-dump-title { font-size:14px; font-weight:800; color:#5d4085; margin-bottom:4px; }
  .brain-dump-sub { font-size:12px; color:#8A6BAE; margin-bottom:10px; }
  .brain-dump-line { border-bottom:1.5px dashed #C8A0E0; height:28px; margin-bottom:6px; }

  .table-wrap { border:2px dashed #f0d6b2; border-radius:16px; padding:10px; background:#fffaf2; }
  table { width:100%; border-collapse:collapse; }
  th { text-align:left; font-family:Menlo,Monaco,monospace; text-transform:uppercase; letter-spacing:0.08em; font-size:10px; color:#9c8d7e; padding-bottom:8px; font-weight:400; }
  td { vertical-align:middle; padding:7px 4px 7px 0; border-top:2px dashed #f3dec0; }
  .price-name { font-size:13px; font-weight:800; color:#58473b; }
  .fill-box { border:2px solid #f2bf77; border-radius:9px; background:white; }
  .fill-box.small { width:70px; height:26px; }

  .vocab-grid { overflow:hidden; }
  .vocab-grid > * { float:left; width:32%; margin-right:1%; margin-bottom:8px; box-sizing:border-box; }
  .vocab-card { border:2px solid #bee9e2; background:#f3fffd; border-radius:14px; padding:10px; }
  .vocab-char { font-size:24px; font-weight:900; color:#23675e; }
  .vocab-pinyin { font-family:Menlo,Monaco,monospace; font-size:11px; color:#56867f; margin-top:2px; }
  .vocab-meaning { font-size:12px; color:#375b56; margin:4px 0 8px; }

  .trace-row { display:flex; gap:4px; flex-wrap:wrap; }
  .trace-box { border:2px dashed #ffb7b2; border-radius:8px; background:white; position:relative; }
  .trace-box::before { content:""; position:absolute; left:50%; top:0; bottom:0; width:1px; background:#f5d6d3; }
  .trace-box::after  { content:""; position:absolute; top:50%; left:0; right:0; height:1px; background:#f5d6d3; }
  .trace-box.big  { width:46px; height:46px; display:inline-block; margin-right:5px; margin-bottom:5px; }
  .trace-box.mini { width:28px; height:28px; }

  .dialogue-card { border:2px dashed #d7c6ff; border-radius:14px; padding:10px 12px; background:#faf7ff; margin-bottom:8px; }
  .dialogue-speaker { font-family:Menlo,Monaco,monospace; font-size:10px; color:#7b67a8; text-transform:uppercase; letter-spacing:0.08em; }
  .dialogue-main { font-size:18px; font-weight:900; color:#4c3d6a; margin-top:3px; }
  .dialogue-sub { font-family:Menlo,Monaco,monospace; font-size:11px; color:#7b7190; margin-top:3px; }
  .dialogue-meaning { font-size:12px; color:#5f5770; margin-top:4px; }

  .gloss-grid { overflow:hidden; }
  .gloss-grid > * { float:left; width:48%; margin-right:2%; margin-bottom:8px; box-sizing:border-box; }
  .gloss-card { border:2px dashed #d7e0ef; border-radius:14px; padding:9px 10px; background:#f8fbff; }
  .gloss-line-no { font-family:Menlo,Monaco,monospace; font-size:10px; color:#627b97; text-transform:uppercase; }
  .gloss-cn { font-size:15px; font-weight:900; color:#37495d; margin-top:4px; }
  .gloss-pinyin { font-family:Menlo,Monaco,monospace; font-size:10px; color:#64788f; margin-top:2px; }
  .gloss-en { font-size:11px; color:#59697b; margin-top:4px; }

  .reader-line { margin-bottom:8px; }
  .reader-cn { font-size:18px; font-weight:900; color:#4b3a35; line-height:1.25; }
  .reader-pinyin { font-family:Menlo,Monaco,monospace; font-size:10px; color:#85756d; margin-top:2px; }

  .doodle-grid { overflow:hidden; }
  .doodle-grid > * { float:left; width:48%; margin-right:2%; margin-bottom:10px; box-sizing:border-box; }
  .doodle-cloud { border:2px dashed #f5c690; border-radius:18px; background:#fff9f1; min-height:82px; padding:10px; display:flex; align-items:center; justify-content:center; text-align:center; }
  .doodle-cloud-text { font-size:13px; font-weight:800; color:#755338; }

  .sticker-grid { overflow:hidden; }
  .sticker-grid > * { float:left; width:24%; margin-right:1%; margin-bottom:8px; box-sizing:border-box; }
  .sticker-slot { border:2px dashed #f2b5cf; background:#fff8fb; border-radius:16px; padding:8px; text-align:center; min-height:86px; }
  .sticker-circle { width:34px; height:34px; border:2px solid #f2b5cf; border-radius:50%; background:white; margin:2px auto 8px; }
  .sticker-label { font-size:11px; font-weight:800; color:#7b5164; }

  .mascot { font-size:12px; display:inline-block; padding:5px 10px; border:2px dashed #c8b6ff; border-radius:999px; background:#f7f4ff; color:#5d4d85; margin-top:8px; font-weight:800; }

  .dog-block { border:2px dashed #FFAB76; border-radius:16px; background:#FFF5EC; padding:12px 14px; margin-bottom:10px; }
  .dog-block-title { font-size:14px; font-weight:800; color:#7A4010; margin-bottom:8px; }
  .morning-checklist { border:2px dashed #B5D8A8; border-radius:16px; background:#F3FFF0; padding:12px 14px; margin-bottom:10px; }
  .morning-checklist-title { font-size:14px; font-weight:800; color:#2E6B1E; margin-bottom:8px; }
  .stretch-card { border:2px dashed #D8B4D8; border-radius:16px; background:#FBF0FF; padding:12px 14px; margin-bottom:10px; }
  .exercise-card { border:2px dashed #A8C4D8; border-radius:16px; background:#EFF7FF; padding:12px 14px; margin-bottom:10px; }
  .dinner-card { border:2px dashed #F4C87A; border-radius:16px; background:#FFFBF0; padding:12px 14px; margin-bottom:10px; }
  .admin-card { border:2px dashed #90C0B0; border-radius:16px; background:#F0FFF8; padding:12px 14px; margin-bottom:10px; }
  .parking-card { border:2px dashed #C8C8C8; border-radius:16px; background:#F9F9F9; padding:12px 14px; margin-bottom:10px; }
  .article-title { font-family:Georgia,'Times New Roman',serif; font-size:24px; font-weight:700; line-height:1.25; color:#2b2b2b; margin:4px 0 6px; }
  .article-byline { font-family:Menlo,Monaco,monospace; font-size:10.5px; color:#8a7a6a; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:12px; }
  .article-body { font-family:Georgia,'Times New Roman',serif; font-size:12.5px; line-height:1.6; color:#2f2f2f; }
  .article-body p, .article-body li { margin:0 0 9px; display:block; }
  .article-body h3 { font-size:15px; margin:14px 0 6px; color:#3a3a3a; }
  .article-body blockquote { margin:8px 0 10px; padding:4px 12px; border-left:3px solid #e6d5c4; color:#555; font-style:italic; }
  .prompt-card { padding:10px 14px; margin-bottom:9px; }
  .lc-card { padding:10px 14px; margin-bottom:9px; }
  .lc-statement { font-size:13px; font-weight:700; color:#3c3c3c; line-height:1.45; margin-bottom:6px; }
  .lc-example { font-family:Menlo,Monaco,monospace; font-size:11px; line-height:1.5; background:#F6F8FB; border:1px solid #DCE4EE; border-radius:8px; padding:6px 9px; margin:5px 0; color:#333; }
  .lc-why { font-family:inherit; color:#777; }
  .lc-ex-grid { display:grid; grid-template-columns:1fr 1fr; gap:0 8px; }
  .lc-ex-grid .lc-example { margin:4px 0; }
  .lc-howto { font-size:12px; line-height:1.45; color:#4a4a4a; background:#FFFBF0; }
  .lc-step { display:flex; gap:10px; margin-bottom:6px; }
  .lc-letter { flex:0 0 26px; height:26px; border-radius:50%; background:#2F5277; color:white; font-weight:800; font-size:13px; display:flex; align-items:center; justify-content:center; margin-top:2px; }
  .lc-step-body { flex:1; }
  .umpire-key { display:grid; grid-template-columns:1fr 1fr; gap:3px 14px; margin:7px 0; font-size:11.5px; }
  .umpire-key > div { display:flex; align-items:center; gap:6px; }
  .lc-letter.sm { flex:0 0 18px; width:18px; height:18px; font-size:10px; margin:0; display:inline-flex; }
  .lc-meta { font-size:11px; font-weight:600; color:#8a8a8a; }
  .lc-review { margin-bottom:8px; }
  .lc-hint { font-size:12.5px; line-height:1.45; padding:6px 0; border-bottom:1px dashed #DCE4EE; }
  .lc-code { font-family:Menlo,Monaco,monospace; font-size:10.5px; line-height:1.45; background:#F6F8FB; border:1px solid #DCE4EE; border-radius:8px; padding:8px 10px; white-space:pre-wrap; margin:6px 0; color:#222; }
  .prompt-text { font-size:13px; font-weight:700; color:#3c3c3c; line-height:1.45; margin:6px 0 2px; }
  .prompt-follow { font-size:12px; font-style:italic; color:#6a6a6a; line-height:1.4; margin-bottom:2px; }
  .hz-card { padding:10px 14px; margin-bottom:9px; }
  .hz-head { display:flex; gap:12px; align-items:center; margin-bottom:6px; }
  .hz-title { font-size:26px; font-weight:800; color:#2B665E; }
  .hz-pinyin { font-size:15px; font-weight:600; color:#6a6a6a; margin-left:6px; }
  .so-strip { display:flex; flex-wrap:wrap; gap:4px; margin:4px 0 8px; }
  .so-cell { position:relative; }
  .so-num { position:absolute; top:1px; left:4px; font-size:8px; font-weight:800; color:#E56D5C; }
  .tzg-row { display:flex; gap:3px; margin-bottom:4px; }
  .tzg { display:block; }
  .ms-grid { margin-top:8px; }
  .ms-row { display:flex; margin-bottom:6px; }
  .ms-row .tzg { margin-right:-1px; }
  .algo-intro { background:#FFFBF0; border-color:#F5D38B; padding:12px 16px; }
  .algo-kicker { display:block; font-family:Menlo,Monaco,monospace; font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:#9a7b3c; margin-bottom:2px; }
  .algo-bigidea { font-size:15px; font-weight:700; color:#3c3c3c; line-height:1.45; margin-bottom:8px; }
  .algo-picture { font-size:13px; color:#4a4a4a; line-height:1.5; margin-bottom:6px; }
  .algo-signals { margin-top:6px; }
  .algo-num { font-family:Menlo,Monaco,monospace; font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:#8a7a6a; }
  .viz { margin:8px 0; text-align:center; }
  .viz svg { max-width:100%; height:auto; }
  .walk-label { font-size:11px; font-weight:800; color:#2F5277; text-align:left; margin-bottom:4px; }
  .algo-q + .algo-q { margin-top:18px; padding-top:14px; border-top:2px dashed #EADFD2; }
  .algo-warm { background:#F3FBF8; border-color:#9DD9D2; }
  .algo-own { border-color:#C8B6FF; }
  .algo-upside { margin-top:6px; text-align:right; }
  .algo-upside span { display:inline-block; transform:rotate(180deg); font-size:10.5px; line-height:1.35; color:#8a7f75; max-width:90%; text-align:left; }
  .walk-step { display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,1fr); gap:12px; align-items:center;
               background:#fff; border:1px solid #EADFD2; border-radius:12px; padding:6px 12px; margin-bottom:7px; }
  .walk-step .viz { margin:0; }
  .walk-n { display:inline-block; width:20px; height:20px; border-radius:50%; background:#FFF5D9; border:1px solid #D6A53C;
            color:#7D5B21; font-weight:800; font-size:11px; text-align:center; line-height:20px; margin-right:6px; }
  .walk-say { font-size:12.5px; line-height:1.45; color:#3c3c3c; }
  .walk-look { margin-top:6px; font-size:11.5px; line-height:1.35; color:#2B665E; background:#EFFFF7; border-radius:6px; padding:3px 7px; }
  .algo-walk-title { font-size:12.5px; font-weight:800; color:#5a4a3a; margin-top:6px; }
  .algo-tip { font-size:12px; color:#2B665E; background:#EFFFF7; border-radius:8px; padding:6px 10px; margin-top:6px; }
  .algo-sketch { margin-top:4px; }
  .algo-card { padding:10px 14px; margin-bottom:9px; }
  .algo-problem { font-size:12.5px; font-weight:700; color:#3c3c3c; line-height:1.4; margin-bottom:4px; }
  .algo-steps { margin:3px 0 6px 18px; padding:0; font-size:12px; line-height:1.38; color:#444; }
  .algo-steps li { margin-bottom:1px; }
  .algo-why { font-size:12px; line-height:1.4; color:#4a4a4a; background:#F7F4FF; border-left:3px solid #C8B6FF; padding:6px 10px; border-radius:6px; }
  .checkin-row { margin-top:8px; }
  .checkin-label { font-size:13px; font-weight:700; color:#5a4a3a; margin-bottom:2px; }
  .energy-scale { display:flex; align-items:center; gap:10px; margin:6px 0 4px; }
  .energy-dot { width:28px; height:28px; border:2px solid #E6D5C4; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; color:#8a7a6a; }
  .offline-card { border:2px dashed #8FB8DE; border-radius:16px; background:#F2F8FF; padding:12px 14px; margin-bottom:10px; }
  .offline-headline { font-size:18px; font-weight:800; color:#2F5277; margin-bottom:4px; }
  .evening-dog { border:2px dashed #C8A0E0; border-radius:16px; background:#F9F2FF; padding:12px 14px; margin-bottom:10px; }

  .moon-card { border:2px solid #9B8EC4; border-radius:18px; background:#fff; padding:14px 16px; margin-bottom:12px; color:#2b2540; }
  .moon-emoji { font-size:40px; text-align:center; margin-bottom:4px; display:block; }
  .moon-phase-name { font-size:22px; font-weight:800; color:#2b2540; text-align:center; margin-bottom:4px; }
  .moon-illumination { font-family:Menlo,Monaco,monospace; font-size:12px; color:#444; text-align:center; margin-bottom:12px; }
  .moon-section-label { font-family:Menlo,Monaco,monospace; font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:3px; font-weight:700; }
  .moon-text { font-size:13px; color:#222; line-height:1.55; margin-bottom:10px; }
  .moon-reflection { border:1.5px solid #9B8EC4; border-radius:12px; background:#fff; padding:10px 12px; margin:0 0 6px; }
  .moon-reflection-q { font-size:14px; font-weight:800; color:#2b2540; }
  .moon-ritual { border-left:3px solid #9B8EC4; padding-left:10px; margin:10px 0; }
  .moon-ritual-text { font-size:13px; color:#222; font-style:italic; }
  .moon-write-line { border-bottom:1px solid #bbb; height:26px; margin-bottom:8px; }
  .full-moon-alert, .new-moon-alert { border:1.5px solid #9B8EC4; border-radius:14px; background:#fff; padding:10px 12px; margin-top:12px; }
  .full-moon-alert { border-color:#C9A227; }
  .full-moon-alert-title, .new-moon-alert-title { font-size:14px; font-weight:800; color:#222; margin-bottom:6px; }
  .full-moon-alert-text, .new-moon-alert-text { font-size:13px; color:#333; line-height:1.5; }

  .cycle-card { border:2px solid #ccc; border-radius:18px; padding:14px 16px; margin-bottom:12px; background:#fff; color:#222; }
  .cycle-phase-name { font-size:22px; font-weight:800; margin-bottom:2px; color:#222; }
  .cycle-day-label { font-family:Menlo,Monaco,monospace; font-size:12px; margin-bottom:10px; color:#555; }
  .cycle-section-label { font-family:Menlo,Monaco,monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:3px; color:#555; font-weight:700; }
  .cycle-text { font-size:13px; line-height:1.55; margin-bottom:10px; color:#222; }
  .cycle-row { overflow:hidden; margin-bottom:10px; }
  .cycle-row > * { float:left; width:48%; margin-right:2%; box-sizing:border-box; }
  .cycle-block { border-radius:12px; padding:9px 12px; background:#fff; border:1px solid #ccc; }
  .cycle-block-title { font-size:11px; font-weight:800; margin-bottom:4px; color:#555; text-transform:uppercase; letter-spacing:0.06em; }
  .cycle-block-text { font-size:12.5px; line-height:1.45; color:#222; }
  .cycle-alert { border-radius:12px; padding:9px 12px; background:#fff; border:1.5px solid #ccc; margin-top:10px; }
  .cycle-alert-title { font-size:13px; font-weight:800; margin-bottom:4px; color:#222; }
  .cycle-alert-text { font-size:12.5px; color:#333; line-height:1.45; }
  .cycle-emotional { border-radius:12px; padding:10px 12px; background:#fff; border:1px solid #ccc; margin-top:10px; }
  .cycle-emotional-q { font-size:14px; font-weight:800; margin-bottom:8px; color:#222; }
  .cycle-write-line { border-bottom:1px solid #bbb; height:26px; margin-bottom:8px; }
  .cycle-bar-wrap { display:flex; gap:3px; margin:8px 0 4px; }
  .cycle-bar-seg { height:8px; border-radius:4px; flex:1; border:1px solid #bbb; background:#fff; }

  .weather-card { border:2px dashed #90BFDF; border-radius:18px; background:#EFF7FF; padding:14px 16px; margin-bottom:12px; }
  .weather-main { display:flex; align-items:center; gap:14px; margin-bottom:12px; }
  .weather-emoji { font-size:18px; font-weight:800; color:#1A4A6E; background:#D6EAFF; border-radius:8px; padding:6px 10px; line-height:1; white-space:nowrap; }
  .weather-temp { font-size:36px; font-weight:800; color:#1A4A6E; line-height:1; }
  .weather-desc { font-size:14px; color:#2C6E9E; margin-top:2px; font-weight:500; }
  .weather-wind { font-size:12px; color:#5A8DAE; margin-top:2px; }
  .weather-grid { overflow:hidden; margin-bottom:10px; }
  .weather-grid > * { float:left; width:48%; margin-right:2%; margin-bottom:8px; box-sizing:border-box; }
  .weather-block { background:rgba(255,255,255,0.7); border-radius:10px; padding:8px 10px; }
  .weather-block-label { font-family:Menlo,Monaco,monospace; font-size:10px; text-transform:uppercase; letter-spacing:0.07em; color:#5A8DAE; margin-bottom:3px; }
  .weather-block-val { font-size:14px; font-weight:800; color:#1A4A6E; }
  .weather-block-sub { font-size:11px; color:#5A8DAE; margin-top:1px; }
  .weather-hourly { display:flex; gap:6px; overflow-x:auto; padding-bottom:4px; }
  .weather-hour { text-align:center; min-width:44px; background:rgba(255,255,255,0.6); border-radius:8px; padding:6px 4px; flex-shrink:0; }
  .weather-hour-time { font-family:Menlo,Monaco,monospace; font-size:9px; color:#5A8DAE; }
  .weather-hour-temp { font-size:13px; font-weight:800; color:#1A4A6E; margin:2px 0; }
  .weather-hour-precip { font-size:9px; color:#6A9FBF; }
  .weather-alert { border:2px solid #E05A5A; border-radius:10px; background:#FFF0F0; padding:8px 10px; margin-bottom:6px; }
  .weather-alert-title { font-size:12px; font-weight:800; color:#C03030; }
  .weather-alert-sub { font-size:11px; color:#A04040; margin-top:2px; }

  @page { size: Letter; margin: 0.25in; }

  @media print {
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    html, body { margin:0 !important; padding:0 !important; background:white !important; width:auto !important; height:auto !important; }

    .page {
      width: 8in !important;
      height: 10.5in !important;
      overflow: hidden !important;
      margin: 0 auto !important;
      padding: 0.32in !important;
      box-shadow: none !important;
      page-break-after: always !important;
      break-after: page !important;
      page-break-before: auto !important;
      break-before: auto !important;
    }
    .page:last-child { page-break-after: auto !important; break-after: auto !important; }
    .page.flow { height: auto !important; min-height: 10.3in !important; overflow: visible !important; box-sizing: border-box !important; }
    .page.flow .frame { min-height: 0 !important; display: block !important; }
    .page.flow { padding-bottom: 0 !important; }
    .page.flow .cycle-card { page-break-inside: auto !important; break-inside: auto !important; }

    .frame { min-height: 9.86in !important; height: auto !important; max-height: none !important; overflow: visible !important; display: flex !important; flex-direction: column !important; }

    .card, .hero-card, .weather-card, .weather-alert,
    .moon-card, .moon-reflection, .moon-ritual,
    .full-moon-alert, .new-moon-alert,
    .cycle-card, .cycle-block, .cycle-alert, .cycle-emotional,
    .dog-block, .morning-checklist, .one-thing-box, .brain-dump-box,
    .stretch-card, .exercise-card, .dinner-card,
    .admin-card, .parking-card, .offline-card, .algo-card, .algo-intro, .walk-step, .prompt-card, .lc-card, .hz-card, .evening-dog,
    .vocab-card, .check-card, .dialogue-card, .gloss-card,
    .doodle-cloud, .sticker-slot {
      page-break-inside: avoid !important;
      break-inside: avoid !important;
    }

    .section-head, .section-title, .mini-title {
      page-break-after: avoid !important;
      break-after: avoid !important;
    }

    .vocab-grid, .sticker-grid, .gloss-grid, .doodle-grid,
    .weather-grid, .cycle-row, .split, .split-3,
    .trace-row, .weather-hourly {
      page-break-inside: avoid !important;
      break-inside: avoid !important;
    }

    .page { font-size: 95% !important; }
    .card, .hero-card, .weather-card, .moon-card, .cycle-card { margin-bottom:9px !important; }
  }
</style>
"""


def build_html(wb: dict) -> str:
    theme      = wb["theme"]
    cover      = wb["cover"]
    algo       = wb.get("_algorithms") or {}
    chores     = wb["chores_page"]
    chinese_lesson = wb["chinese_lesson_page"]
    chinese_ref    = wb["chinese_reference_page"]
    chinese_reader = wb["chinese_reader_page"]
    creativity     = wb["creativity_page"]
    reflection     = wb["reflection_page"]
    back           = wb["back_page"]
    morning        = wb.get("_morning", {})
    moon_data      = wb.get("_moon", {})
    cycle_data     = wb.get("_cycle", {})
    weather_data   = wb.get("_weather", {})
    moon_page      = wb.get("_moon_page", {})
    admin_parking  = wb.get("_admin_parking", {})
    dtype          = wb.get("_dtype", "free")
    date_label     = today_label()
    day_num        = wb.get("day_num", 1)

    is_work    = dtype == "work"
    is_therapy = dtype == "therapy"
    is_weekend = dtype == "weekend"

    # ── Helper lambdas ────────────────────────────────────────────────────────

    def blank_lines(count, color="#D8D0C8", height=24):
        return "".join(f'<div style="border-bottom:2px dashed {color};height:{height}px;margin-bottom:8px;"></div>' for _ in range(count))

    def chip(text, bg="#FFF2CC", border="#F4C87A", fg="#6F5430"):
        return f'<span class="chip" style="background:{bg};border-color:{border};color:{fg};">{esc(text)}</span>'

    def checkbox_item(text, note="", border="#F4B183", bg="#FFF7EF"):
        note_html = f'<div class="mini-note">{esc(note)}</div>' if note else ""
        return f'<div class="check-card" style="border-color:{border};background:{bg};"><div class="check-box" style="border-color:{border};"></div><div><div class="check-title">{esc(text)}</div>{note_html}</div></div>'

    def section_title(label, title, bubble):
        return f'<div class="section-head"><div class="section-label">{esc(label)}</div><div class="section-title">{esc(title)} <span class="bubble">{esc(bubble)}</span></div></div>'

    def ms_grid(rows):
        if hanzi:
            return hanzi.manuscript(rows, 13, 0.48)
        return blank_lines(rows * 2, "#d7e0ef", 26)

    def vocab_card(v):
        return f'<div class="vocab-card"><div class="vocab-char">{esc(v.get("char",""))}</div><div class="vocab-pinyin">{esc(v.get("pinyin",""))}</div><div class="vocab-meaning">{esc(v.get("meaning",""))}</div></div>'

    def doodle_cloud(text):
        return f'<div class="doodle-cloud"><div class="doodle-cloud-text">{esc(text)}</div></div>'

    def sticker_grid(labels):
        return "".join(f'<div class="sticker-slot"><div class="sticker-circle"></div><div class="sticker-label">{esc(l)}</div></div>' for l in labels)

    def dialogue_row(line):
        return f'<div class="dialogue-card"><div class="dialogue-speaker">{esc(line.get("speaker",""))}</div><div class="dialogue-main">{esc(line.get("chinese",""))}</div><div class="dialogue-sub">{esc(line.get("pinyin",""))}</div><div class="dialogue-meaning">{esc(line.get("meaning",""))}</div></div>'

    # ── Build HTML sections ───────────────────────────────────────────────────

    focus_chips = "".join(chip(w) for w in cover["focus_words"])
    chores_weekly_html = checkbox_item(f"⭐ {chores['weekly'].get('task','')}", f"{chores['weekly'].get('note','')} · {chores['weekly'].get('time_estimate','')}", "#D89BE8", "#FCF5FF")
    chores_daily_html = "".join(checkbox_item(t.get("task",""), t.get("time_estimate",""), "#C8B6FF", "#F8F6FF") for t in chores["daily"])
    lesson_vocab_html = "".join(vocab_card(v) for v in chinese_lesson["vocab"])
    review_vocab_html = "".join(vocab_card(v) for v in chinese_lesson["review_words"][:3])
    dialogue_html = "".join(dialogue_row(l) for l in chinese_lesson["mini_dialogue"])
    helper_html = "".join(vocab_card(v) for v in chinese_ref["reader_helper_words"])
    gloss_html = "".join(f'<div class="gloss-card"><div class="gloss-line-no">Line {esc(str(item.get("line_no","")))} </div><div class="gloss-cn">{esc(item.get("chinese",""))}</div><div class="gloss-pinyin">{esc(item.get("pinyin",""))}</div><div class="gloss-en">{esc(item.get("meaning",""))}</div></div>' for item in chinese_ref["reader_line_glosses"])
    reader_html = "".join(f'<div class="reader-line"><div class="reader-cn">{esc(cn)}</div><div class="reader-pinyin">{esc(py)}</div></div>' for cn,py in zip(chinese_reader["story_lines"], chinese_reader["pinyin_lines"]))
    char_boxes = "".join('<div class="trace-box big"></div>' for _ in range(8))
    doodle_html = "".join(doodle_cloud(p) for p in creativity["doodle_prompts"])
    affirmation_chips = "".join(chip(a, "#EFFFF7","#9DD9D2","#2B665E") for a in creativity["affirmations"])
    reward_chips = "".join(chip(r,"#FFF0F5","#F2B5CF","#7B4C62") for r in chores["reward_ideas"])
    gratitude_chips = "".join(chip(g,"#FFF8E7","#F5D38B","#7D5B21") for g in reflection["gratitude_prompts"])
    tiny_rewards = "".join(chip(r,"#F7F4FF","#C8B6FF","#5D4D85") for r in back["tiny_rewards"])

    # Admin + parking
    admin_task = admin_parking.get("admin_task")
    parking_items = admin_parking.get("parking_items", [])
    admin_html = ""
    if admin_task:
        admin_html = f'<div class="admin-card"><div class="mini-title">📬 Life admin</div>{checkbox_item(admin_task, "Quick one — get it off the list.", "#90C0B0","#F0FFF8")}</div>'
    parking_html = ""
    if parking_items:
        items_html = "".join(f'<div class="footer-note" style="margin-bottom:6px;">💡 {esc(p)}</div>' for p in parking_items)
        parking_html = f'<div class="parking-card"><div class="mini-title">🅿️ Parking lot — ideas only, not tasks</div><div class="footer-note" style="color:#aaa;margin-bottom:8px;">These aren\'t on your plate yet. Just keeping them warm.</div>{items_html}</div>'

    # Stretch + exercise + dinner
    stretch_name = morning.get("stretch_name","Morning stretch")
    stretch_desc = morning.get("stretch_desc","Take 5 minutes to move gently.")
    exercise_suggestion = morning.get("exercise","Move your body today.")
    dinner_suggestion = morning.get("dinner","Cook something with protein and vegetables.")

    parts = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>",
        f"<title>Daily Workbook — {esc(date_label)}</title>",
        STYLES,
        "</head><body>",
    ]

    parts.append("<!--SECTION:cover-->")
    # ── PAGE 1: Cover + Morning ───────────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  <div class="eyebrow">Day {day_num} · whimsical daily workbook</div>
  <div class="main-title">✨ {esc(theme["title"])} ✨</div>
  <div class="sub-title">{esc(theme["subtitle"])} · {esc(date_label)}</div>
  <div class="mascot">Today's mascot: {esc(theme["mascot"])}</div>

  <div class="one-thing-box">
    <div class="one-thing-label">Before anything else —</div>
    <div class="one-thing-title">⭐ What is the ONE thing that would make today feel like a win?</div>
    <div class="one-thing-line"></div>
    <div style="font-size:11px;color:#E56D5C;margin-top:4px;">Write it here first. Everything else is bonus.</div>
  </div>

  <div class="morning-checklist">
    <div class="morning-checklist-title">☀️ Your morning care — while meds kick in</div>
    {checkbox_item("Take ADHD medication","Right when you wake up","#B5D8A8","#F3FFF0")}
    {checkbox_item("Eat breakfast","Protein if possible — don't skip on busy days","#B5D8A8","#F3FFF0")}
    {checkbox_item("Drink a glass of water","","#B5D8A8","#F3FFF0")}
  </div>

  <div class="dog-block">
    <div class="dog-block-title">🐾 Dog morning care — non-negotiable</div>
    {checkbox_item("Give morning meds with food","Don't skip — he needs these daily","#FFAB76","#FFF5EC")}
    {checkbox_item("Morning walk","Good boy time","#FFAB76","#FFF5EC")}
    {checkbox_item("Top up food + fresh water","","#FFAB76","#FFF5EC")}
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append(f"""
<div class="page"><div class="frame">
  <div class="stretch-card">
    <div class="mini-title">🧘 Stretch / yoga — {esc(stretch_name)}</div>
    <div class="footer-note">{esc(stretch_desc)}</div>
    {checkbox_item("Done my stretch","","#D8B4D8","#FBF0FF")}
  </div>
  <div class="brain-dump-box">
    <div class="brain-dump-title">🧠 Brain dump — clear the tabs</div>
    <div class="brain-dump-sub">Dump everything rattling around in your head before you start. Worries, ideas, to-dos, random thoughts — get it out of your brain and onto paper.</div>
    {''.join('<div class="brain-dump-line"></div>' for _ in range(9))}
  </div>

  <div class="card">
    <div class="mini-title">☕ Morning check-in</div>
    <div class="checkin-row"><div class="checkin-label">How am I feeling?</div>{blank_lines(2)}</div>
    <div class="checkin-row"><div class="checkin-label">Energy</div>
      <div class="energy-scale">{"".join(f'<span class="energy-dot">{i}</span>' for i in range(1, 6))}<span class="mini-note" style="margin-left:8px;">circle one</span></div>
    </div>
    <div class="checkin-row"><div class="checkin-label">What's my top goal today, and what might get in the way?</div>{blank_lines(3)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:cs311-->")
    # ── CS311: topic intro, worked problems with pictures, your turn ─────────
    def viz(spec):
        if not spec or not cs311_visuals:
            return ""
        try:
            return f'<div class="viz">{cs311_visuals.render(spec)}</div>'
        except Exception as e:  # a bad spec shouldn't sink the whole workbook
            print(f"⚠ CS311 diagram skipped: {e}")
            return ""

    def viz_walk(frames):
        if not frames or not cs311_visuals:
            return ""
        try:
            return f'<div class="viz walk"><div class="walk-label">Watch it happen</div>{cs311_visuals.render_walkthrough(frames)}</div>'
        except Exception as e:
            print(f"⚠ CS311 walkthrough skipped: {e}")
            return ""

    def upside(label, text):
        """Printed upside down: turn the page to check, so it's not read by accident."""
        if not text:
            return ""
        return f'<div class="algo-upside"><span><b>{esc(label)}:</b> {esc(text)}</span></div>'

    def walk_html(prob):
        """The worked problem, one small step per row: picture on the left, words on the right."""
        walk = prob.get("walk") or []
        if not walk:  # older entries: a strip of frames + a text list of steps
            steps = "".join(f"<li>{esc(st)}</li>" for st in prob.get("steps", []))
            return f"""{viz_walk(prob.get("walkthrough"))}
  <div class="card algo-card"><div class="algo-walk-title">Let's walk through it</div><ol class="algo-steps">{steps}</ol></div>"""
        rows = ""
        for j, st in enumerate(walk, 1):
            look = f'<div class="walk-look">👀 {esc(st["look"])}</div>' if st.get("look") else ""
            rows += f"""
  <div class="walk-step">
    <div class="walk-pic">{viz(st.get("visual"))}</div>
    <div class="walk-text"><span class="walk-n">{j}</span><span class="walk-say">{esc(st.get("say",""))}</span>{look}</div>
  </div>"""
        return rows

    def practice_card(pr, label, extra=""):
        picture = viz(pr.get("visual"))
        return f"""
  <div class="card algo-card algo-own">
    <div class="algo-num">{label}</div>{extra}
    <div class="algo-problem">{esc(pr.get("problem",""))}</div>
    {picture}
    <div class="algo-sketch"><span class="mini-note">{"Mark up the picture, then explain your answer." if picture else "Sketch it first, then write your answer."}</span>{blank_lines(5)}</div>
    {upside("Hint (only if you're stuck)", pr.get("hint"))}
  </div>"""

    def cs311_page(q, track, show_intro=True):
        """One CS311 question: warm-up, a picture-by-picture walkthrough, then one on your own."""
        intro = (q.get("intro") or {}) if show_intro else {}
        topic = q.get("topic", "Algorithms")
        full_intro = track == "course" and q.get("question_number") == 1
        intro_html = ""
        if intro and full_intro:
            signals = "".join(chip(x, "#F7F4FF", "#C8B6FF", "#5D4D85") for x in intro.get("you_know_it_when", []))
            intro_html = f"""
  <div class="card algo-intro">
    <div class="algo-bigidea"><span class="algo-kicker">The big idea</span>{esc(intro.get("big_idea",""))}</div>
    <div class="algo-picture"><span class="algo-kicker">Picture this</span>{esc(intro.get("picture_this",""))}</div>
    {viz(intro.get("visual"))}
    <div class="algo-signals"><span class="algo-kicker">You know it's this topic when…</span><div>{signals}</div></div>
  </div>
  <div class="card algo-card">
    <div class="mini-title">🧠 What do you remember?</div>
    <div class="footer-note">Before reading on: what do you already remember about {esc(topic)} from lecture or the book? A word, a picture, a half-remembered rule all count.</div>
    {blank_lines(3)}
  </div>"""
        elif intro:
            intro_html = f"""
  <div class="card algo-intro">
    <div class="algo-bigidea"><span class="algo-kicker">{"Reminder: the big idea" if track == "course" else "The big idea"}</span>{esc(intro.get("big_idea",""))}</div>
  </div>"""
        prob = q.get("worked") or {}
        warm = prob.get("warmup") or {}
        warm_html = ""
        if warm:
            warm_html = f"""
  <div class="card algo-card algo-warm">
    <div class="algo-num">① Warm-up · about a minute</div>
    <div class="algo-problem">{esc(warm.get("question",""))}</div>
    {viz(warm.get("visual"))}
    {blank_lines(2)}
    {upside("Answer", warm.get("answer"))}
  </div>"""
        tip = f'<div class="algo-tip">💡 {esc(prob["tip"])}</div>' if prob.get("tip") else ""
        worked_html = f"""
  <div class="card algo-card">
    <div class="algo-num">{"② " if warm else ""}Walk through it together</div>
    <div class="mini-title">{esc(prob.get("title",""))}</div>
    <div class="algo-problem">{esc(prob.get("problem",""))}</div>
    {viz(prob.get("visual"))}
  </div>
  {walk_html(prob)}
  <div class="card algo-card">
    <div class="algo-why"><b>Why it works.</b> {esc(prob.get("why",""))}</div>
    {tip}
  </div>"""
        practice_html = practice_card(q.get("practice") or {}, f'{"③ " if warm else ""}On your own · no peeking')
        qpos = f'Q{q.get("question_number","")} of {q.get("question_count","")}'
        if track == "course":
            kicker = "cs311 · course order"
            stamp = f'topic {q.get("topic_number","")}/{q.get("topic_count","")} · {qpos}'
            note = "Warm up, follow the pictures step by step, then do the matching one on your own. Answers are on the last page."
        else:
            kicker = "cs311 · random pick"
            stamp = "random pick"
            note = "A question from anywhere in the course, to keep things fresh. Same three steps; answers are on the last page."
        sub = f'{q.get("chapter","")} · {q.get("lectures","")} · {qpos} · Kleinberg & Tardos'
        # No page wrapper: questions flow one after another (see below), so a short
        # question doesn't leave half a printed page empty.
        return f"""
  <div class="algo-q">
  {section_title(kicker, topic, stamp)}
  <div class="footer-note" style="margin-bottom:10px;">{esc(sub)}. {esc(note)}</div>
  {intro_html}
  {warm_html}
  {worked_html}
  {practice_html}
  </div>
"""

    def review_page(reviews):
        cards = ""
        for r in reviews:
            try:
                when = datetime.strptime(r.get("from_date", ""), "%Y-%m-%d").strftime("%a %b %-d")
            except ValueError:
                when = r.get("from_date", "")
            extra = f'<div class="footer-note">{esc(r.get("topic",""))} Q{r.get("question_number","")} · you did this on {esc(when)}</div>'
            cards += practice_card(r.get("practice") or {}, "Redo it cold", extra)
        return f"""
<div class="page flow"><div class="frame">
  {section_title("cs311 · spaced review", "Can you still do it?", f"{len(reviews)} from earlier days")}
  <div class="footer-note" style="margin-bottom:10px;">Questions you already did. Try them without looking back at that day's pages: pulling it out of memory is what makes it stick. Answers are on the last page.</div>
  {cards}
</div></div>
"""

    seen_topics = set()
    questions = []
    for q in algo.get("course_order") or []:
        # Intro once per topic per day; later questions on the same topic skip it.
        questions.append(cs311_page(q, "course", show_intro=q.get("topic") not in seen_topics))
        seen_topics.add(q.get("topic"))
    if algo.get("random"):
        questions.append(cs311_page(algo["random"], "random"))
    if questions:
        parts.append(f'<div class="page flow"><div class="frame">{"".join(questions)}</div></div>')
    if algo.get("review"):
        parts.append(review_page(algo["review"]))

    parts.append("<!--SECTION:leetcode-->")
    # ── LeetCode: worksheet (UMPIRE) ─────────────────────────────────────────
    lc = wb.get("_leetcode") or {}
    if lc:
        lp = lc.get("problem")
        reviews_html = ""
        for r in lc.get("reviews", []):
            reviews_html += (f'<div class="card lc-card"><div class="mini-title">🔁 Re-solve from memory: #{r["lc"]} {esc(r["title"])} '
                             f'<span class="lc-meta">{esc(r["pattern"])} · from {r["days_ago"]} days ago</span></div>'
                             f'<div class="footer-note">From memory: write the key idea, then the code. Check it on the LeetCode answer page.</div>'
                             f'{blank_lines(5, "#C9D6E8", 22)}</div>')
        if lp:
            ex_html = "".join(
                f'<div class="lc-example"><b>Input:</b> {esc(i)}<br><b>Output:</b> {esc(o)}'
                + (f'<br><span class="lc-why">{esc(w)}</span>' if w else "") + "</div>"
                for i, o, w in lp["examples"])
            intro = (f'<div class="card lc-card lc-intro"><div class="mini-title">🧩 New pattern: {esc(lp["pattern"])}</div>'
                     f'<div class="footer-note">{esc(lc.get("pattern_intro",""))}</div></div>') if lc.get("new_pattern") else ""
            def step(letter, name, prompt, lines, height=24):
                return (f'<div class="card lc-card"><div class="lc-step"><div class="lc-letter">{letter}</div><div class="lc-step-body">'
                        f'<div class="mini-title">{name}</div><div class="footer-note">{prompt}</div>'
                        f'{blank_lines(lines, "#C9D6E8", height)}</div></div></div>')
            parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("leetcode", f'#{lp["lc"]} ' + lp["title"], f'{lc["level"]} · {lc["position"]} of {lc["total"]}')}
  <div style="margin-bottom:8px;">{chip(lp["pattern"], "#EFF7FF", "#A8C4D8", "#2F5277")}{chip(f'{lc["minutes"]}-min timer', "#FFF8E7", "#F5D38B", "#7D5B21")}</div>
  {intro}
  <div class="card lc-card">
    <div class="lc-statement">{esc(lp["statement"])}</div>
    <div class="lc-ex-grid">{ex_html}</div>
    <div class="footer-note" style="margin-top:6px;"><b>Constraints:</b> {esc(lp["constraints"])}</div>
  </div>
  <div class="card lc-card lc-howto">
    <b>How to work it:</b> start a {lc["minutes"]}-minute timer and work through the six UMPIRE steps below on paper.
    UMPIRE is a problem-solving checklist from CodePath; it keeps you from jumping straight into code.
    <div class="umpire-key">
      <div><span class="lc-letter sm">U</span><b>Understand</b>: say it in your words, find edge cases</div>
      <div><span class="lc-letter sm">M</span><b>Match</b>: which pattern does it look like?</div>
      <div><span class="lc-letter sm">P</span><b>Plan</b>: steps in plain words, before code</div>
      <div><span class="lc-letter sm">I</span><b>Implement</b>: write the code</div>
      <div><span class="lc-letter sm">R</span><b>Review</b>: trace an example by hand to catch bugs</div>
      <div><span class="lc-letter sm">E</span><b>Evaluate</b>: time and space; could it be better?</div>
    </div>
    Stuck when the timer ends? Read <b>one</b> hint on the LeetCode answer page, then try 5 more minutes.
    Submit at leetcode.com/problems/{esc(lp["slug"])} during your online hour.
  </div>
  {step("U", "Understand", "Restate the problem in your own words. Write two edge cases (empty? one item? duplicates? negatives?).", 2 if lc.get("new_pattern") else 3)}
  {step("M", "Match", "Which pattern fits, and what in the problem told you?", 2)}
  <div style="flex:1"></div>
</div></div>
""")
            parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("leetcode", f'#{lp["lc"]} ' + lp["title"], "write it out")}
  {step("P", "Plan", "Write the steps in plain English or pseudocode before any real code.", 3, 22)}
  {step("I", "Implement", "Write the code by hand, in Python.", 10, 22)}
    {step("R", "Review", "Trace Example 1 through your code line by line. Did you get the expected output?", 2)}
    {step("E", "Evaluate", "Time: ________ &nbsp; Space: ________ &nbsp; Could it be faster, or use less memory?", 1)}
  {reviews_html}
  <div style="flex:1"></div>
</div></div>
""")
        else:
            parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("leetcode", "Level complete", lc["level"])}
  <div class="card lc-card"><div class="mini-title">🎉 You've finished all {lc["total"]} {esc(lc["level"])} problems.</div>
    <div class="footer-note">Tell Claude you're ready to move up a level. Until then, keep re-solving from memory.</div></div>
  {reviews_html}
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:chores-->")
    # ── PAGE 3: Chores ────────────────────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  {section_title("home quest", chores["title"], "quick wins")}
  <div class="card">
    <div class="mini-title">Today's tidy-up trail</div>
    {chores_weekly_html}
    {chores_daily_html}
  </div>

  <div class="split">
    <div class="card">
      <div class="mini-title">Speed-run challenge</div>
      <div class="footer-note">{esc(chores["speed_run"])}</div>
      <div class="medium-blank" style="margin-top:10px;"><div class="mini-note">Color here when you beat it.</div></div>
    </div>
    <div class="card">
      <div class="mini-title">Reward snack bar</div>
      <div>{reward_chips}</div>
      <div class="medium-blank" style="margin-top:10px;"><div class="mini-note">Sticker zone 🎉</div></div>
    </div>
  </div>

  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:body-->")
    # ── PAGE 4: Body + Parking ────────────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  {section_title("body", "Move + Fuel", "exercise & dinner")}

  <div class="exercise-card">
    <div class="mini-title">💪 Exercise today</div>
    <div class="footer-note">{esc(exercise_suggestion)}</div>
    {checkbox_item("Moved my body today","Dog walks count too","#A8C4D8","#EFF7FF")}
  </div>

  <div class="dinner-card">
    <div class="mini-title">🍳 Dinner tonight — cooking for you + partner</div>
    <div class="footer-note">{esc(dinner_suggestion)}</div>
    {checkbox_item("Cooked a proper meal tonight","Protein + veg — even a simple version counts","#F4C87A","#FFFBF0")}
    {checkbox_item("Didn't skip a meal today","","#F4C87A","#FFFBF0")}
  </div>

  {admin_html}
  {parking_html}
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:offline-->")
    # ── PAGE 5: Offline today ─────────────────────────────────────────────────
    offline = wb.get("_offline") or {}
    if offline:
        if offline.get("is_online_day"):
            sub = "Your batched list is below. Close the laptop when it's done."
        elif offline.get("mode") == "weekly_day":
            sub = "Write anything you need online on the list. It waits for your internet day."
        else:
            sub = "Outside that hour, write it on the list instead of looking it up."
        online_items = "".join(checkbox_item(i, "", "#8FB8DE", "#F2F8FF") for i in offline.get("online_list", []))
        toolkit_chips = "".join(chip(t, "#F2F8FF", "#8FB8DE", "#2F5277") for t in offline.get("toolkit", []))
        parts.append(f"""
<div class="page"><div class="frame">
  {section_title("offline", "Offline Today", "phone down")}

  <div class="offline-card">
    <div class="offline-headline">🔌 {esc(offline.get("headline", ""))}</div>
    <div class="footer-note">{esc(sub)}</div>
  </div>

  <div class="offline-card">
    <div class="mini-title">📝 Online list</div>
    <div class="footer-note" style="color:#888;margin-bottom:8px;">Carried over from online_list.txt, plus room for what comes up today.</div>
    {online_items}
    {blank_lines(6, "#B9D3EC")}
  </div>

  <div class="offline-card">
    <div class="mini-title">🧰 Reach for these instead</div>
    <div>{toolkit_chips}</div>
  </div>

  <div class="offline-card">
    <div class="mini-title">🌙 End-of-day check-in</div>
    {checkbox_item("Stayed offline outside my plan", "Exceptions don't count against you", "#8FB8DE", "#F2F8FF")}
    <div class="footer-note" style="margin:8px 0 4px;">Minutes online today: ________</div>
    <div class="footer-note" style="margin:8px 0 4px;">When I wanted the internet, I did this instead:</div>
    {blank_lines(2, "#B9D3EC")}
  </div>
  <div style="flex:1"></div>
</div></div>
""")



    parts.append("<!--SECTION:reading-->")
    # ── Reading: today's saved Substack article + reflection ─────────────────
    art = wb.get("_reading") or {}
    if art:
        byline_bits = []
        for x in (art.get("author"), art.get("publication"), art.get("published")):
            if x and x not in byline_bits:
                byline_bits.append(x)
        byline = " · ".join(byline_bits)
        tag = {"h": "h3", "quote": "blockquote", "li": "li"}
        body_html = ""
        for blk in art.get("blocks", []):
            t = tag.get(blk.get("type"), "p")
            body_html += f'<{t} class="article-{t}">{"• " if t == "li" else ""}{esc(blk.get("text",""))}</{t}>'
        paywall = ('<div class="footer-note" style="color:#a66;">This post is paywalled, so only the free preview downloaded.</div>'
                   if art.get("paywalled") else "")
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("reading", "Today's Read", f'{art.get("words", 0)} words')}
  <div class="article-title">{esc(art.get("title",""))}</div>
  <div class="article-byline">{esc(byline)}</div>
  {paywall}
  <div class="card prompt-card">
    <div class="mini-title">Before you read</div>
    <div class="footer-note">From the title alone: what do you already think about this topic, and what do you expect the author to argue?</div>
    {blank_lines(2)}
    <div class="footer-note" style="margin-top:6px;">While you read, mark it up: <b>underline</b> the main claims, <b>?</b> where you doubt something, <b>!</b> where you're surprised.</div>
  </div>
  <div class="article-body">{body_html}</div>
  <div style="flex:1"></div>
</div></div>
""")
        lens_colors = {"In your own words": ("#EFF7FF", "#A8C4D8", "#2F5277"),
                       "Assumptions": ("#FFF8E7", "#F5D38B", "#7D5B21"),
                       "Push back": ("#FFF0F5", "#F2B5CF", "#7B4C62"),
                       "Go deeper": ("#F7F4FF", "#C8B6FF", "#5D4D85"),
                       "Connect": ("#EFFFF7", "#9DD9D2", "#2B665E")}
        def prompt_card(n, pr, lines):
            bg, border, fg = lens_colors.get(pr["lens"], ("#F9F9F9", "#C8C8C8", "#555"))
            return (f'<div class="card prompt-card"><div>{chip(pr["lens"], bg, border, fg)}</div>'
                    f'<div class="prompt-text">{n}. {esc(pr["text"])}</div>'
                    f'<div class="prompt-follow">{esc(pr.get("follow",""))}</div>{blank_lines(lines)}</div>')
        prs = art.get("prompts", [])
        # Long model-written prompts take more room; drop a writing line so the
        # first three still fit on one sheet.
        first_lines = 4 if sum(len(pr["text"]) for pr in prs[:3]) <= 420 else 3
        first = "".join(prompt_card(n, pr, first_lines) for n, pr in enumerate(prs[:3], 1))
        second = "".join(prompt_card(n, pr, 6) for n, pr in enumerate(prs[3:], 4))
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("reading", "Write About It", "think it through")}
  <div class="footer-note" style="margin-bottom:10px;">On: {esc(art.get("title",""))}. Write in full sentences. Quote the article where you can.</div>
  {first}
  <div style="flex:1"></div>
</div></div>
""")
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("reading", "Write About It", "keep going")}
  {second}
  <div class="card prompt-card">
    <div class="mini-title">Questions to look up in your online time</div>
    {blank_lines(3)}
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:weather-->")
    # ── Weather page ──────────────────────────────────────────────────────────
    wx_avail   = weather_data.get("available", False)
    wx_today   = weather_data.get("today", {})
    wx_tonight = weather_data.get("tonight", {})
    wx_tomorrow= weather_data.get("tomorrow", {})
    wx_hourly  = weather_data.get("hourly", [])
    wx_alerts  = weather_data.get("alerts", [])
    wx_error   = weather_data.get("error")

    if wx_avail and wx_today:
        wx_emoji  = weather_emoji(wx_today.get("short_desc", ""))
        wx_temp   = wx_today.get("temp_f", "–")
        wx_desc   = wx_today.get("short_desc", "")
        wx_wind   = f'{wx_today.get("wind_speed","")} {wx_today.get("wind_dir","")}'.strip()
        wx_precip = wx_today.get("precip_pct", 0)
        wx_detail = wx_today.get("detail", "")

        tn_emoji  = weather_emoji(wx_tonight.get("short_desc",""))
        tn_temp   = wx_tonight.get("temp_f","–")
        tn_desc   = wx_tonight.get("short_desc","")
        tn_precip = wx_tonight.get("precip_pct",0)

        tm_emoji  = weather_emoji(wx_tomorrow.get("short_desc",""))
        tm_temp   = wx_tomorrow.get("temp_f","–")
        tm_desc   = wx_tomorrow.get("short_desc","")

        # Hourly strip
        hourly_html = ""
        for h in wx_hourly[:6]:
            p = h.get("precip_pct", 0)
            precip_str = f'{p}%' if p else "—"
            hourly_html += f'''<div class="weather-hour">
              <div class="weather-hour-time">{esc(h.get("time",""))}</div>
              <div class="weather-hour-temp">{h.get("temp_f","–")}°</div>
              <div class="weather-hour-precip">💧{precip_str}</div>
            </div>'''

        # Alerts
        alerts_html = ""
        for a in wx_alerts:
            alerts_html += f'''<div class="weather-alert">
              <div class="weather-alert-title">⚠️ {esc(a.get("event",""))}</div>
              <div class="weather-alert-sub">{esc(a.get("headline",""))}</div>
            </div>'''

        # Outfit suggestion based on temp + conditions
        temp_val = wx_temp if isinstance(wx_temp, (int,float)) else 60
        rain_likely = wx_precip and wx_precip >= 40
        if temp_val >= 75:
            outfit = "Light layers — it's warm out. Shorts/tee weather."
        elif temp_val >= 60:
            outfit = "Light jacket or long sleeves. Comfortable walking weather."
        elif temp_val >= 45:
            outfit = "Jacket needed. Consider a mid-layer."
        elif temp_val >= 32:
            outfit = "Winter coat, hat, gloves. Cold out there."
        else:
            outfit = "Bundle up — below freezing. Heavy coat, layers, warm socks."
        if rain_likely:
            outfit += " Bring an umbrella or rain jacket — good chance of rain."

        parts.append(f"""
<div class="page"><div class="frame">
  {section_title("outside", "Weather — Amherst, MA", "today\'s forecast")}

  {alerts_html}

  <div class="weather-card">
    <div class="weather-main">
      <div class="weather-emoji">{wx_emoji}</div>
      <div>
        <div class="weather-temp">{wx_temp}°F</div>
        <div class="weather-desc">{esc(wx_desc)}</div>
        <div class="weather-wind">💨 {esc(wx_wind)}</div>
      </div>
    </div>

    <div class="weather-grid">
      <div class="weather-block">
        <div class="weather-block-label">Rain chance</div>
        <div class="weather-block-val">{wx_precip}%</div>
      </div>
      <div class="weather-block">
        <div class="weather-block-label">Tonight</div>
        <div class="weather-block-val">{tn_emoji} {tn_temp}°F</div>
        <div class="weather-block-sub">{esc(tn_desc)}</div>
      </div>
      <div class="weather-block">
        <div class="weather-block-label">Tomorrow</div>
        <div class="weather-block-val">{tm_emoji} {tm_temp}°F</div>
        <div class="weather-block-sub">{esc(tm_desc)}</div>
      </div>
      <div class="weather-block">
        <div class="weather-block-label">Tonight rain</div>
        <div class="weather-block-val">{tn_precip}%</div>
      </div>
    </div>

    <div class="mini-title" style="margin-bottom:6px;">Next 10 hours</div>
    <div class="weather-hourly">{hourly_html}</div>
  </div>

  <div class="card" style="background:#EFF7FF;border-color:#90BFDF;">
    <div class="mini-title">👕 What to wear today</div>
    <div class="footer-note">{esc(outfit)}</div>
  </div>

  <div class="card" style="background:#EFF7FF;border-color:#90BFDF;">
    <div class="mini-title">📋 Full forecast</div>
    <div class="footer-note">{esc(wx_detail)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    else:
        err_msg = f"Could not fetch weather: {wx_error}" if wx_error else "Weather unavailable — check your connection."
        parts.append(f"""
<div class="page"><div class="frame">
  {section_title("outside", "Weather — Amherst, MA", "today\'s forecast")}
  <div class="card" style="text-align:center;padding:30px 20px;">
    <div style="font-size:36px;margin-bottom:12px;">🌡️</div>
    <div class="footer-note">{esc(err_msg)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:moon-->")
    # ── PAGE 4: Moon ──────────────────────────────────────────────────────────────
    def _when(days):
        n = round(days)
        return "today" if n <= 0 else "tomorrow" if n == 1 else f"in {n} days"
    moon_phase_name  = moon_data.get("phase_name", "Unknown Phase")
    moon_emoji       = moon_data.get("emoji", "🌕")
    moon_illum       = moon_data.get("illumination_pct", 0)
    moon_days_full   = moon_data.get("days_to_full", 0)
    moon_days_new    = moon_data.get("days_to_new", 0)
    moon_is_full     = moon_data.get("is_full", False)
    moon_is_new      = moon_data.get("is_new", False)
    moon_soon        = moon_data.get("full_moon_soon", False)
    moon_new_soon    = moon_data.get("new_moon_soon", False)
    moon_full_label  = moon_data.get("full_moon_label", "")
    moon_full_lore   = moon_data.get("full_moon_lore", "")
    moon_new_lore    = moon_data.get("new_moon_lore", "")
    moon_full_date   = moon_data.get("full_moon_date_str", "")
    moon_new_date    = moon_data.get("new_moon_date_str", "")
    moon_keywords    = moon_data.get("keywords", "")

    mp_meaning   = moon_page.get("phase_meaning", "")
    mp_spiritual = moon_page.get("spiritual_note", "")
    mp_reflect_q = moon_page.get("reflection_q", "")
    mp_ritual    = moon_page.get("ritual_suggestion", "")
    mp_full_msg  = moon_page.get("full_moon_message", "")
    mp_new_msg   = moon_page.get("new_moon_message", "")

    # Progress bar (moon illumination)
    bar_filled = int(moon_illum / 5)  # 20 segments
    bar_empty  = 20 - bar_filled
    moon_bar   = "█" * bar_filled + "░" * bar_empty

    full_moon_alert_html = ""
    if moon_is_full:
        full_moon_alert_html = f'''
        <div class="full-moon-alert">
          <div class="full-moon-alert-title">🌕 Tonight is the {esc(moon_data.get("full_moon_name","Full Moon"))}!</div>
          <div class="full-moon-alert-text">{esc(moon_full_lore)}</div>
          {f'<div class="full-moon-alert-text" style="margin-top:8px;font-style:italic;">{esc(mp_full_msg)}</div>' if mp_full_msg else ""}
        </div>'''
    elif moon_soon:
        full_moon_alert_html = f'''
        <div class="full-moon-alert">
          <div class="full-moon-alert-title">🌔 {esc(moon_data.get("full_moon_name","Full Moon"))} {_when(moon_days_full)} — {esc(moon_full_date)}</div>
          <div class="full-moon-alert-text">{esc(moon_full_lore)}</div>
          {f'<div class="full-moon-alert-text" style="margin-top:8px;font-style:italic;">{esc(mp_full_msg)}</div>' if mp_full_msg else ""}
        </div>'''

    new_moon_alert_html = ""
    if moon_is_new:
        new_moon_alert_html = f'''
        <div class="new-moon-alert">
          <div class="new-moon-alert-title">🌑 Tonight is the New Moon — set your intentions</div>
          <div class="new-moon-alert-text">{esc(moon_new_lore)}</div>
          {f'<div class="new-moon-alert-text" style="margin-top:8px;font-style:italic;">{esc(mp_new_msg)}</div>' if mp_new_msg and moon_new_lore[:40] not in mp_new_msg else ""}
        </div>'''
    elif moon_new_soon:
        new_moon_alert_html = f'''
        <div class="new-moon-alert">
          <div class="new-moon-alert-title">🌘 New Moon {_when(moon_days_new)} — {esc(moon_new_date)}</div>
          <div class="new-moon-alert-text">{esc(moon_new_lore)}</div>
          {f'<div class="new-moon-alert-text" style="margin-top:8px;font-style:italic;">{esc(mp_new_msg)}</div>' if mp_new_msg and moon_new_lore[:40] not in mp_new_msg else ""}
        </div>'''

    next_full_note = ""
    if not moon_is_full and not moon_soon and not moon_is_new and not moon_new_soon:
        days_note_parts = []
        days_note_parts.append(f'Next full moon: <strong>{esc(moon_full_label)}</strong> — {moon_days_full:.0f} days away')
        days_note_parts.append(f'Next new moon: <strong>{esc(moon_new_date)}</strong> — {_when(moon_days_new)}')
        next_full_note = f'<div class="moon-text" style="margin-top:8px;color:#444;">{" · ".join(days_note_parts)}</div>'

    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("tonight\'s sky", "Moon phase", "celestial check-in")}

  <div class="moon-card">
    <span class="moon-emoji">{moon_emoji}</span>
    <div class="moon-phase-name">{esc(moon_phase_name)}</div>
    <div class="moon-illumination">{moon_bar} {moon_illum}% illuminated · Day {moon_data.get("phase_day",0):.1f} of 29.5</div>

    <div class="moon-section-label">Energy &amp; meaning</div>
    <div class="moon-text">{esc(mp_meaning)}</div>

    <div class="moon-section-label">Keywords</div>
    <div class="moon-text" style="font-style:italic;">{esc(moon_keywords)}</div>

    <div class="moon-section-label">A thought</div>
    <div class="moon-text">{esc(mp_spiritual)}</div>

    <div class="moon-ritual">
      <div class="moon-section-label">Tonight\'s ritual</div>
      <div class="moon-ritual-text">{esc(mp_ritual)}</div>
    </div>

    {full_moon_alert_html}
    {new_moon_alert_html}
    {next_full_note}
  </div>

  <div class="card">
    <div class="moon-reflection">
      <div class="moon-reflection-q">✦ {esc(mp_reflect_q)}</div>
    </div>
    <div style="margin-top:6px;">
      {''.join('<div class="moon-write-line"></div>' for _ in range(5))}
    </div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")


    parts.append("<!--SECTION:cycle-->")
    # ── Cycle page (inserted after moon page) ────────────────────────────────
    cycle_avail      = cycle_data.get("available", False)
    cycle_phase      = cycle_data.get("phase", {})
    cycle_day        = cycle_data.get("cycle_day", 1)
    cycle_avg        = cycle_data.get("cycle_length_avg", CYCLE_LENGTH_AVG)
    cycle_phase_key  = cycle_data.get("phase_key", "")
    days_in_phase    = cycle_data.get("days_in_phase", 1)
    days_to_period   = cycle_data.get("days_until_next_period", 0)
    days_to_ovul     = cycle_data.get("days_until_ovulation", 0)
    period_soon      = cycle_data.get("period_coming_soon", False)
    ovul_soon        = cycle_data.get("ovulation_soon", False)

    if cycle_avail and cycle_phase:
        p_name    = cycle_phase.get("name", "Unknown")
        p_emoji   = cycle_phase.get("emoji", "🌀")
        p_accent  = cycle_phase.get("accent", "#c8b8e8")
        p_energy  = cycle_phase.get("energy", "")
        p_kw      = cycle_phase.get("keywords", "")
        p_desc    = cycle_phase.get("description", "")
        p_tasks   = cycle_phase.get("task_tone", "")
        p_ex      = cycle_phase.get("exercise", "")
        p_food    = cycle_phase.get("foods", "")
        p_emo     = cycle_phase.get("emotional", "")
        p_pms     = cycle_phase.get("pms_warning", False)

        # Cycle progress bar — 4 segments: menstrual / follicular / ovulatory / luteal
        seg_keys   = ["menstrual", "follicular", "ovulatory", "luteal"]
        active_seg = "luteal" if cycle_phase_key.startswith("luteal") else cycle_phase_key
        seg_labels = ["Menstrual", "Follicular", "Ovulatory", "Luteal"]
        bar_html = "".join(
            f'<div class="cycle-bar-seg" style="background:{p_accent};border-color:{p_accent};" title="{l}"></div>'
            if k == active_seg else f'<div class="cycle-bar-seg" title="{l}"></div>'
            for k, l in zip(seg_keys, seg_labels))

        # Alerts
        alerts_html = ""
        if period_soon:
            alerts_html += f'''<div class="cycle-alert" style="border-color:#C8697A;">
              <div class="cycle-alert-title">🌹 Period arriving {_when(days_to_period)}</div>
              <div class="cycle-alert-text">Stock up on comfort supplies. Be extra gentle with your expectations over the next few days.</div>
            </div>'''
        if ovul_soon:
            alerts_html += f'''<div class="cycle-alert" style="border-color:#E0A800;">
              <div class="cycle-alert-title">☀️ Ovulation window {_when(days_to_ovul)}</div>
              <div class="cycle-alert-text">Your peak energy window is coming. Plan your most important tasks or social moments for then.</div>
            </div>'''
        if p_pms:
            alerts_html += f'''<div class="cycle-alert" style="border-color:#9B8EC4;">
              <div class="cycle-alert-title">💜 PMS territory — be kind to yourself</div>
              <div class="cycle-alert-text">What you're feeling is real and physiological. Don't make big decisions today. Rest is productive right now.</div>
            </div>'''

        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("inner season", "Cycle phase", "body wisdom")}

  <div class="cycle-card" style="border-color:{p_accent};">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <span style="font-size:36px;">{p_emoji}</span>
      <div>
        <div class="cycle-phase-name">{esc(p_name)}</div>
        <div class="cycle-day-label">Cycle day {cycle_day} of ~{cycle_avg} · {esc(cycle_phase.get("days",""))}</div>
      </div>
    </div>

    <div class="cycle-bar-wrap">{bar_html}</div>
    <div style="font-size:11px;color:#555;font-family:monospace;margin-bottom:12px;">Menstrual · Follicular · Ovulatory · Luteal</div>

    <div class="cycle-section-label">Energy &amp; phase</div>
    <div class="cycle-text">{esc(p_energy)} — {esc(p_kw)}</div>

    <div class="cycle-section-label">What this phase means</div>
    <div class="cycle-text">{esc(p_desc)}</div>

    <div class="cycle-row">
      <div class="cycle-block">
        <div class="cycle-block-title">Task tone today</div>
        <div class="cycle-block-text">{esc(p_tasks)}</div>
      </div>
      <div class="cycle-block">
        <div class="cycle-block-title">Exercise</div>
        <div class="cycle-block-text">{esc(p_ex)}</div>
      </div>
    </div>

    <div class="cycle-block" style="margin-bottom:10px;">
      <div class="cycle-block-title">Food &amp; nourishment</div>
      <div class="cycle-block-text">{esc(p_food)}</div>
    </div>

    <div class="cycle-block" style="margin-bottom:10px;">
      <div class="cycle-block-title">🍵 Tea blend for today</div>
      <div class="cycle-block-text" style="font-weight:800;margin-bottom:4px;">{esc(cycle_phase.get("tea",{}).get("blend",""))}</div>
      <div class="cycle-block-text">{esc(cycle_phase.get("tea",{}).get("why",""))}</div>
      <div class="cycle-block-text" style="font-style:italic;color:#444;margin-top:4px;">💡 {esc(cycle_phase.get("tea",{}).get("notes",""))}</div>
    </div>

    {alerts_html}

    <div class="cycle-emotional">
      <div class="cycle-emotional-q">💬 {esc(p_emo)}</div>
      {''.join('<div class="cycle-write-line"></div>' for _ in range(2))}
    </div>

    <div class="cycle-text" style="margin:10px 0 0;">
      <strong>Coming up:</strong>
      {'🌹 Period in ' + str(days_to_period) + ' days' if days_to_period > 0 else '🌹 Period today or very soon'}{' · ☀️ Ovulation window in ' + str(days_to_ovul) + ' days (day ' + str(OVULATION_DAY) + '±2)' if days_to_ovul > 0 else ""}
    </div>
    <div class="cycle-day-label" style="margin:4px 0 0;font-size:10.5px;">Last period logged: {esc(cycle_data.get("last_period_start","unknown"))} · update with --log-period</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    else:
        # No cycle data logged yet — prompt user to set it up
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("inner season", "Cycle phase", "body wisdom")}
  <div class="card" style="text-align:center;padding:30px 20px;">
    <div style="font-size:36px;margin-bottom:12px;">🌹</div>
    <div class="mini-title" style="color:#5d4085;">Set up cycle tracking</div>
    <div class="footer-note" style="margin-bottom:16px;">Run this command when your next period starts to activate this section:</div>
    <div style="background:#fff;border:1.5px solid #999;color:#222;font-family:monospace;font-size:13px;padding:12px 16px;border-radius:10px;display:inline-block;">python3 dailyWorkbookLocal.py --log-period</div>
    <div class="footer-note" style="margin-top:12px;color:#aaa;">You can also log a past date: --log-period 2026-05-01</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")


    parts.append("<!--SECTION:chinese-->")
    # ── PAGES 5-7: Chinese ────────────────────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  {section_title("Chinese lesson", chinese_lesson["title"], "learn & review")}
  <div class="card">
    <div class="mini-title">Lesson intro</div>
    <div class="footer-note">{esc(chinese_lesson["lesson_intro"])}</div>
  </div>
  <div class="card">
    <div class="mini-title">{esc(chinese_lesson["new_words_banner"])}</div>
    <div class="vocab-grid">{lesson_vocab_html}</div>
  </div>
  <div class="card">
    <div class="mini-title">{esc(chinese_lesson["review_banner"])}</div>
    <div class="vocab-grid">{review_vocab_html}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    # Writing practice: stroke order + 田字格 squares for each new character
    seen_chars, practice_cards = [], []
    for v in chinese_lesson.get("vocab", []):
        for ch in v.get("char", ""):
            if "\u4e00" <= ch <= "\u9fff" and ch not in seen_chars:
                seen_chars.append(ch)
    for ch in seen_chars[:6]:
        word = WORD_INDEX.get(ch) or next((w for w in chinese_lesson.get("vocab", []) if ch in w.get("char", "")), {})
        in_word = "" if word.get("char") == ch else f' · in {esc(word.get("char",""))}'
        n = hanzi.stroke_count(ch) if hanzi else None
        strip = hanzi.stroke_order(ch) if hanzi else ""
        boxes1 = "".join(hanzi.box(ch, 0.7, "trace") for _ in range(3)) + "".join(hanzi.box(None, 0.7) for _ in range(6)) if hanzi else ""
        boxes2 = "".join(hanzi.box(None, 0.7) for _ in range(9)) if hanzi else ""
        practice_cards.append(f'''
  <div class="card hz-card">
    <div class="hz-head">
      {hanzi.box(ch, 0.95, "model") if hanzi else f'<div class="vocab-char">{esc(ch)}</div>'}
      <div>
        <div class="hz-title">{esc(ch)} <span class="hz-pinyin">{esc(word.get("pinyin",""))}</span></div>
        <div class="footer-note">{esc(word.get("meaning",""))}{in_word}{f" · {n} strokes" if n else ""}</div>
        <div class="mini-note">Stroke order: the red stroke is the new one; the circle shows where the pen starts.</div>
      </div>
    </div>
    {strip}
    <div class="tzg-row">{boxes1}</div>
    <div class="tzg-row">{boxes2}</div>
    <div class="tzg-row">{boxes2}</div>
  </div>''')
    if practice_cards:
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("Chinese writing", "Write It: 写字", "stroke by stroke")}
  <div class="footer-note" style="margin-bottom:8px;">Trace the gray characters first, then write on your own. Say the sound out loud each time you write it.</div>
  {"".join(practice_cards)}
  <div style="flex:1"></div>
</div></div>
""")

    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("Chinese lesson", "Mini dialogue", "read it aloud")}
  <div class="card">
    {dialogue_html}
  </div>
  <div class="card">
    <div class="mini-title">Tiny game</div>
    <div class="footer-note">{esc(chinese_lesson["tiny_game"])}</div>
    <div class="ms-grid">{ms_grid(2)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("reference page", chinese_ref["title"], "cheat sheet")}
  <div class="card">
    <div class="mini-title">How to use this page</div>
    <div class="footer-note">{esc(chinese_ref["reference_intro"])}</div>
  </div>
  <div class="card">
    <div class="mini-title">{esc(chinese_ref["word_bank_title"])}</div>
    <div class="vocab-grid">{helper_html}</div>
  </div>
  <div class="card">
    <div class="mini-title">Grammar note</div>
    <div class="footer-note">{esc(chinese_ref["grammar_note"])}</div>
  </div>
  <div class="card">
    <div class="mini-title">{esc(chinese_ref["reader_translation_title"])}</div>
    <div class="gloss-grid">{gloss_html}</div>
  </div>
  <div class="card">
    <div class="mini-title">Review quiz</div>
    {"".join(checkbox_item(q,"","#9DD9D2","#F3FFFD") for q in chinese_ref["review_quiz_prompts"])}
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("graded reader", chinese_reader["title"], "read slowly")}
  <div class="card">
    <div class="mini-title">{esc(chinese_reader["story_title"])}</div>
    <div class="footer-note">{esc(chinese_reader["reader_intro"])}</div>
  </div>
  <div class="card">{reader_html}</div>
  <div class="card">
    <div class="mini-title">Comprehension questions</div>
    {"".join(checkbox_item(q,"","#BDE0FE","#F8FBFF") for q in chinese_reader["comprehension_questions"][:3])}
  </div>
  <div class="card">
    <div class="mini-title">Copywork 抄写</div>
    <div class="footer-note">{esc(chinese_reader["copywork_prompt"])} One character per square, punctuation gets its own square.</div>
    <div class="ms-grid">{ms_grid(3)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    # ── Italian: today's quaderno day (italian.py) ───────────────────────────
    it_pages = {}
    if italian and wb.get("_italian"):
        try:
            it_pages = italian.render(wb["_italian"])
        except Exception as e:
            print(f"⚠ Italian pages skipped: {e}")
    if it_pages:
        parts.append("<!--SECTION:italian-->")
        parts.append(it_pages.get("css", ""))
        parts.extend(it_pages.get("lesson_pages", []))
        if it_pages.get("answer_pages"):
            parts.append("<!--SECTION:it_answers-->")
            parts.append(it_pages.get("css", ""))
            parts.extend(it_pages["answer_pages"])

    parts.append("<!--SECTION:evening-->")
    # ── PAGE 8: Evening + Reflection ─────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  {section_title("evening", "Wind-down routine", "end of day")}

  <div class="evening-dog">
    <div class="mini-title">🌙 Evening dog care — non-negotiable</div>
    {checkbox_item("Evening walk","Good boy deserves it","#C8A0E0","#F9F2FF")}
    {checkbox_item("Give evening meds with food","Don't skip","#C8A0E0","#F9F2FF")}
    {checkbox_item("Fresh water before bed","","#C8A0E0","#F9F2FF")}
  </div>

  {section_title("evening reflection", reflection["title"], "close the loop")}
  <div class="card">
    <div class="mini-title">Reflection questions</div>
    {"".join(checkbox_item(q,"","#F2B5CF","#FFF8FB") for q in reflection["questions"])}
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append(f"""
<div class="page"><div class="frame">
  <div class="split">
    <div class="card">
      <div class="mini-title">Tiny wins</div>
      <div class="footer-note">{esc(reflection["wins_prompt"])}</div>
      <div style="margin-top:10px;">{blank_lines(5)}</div>
    </div>
    <div class="card">
      <div class="mini-title">Tomorrow crumbs</div>
      {"".join(checkbox_item(s,"","#C8B6FF","#F8F6FF") for s in reflection["tomorrow_steps"])}
    </div>
  </div>
  <div class="card">
    <div class="mini-title">Gratitude mini-menu</div>
    <div>{gratitude_chips}</div>
    <div style="margin-top:10px;">{blank_lines(5)}</div>
  </div>
  <div class="card">
    <div class="mini-title">Bedtime note</div>
    <div class="footer-note">{esc(reflection["bedtime_note"])}</div>
    <div style="margin-top:10px;">{blank_lines(4)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:back-->")
    # ── PAGE 9: Back ──────────────────────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  {section_title("back page","Tiny Rewards Receipt","done enough")}
  <div class="hero-card">
    <div class="mini-title">Closing note</div>
    <div class="footer-note">{esc(back["closing_note"])}</div>
  </div>
  <div class="card">
    <div class="mini-title">Tiny rewards</div>
    <div>{tiny_rewards}</div>
  </div>
  <div class="card">
    <div class="mini-title">Tomorrow preview</div>
    <div class="footer-note">{esc(back["tomorrow_preview"])}</div>
    <div style="margin-top:10px;">{blank_lines(8)}</div>
  </div>
  <div class="card">
    <div class="mini-title">Final sticker zone</div>
    <div class="sticker-grid">{sticker_grid(["showed up","learned","made","rested","tidied","studied","wrote","sparkled"])}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:lc_answers-->")
    # ── LeetCode hints + solution (near the back, so it's not in view) ───────
    if lc and (lc.get("problem") or lc.get("reviews")):
        lp = lc.get("problem")
        sol_html = ""
        if lp:
            hints = "".join(f'<div class="lc-hint"><b>Hint {n}.</b> {esc(h)}</div>' for n, h in enumerate(lp["hints"], 1))
            approach = "".join(f"<li>{esc(a)}</li>" for a in lp["approach"])
            sol_html = f"""
  <div class="card lc-card">
    <div class="mini-title">#{lp["lc"]} {esc(lp["title"])}: hints</div>
    <div class="footer-note" style="margin-bottom:6px;">Cover this page and reveal one hint at a time. Try again after each one.</div>
    {hints}
  </div>
  <div class="card lc-card">
    <div class="mini-title">Solution</div>
    <ol class="algo-steps">{approach}</ol>
    <pre class="lc-code">{esc(lp["solution"])}</pre>
    <div class="footer-note"><b>Time:</b> {esc(lp["time"])} &nbsp; <b>Space:</b> {esc(lp["space"])}</div>
    <div class="algo-why" style="margin-top:6px;"><b>Pattern note.</b> {esc(lp["takeaway"])} Copy this into your own words in your pattern notebook.</div>
  </div>"""
        rev_html = "".join(
            f'<div class="card lc-card"><div class="mini-title">Re-solve check: #{r["lc"]} {esc(r["title"])}</div>'
            f'<pre class="lc-code">{esc(r["solution"])}</pre></div>' for r in lc.get("reviews", []))
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("answer key", "LeetCode: Hints & Solutions", "only when stuck")}
  {sol_html}
  {rev_html}
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:cs311_answers-->")
    # ── Answer key (last page, so it's easy to fold back) ────────────────────
    algo_qs = ([("Course order", q) for q in (algo.get("course_order") or [])]
               + ([("Random pick", algo["random"])] if algo.get("random") else [])
               + [("Review", q) for q in (algo.get("review") or [])])
    algo_qs = [(label, q) for label, q in algo_qs if q.get("practice")]
    if algo_qs:
        answers_html = "".join(
            f'<div class="card algo-card"><div class="mini-title">{label}: {esc(q.get("topic",""))} '
            f'Q{q.get("question_number","")}</div>'
            f'<div class="algo-problem" style="color:#888;">{esc(q["practice"].get("problem",""))}</div>'
            f'<div class="algo-why"><b>Answer.</b> {esc(q["practice"].get("answer",""))}</div></div>'
            for label, q in algo_qs)
        parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("answer key", "CS311 Answers", "check yourself")}
  {answers_html}
  <div class="card">
    <div class="mini-title">Checkpoint</div>
    <div class="footer-note">What clicked today, what did you miss, and what do you want to ask about in lecture?</div>
    <div style="margin-top:10px;">{blank_lines(3)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    parts.append("<!--SECTION:end-->")
    parts.append("</body></html>")
    return "\n".join(_reorder_sections(parts))


# Order the printed sections. Gentle, outward-looking pages (weather, moon,
# cycle) come before the brain-heavy study pages; answer keys stay at the back.
SECTION_ORDER = [
    "cover", "weather", "moon", "cycle",
    "cs311", "leetcode",
    "chores", "body", "offline",
    "reading", "chinese", "italian",
    "evening", "back",
    "lc_answers", "cs311_answers", "it_answers",
]


def _reorder_sections(parts: list[str]) -> list[str]:
    """Split build_html's parts at <!--SECTION:name--> tags and reassemble them in SECTION_ORDER."""
    import re
    head, sections, current = [], {}, None
    for part in parts:
        m = re.fullmatch(r"<!--SECTION:(\w+)-->", part)
        if m:
            current = m.group(1)
            sections.setdefault(current, [])
            continue
        (sections[current] if current else head).append(part)
    tail = sections.pop("end", [])
    ordered = [n for n in SECTION_ORDER if n in sections] + [n for n in sections if n not in SECTION_ORDER]
    return head + [x for n in ordered for x in sections[n]] + tail


# ── Save / export / email ─────────────────────────────────────────────────────

def save_workbook_html(wb: dict) -> Path:
    ensure_output_dir()
    out_path = OUTPUT_DIR / f"daily-workbook-{today_stamp()}.html"
    out_path.write_text(build_html(normalize(wb)), encoding="utf-8")
    return out_path

def find_browser_binary() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        shutil.which("google-chrome"), shutil.which("chromium"),
        shutil.which("chromium-browser"), shutil.which("brave"),
    ]
    return next((str(c) for c in candidates if c and Path(c).exists()), None)

def export_pdf(html_path: Path) -> Path | None:
    browser = find_browser_binary()
    if not browser:
        print("⚠ No Chrome/Chromium/Brave found. Skipping PDF export.")
        return None
    pdf_path = html_path.with_suffix(".pdf")
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
           f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header",
           str(html_path.resolve())]
    try:
        print("⏳ Exporting PDF...")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            print(f"✓ PDF saved: {pdf_path}")
            return pdf_path
        print("⚠ PDF command ran but no file created.")
        return None
    except Exception as e:
        print(f"⚠ PDF export failed: {e}")
        return None

def send_email(subject, body, attachments):
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_APP_PASSWORD not set. export GMAIL_APP_PASSWORD='your_16_char_password'")
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL; msg["To"] = RECIPIENT_EMAIL; msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments:
        if not path or not path.exists(): continue
        data = path.read_bytes()
        if path.suffix.lower() == ".pdf":  mt, ms = "application", "pdf"
        elif path.suffix.lower() == ".html": mt, ms = "text", "html"
        else: mt, ms = "application", "octet-stream"
        msg.add_attachment(data, maintype=mt, subtype=ms, filename=path.name)
    print("⏳ Sending email...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)
    print(f"✓ Email sent to {RECIPIENT_EMAIL}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Handle --log-period CLI flag
    if "--log-period" in sys.argv:
        idx = sys.argv.index("--log-period")
        date_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) and not sys.argv[idx+1].startswith("-") else None
        log_period_start(date_arg)
        return

    # --date YYYY-MM-DD builds the workbook for that day (used by print_batch.py)
    global WORKBOOK_DATE
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        try:
            WORKBOOK_DATE = datetime.strptime(sys.argv[idx + 1], "%Y-%m-%d").date()
        except (IndexError, ValueError):
            print("✗ --date needs a date like 2026-11-10"); return 1
    # --no-open: don't open Preview, and exit non-zero if no PDF was made
    no_open = "--no-open" in sys.argv

    print(f"\n🖍  Daily Workbook Generator — Whimsical Edition")
    print(f"   {today_label()}\n")

    try:
        wb = generate_workbook_content()
        print("✓ Content generated")
    except Exception as e:
        print(f"✗ Generation failed: {e}"); traceback.print_exc(); return 1

    try:
        update_hsk_progress(
            progress=wb.get("_progress") or load_hsk_progress(),
            day_num=wb["day_num"], date_str=wb["_today_date"],
            today_pack=wb["_hsk_internal"],
        )
        print("✓ HSK progress updated")
    except Exception as e:
        print(f"⚠ HSK progress update failed: {e}"); traceback.print_exc()

    try:
        html_path = save_workbook_html(wb)
        print(f"✓ HTML saved: {html_path}")
    except Exception as e:
        print(f"✗ Save failed: {e}"); traceback.print_exc(); return 1

    # Convert HTML to PDF: pdfkit (wkhtmltopdf) if installed, else headless Chrome
    pdf_path = html_path.with_suffix(".pdf")
    pdf_path.unlink(missing_ok=True)  # never mistake an old PDF for a new one
    try:
        print("⏳ Generating PDF...")
        import pdfkit
        options = {
            'page-size': 'Letter',
            'margin-top': '0.25in',
            'margin-right': '0.25in',
            'margin-bottom': '0.25in',
            'margin-left': '0.25in',
            'encoding': 'UTF-8',
            'print-media-type': '',
            'enable-local-file-access': '',
            'no-outline': None,
            'dpi': '300',
        }
        pdfkit.from_file(str(html_path), str(pdf_path), options=options)
    except Exception as e:
        print(f"⚠ pdfkit unavailable or failed ({e}) — trying headless Chrome")
        export_pdf(html_path)

    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        print(f"✓ PDF saved: {pdf_path}")
        if not no_open:
            subprocess.run(["open", str(pdf_path)])
            print(f"✓ Opened in Preview — ready to print")
    else:
        print("⚠ PDF not created" + ("" if no_open else " — opening HTML instead"))
        if no_open: return 1
        subprocess.run(["open", str(html_path)])

    print(f"\n✅ Done! Saved to:\n   {html_path}\n   {pdf_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
