#!/usr/bin/env python3
"""
Workbook Generator — Whimsical Edition
Local MLX for the cozy bits; everything else is built from the files in
daily-workbook/.

Workbooks are numbered, not dated. Each one picks up where the last one
stopped (CS311, LeetCode, HSK 1, Italian, reading), so nothing falls behind
when a day is skipped. Pages that used to follow the calendar (moon, cycle,
chores) are fill-in pages now: you look, you decide, you write it down.

Setup:
    python3 -m venv .venv
    source .venv/bin/activate
    pip install mlx-lm huggingface_hub

Optional:
    export HF_TOKEN="hf_your_token"

Required for email:
    export GMAIL_APP_PASSWORD="your_16_char_gmail_app_password"

Run:
    python3 dailyWorkbookLocal.py               # build the next workbook
    python3 dailyWorkbookLocal.py --number 3    # rebuild workbook 3 (same content)
"""

import html as py_html
import sys
import json
import math
import os
import random
import shutil
import smtplib
import subprocess
import traceback
from email.message import EmailMessage
from pathlib import Path

# offline_plan.py lives one folder up, in daily-workbook/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import progression
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
    import hanzi_notes
    import hsk_stories
except ImportError:
    hanzi_notes = hsk_stories = None
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

# ── Chore menu ────────────────────────────────────────────────────────────────
# Points are effort, like story points: 1 = five minutes, 5 = a real project.
# The chore page lets you pick a budget for your energy and commit to that much.

CHORE_MENU = [
    (1, "Clear one visible surface",    "5 min"),
    (1, "Put away 10 stray items",      "5 min"),
    (1, "Dishes or sink reset",         "5–10 min"),
    (1, "Trash + recycling out",        "5 min"),
    (2, "Dishes + quick kitchen wipe",  "~10 min"),
    (2, "Laundry: wash, dry, put away", "~15 min active"),
    (2, "Clutter sweep of one room",    "~15 min"),
    (3, "Bathroom 1 deep clean",        "~25 min"),
    (3, "Floors: vacuum + mop",         "~30 min"),
    (3, "Kitchen deep reset",           "~30 min"),
    (5, "Bathroom 2 + clutter purge",   "~40 min"),
]
# One bigger chore takes the spotlight each workbook, in turn, so none of them
# waits forever. It's worth a bonus point if you pick it.
CHORE_SPOTLIGHT = [c for c in CHORE_MENU if c[0] >= 2]
CHORE_SPEED_RUNS = [
    "Set a 7-min timer and race one tiny mess, not the whole house.",
    "Set a 5-min timer and clear the bathroom counter.",
    "One song: put away everything on the floor of one room.",
    "Set a 10-min timer: fill one bag for donation or trash.",
    "Two songs: empty and reload the dishwasher or drying rack.",
]
CHORE_REWARDS = ["boba point", "sticker", "sweet treat", "cozy show episode", "fancy tea", "ten guilt-free minutes"]

# ─────────────────────────────────────────────────────────────────────────────


def esc(text) -> str:
    return py_html.escape("" if text is None else str(text))

# The workbook being built. Set in main(): the next one, or --number N.
WORKBOOK_NUM = 1

def workbook_label() -> str:
    return f"Workbook {WORKBOOK_NUM}"

def rotate(options: list, offset: int = 0):
    """The option for this workbook: walks the list in order and wraps around."""
    return options[(WORKBOOK_NUM - 1 + offset) % len(options)]

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

def get_existing_day_pack(progress: dict, day_num: int):
    for day in progress.get("days", []):
        if day.get("day_num") == day_num:
            return {
                "new_words":       words_from_chars(day.get("new_chars", [])),
                "review_words":    words_from_chars(day.get("review_chars", [])),
                "lesson_words":    words_from_chars(day.get("lesson_chars", [])),
                "char_practice":   vocab_by_char(day.get("char_practice_char", "")) or HSK1_VOCAB[0],
                "all_learned_words": words_from_chars(day.get("all_learned_chars", [])),
                "story_id":        day.get("story_id"),
                "dialogue_id":     day.get("dialogue_id"),
            }
    return None

def choose_hsk_words_for_today(progress: dict, day_num: int):
    existing = get_existing_day_pack(progress, day_num)
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

def update_hsk_progress(progress: dict, day_num: int, today_pack: dict) -> None:
    new_chars = [w["char"] for w in today_pack["new_words"]]
    introduced = progress.get("introduced_chars", [])
    for ch in new_chars:
        if ch not in introduced: introduced.append(ch)
    progress["introduced_chars"] = introduced

    replacement = {
        "day_num": day_num,
        "new_chars":        new_chars,
        "review_chars":     [w["char"] for w in today_pack["review_words"]],
        "lesson_chars":     [w["char"] for w in today_pack["lesson_words"]],
        "all_learned_chars":[w["char"] for w in today_pack["all_learned_words"]],
        "char_practice_char": today_pack["char_practice"]["char"],
    }
    for key in ("story_id", "dialogue_id"):
        if today_pack.get(key):
            replacement[key] = today_pack[key]
    days = progress.setdefault("days", [])
    for i, day in enumerate(days):
        if day.get("day_num") == day_num:
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



# ── Moon phases (a fill-in page: you look up and work out which one it is) ────

# (symbol, name, how to spot it, keywords, question)
MOON_PHASES = [
    ("🌑", "New Moon",        "dark, or not up at night",
     "New beginnings, intention setting, planting seeds",
     "What do you want to call in this cycle?"),
    ("🌒", "Waxing Crescent", "thin sliver, lit on the right, evening",
     "Growth, momentum, taking first steps",
     "What small action moves you toward your intention?"),
    ("🌓", "First Quarter",   "right half lit",
     "Decision, commitment, pushing through resistance",
     "What is in your way, and what do you choose despite it?"),
    ("🌔", "Waxing Gibbous",  "almost full, still growing",
     "Refinement, patience, trusting the process",
     "What needs adjusting before things come together?"),
    ("🌕", "Full Moon",       "a whole bright disc",
     "Culmination, release, illumination, celebration",
     "What has come to light? What are you releasing?"),
    ("🌖", "Waning Gibbous",  "just past full, shrinking",
     "Gratitude, sharing, integration",
     "What did you learn, and who can you share it with?"),
    ("🌗", "Last Quarter",    "left half lit, up after midnight",
     "Letting go, forgiveness, clearing",
     "What habit, thought, or weight do you put down?"),
    ("🌘", "Waning Crescent", "thin sliver, lit on the left, before dawn",
     "Rest, surrender, preparation",
     "Where can you rest without guilt?"),
]
MOON_REFLECTIONS = [
    "What does this phase mean to me right now?",
    "Where in my life is something growing, and where is something fading?",
    "What would it look like to move with this phase instead of against it?",
    "What do I want to be true by the time the moon looks like this again?",
    "What is this moon asking me to notice?",
    "If tonight's moon were a mood, which of mine would it be?",
]
MOON_RITUALS = [
    "Light a candle, take three slow breaths, and write one honest sentence about where you are right now.",
    "Stand outside for two minutes. Name five things you can see and one thing you can let go of.",
    "Write one word for this phase on your hand or a scrap of paper and keep it with you tomorrow.",
    "Put a glass of water where the moon would reach it. Drink it in the morning, slowly.",
    "Breathe in for four, out for six, ten times, looking at the sky or a window.",
]


# ── Cycle tracking ────────────────────────────────────────────────────────────

CYCLE_FILE = DATA_DIR / "cycle_progress.json"


def _cycle_setting(key: str, default: int) -> int:
    """Personal cycle parameters live in CYCLE_FILE, which is gitignored."""
    try:
        return int(json.loads(CYCLE_FILE.read_text(encoding="utf-8"))[key])
    except Exception:
        return default


CYCLE_LENGTH_AVG  = _cycle_setting("cycle_length_avg",  28)
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


# ── Day context ───────────────────────────────────────────────────────────────

def get_day_context() -> dict:
    progress  = load_hsk_progress()
    return {
        "day_num":   WORKBOOK_NUM,
        "today_hsk": choose_hsk_words_for_today(progress, WORKBOOK_NUM),
        "progress":  progress,
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
Context: {ctx_json({"workbook_number": ctx["day_num"], "vibe": "whimsical, cozy, children's menu, coloring workbook"})}
Rules: JSON only. Concise. No markdown."""
    return generate_json_object("theme_cover", prompt, ["theme", "cover"], fallback, 900)


def generate_morning_page(ctx: dict) -> dict:
    """Stretch, exercise and dinner ideas. Each list is walked in order, one per workbook."""
    stretch_types = [
        ("5-min morning spine wake-up", "Start lying down. Hug knees to chest for 30s. Roll to seated cat-cow x5. Standing forward fold 30s. Arms overhead side stretch each side."),
        ("Sun salutation flow", "Mountain pose → arms up → forward fold → plank → cobra → downward dog → forward fold → mountain. Repeat 3 times slowly."),
        ("Hip opener stretch", "Low lunge each side 45s. Seated pigeon each side 45s. Supine spinal twist each side 30s. Child's pose 1 min."),
        ("Desk worker reset", "Neck rolls each direction. Shoulder rolls. Chest opener arms behind back. Wrist circles. Standing quad stretch each side."),
        ("Breathwork + gentle stretch", "Box breathing 4 rounds (4 counts in, hold, out, hold). Seated forward fold. Supine knee-to-chest. End with 2 min savasana."),
    ]
    stretch_name, stretch_desc = rotate(stretch_types)

    # Ordered so a lighter option always follows a heavier one.
    exercise_suggestions = [
        "Full gym session — upper body focus",
        "Quick 20-min session — push/pull supersets",
        "Outdoor activity — long walk, hike, or bike ride with the dog",
        "Full gym session — lower body focus",
        "15-min bodyweight circuit at home — squats, push-ups, rows",
        "Easy day: the dog walks count — take them slow and breathe",
        "30-min run or walk outside + 10 min bodyweight",
        "Home workout — dumbbell circuit 30 min",
    ]
    dinner_suggestions = [
        "Sheet pan chicken thighs + roasted broccoli + rice (30 min, mostly hands-off)",
        "Homemade ramen — broth, soft-boiled eggs, veggies, pork or tofu",
        "Simple pasta + marinara + rotisserie chicken + side salad (20 min)",
        "Stir-fry beef + peppers + snap peas over rice (20 min)",
        "Stuffed bell peppers with ground beef + quinoa + tomato sauce",
        "Eggs any style + toast + sliced veg — easy, low-effort, still good",
        "Turkey taco bowls — seasoned meat, black beans, salsa, avocado (25 min)",
        "Salmon en papillote + roasted sweet potato + salad",
        "Homemade pizza on naan or flatbread — whatever toppings you have",
        "Slow cooker chili — set it going early, done by dinner",
        "Roast chicken + roasted root veg + gravy",
    ]
    return {
        "stretch_name": stretch_name,
        "stretch_desc": stretch_desc,
        "exercise": rotate(exercise_suggestions),
        "dinner": rotate(dinner_suggestions),
    }


def generate_algorithms_page(ctx: dict) -> dict:
    """CS311: this workbook's course-order questions + one random question (cs311.py)."""
    if cs311 is None:
        return {}
    return cs311.daily_set(ctx["day_num"])


def generate_leetcode_page(ctx: dict) -> dict:
    """This workbook's LeetCode problem + re-solves due (leetcode.py)."""
    if leetcode is None:
        return {}
    return leetcode.daily_set(ctx["day_num"])


def generate_reading_page(ctx: dict) -> dict:
    """This workbook's saved Substack article (reading.py) + the summary/opinion prompts."""
    if reading is None:
        return {}
    article = reading.article_for(ctx["day_num"])
    if not article:
        return {}
    return {**article, "prompts": [{"lens": label, "text": text, "follow": follow, "lines": lines}
                                   for label, text, follow, lines in reading.WRITING_PROMPTS]}


def generate_chores_page(ctx: dict) -> dict:
    """Chore sprint: a points menu, a spotlight chore that rotates, and room to commit."""
    pts, task, time_estimate = rotate(CHORE_SPOTLIGHT)
    return {
        "title": "Chore Sprint",
        "menu": [{"points": p, "task": t, "time_estimate": e} for p, t, e in CHORE_MENU],
        "spotlight": {"points": pts, "task": task, "time_estimate": time_estimate},
        "speed_run": rotate(CHORE_SPEED_RUNS),
        "reward_ideas": [rotate(CHORE_REWARDS, k) for k in range(4)],
    }


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
    """One life admin task (they take turns) + parking lot for ideas."""

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
        "admin_task": rotate(admin_tasks),
        "parking_items": random.sample(parking_items, min(2, len(parking_items))),
    }


def _recent_story_picks(progress: dict, day_num: int, days: int = 3) -> tuple[list, list]:
    """Story and dialogue ids used in the few workbooks before this one."""
    earlier = sorted((d for d in progress.get("days", []) if d.get("day_num", 0) < day_num),
                     key=lambda d: d["day_num"])[-days:]
    return [d.get("story_id") for d in earlier], [d.get("dialogue_id") for d in earlier]


def _word_anatomy(word: dict) -> dict:
    """Breakdown of one lesson word: each character's meaning, or a single character's parts."""
    w = word["char"]
    out = {"word": w, "pinyin": word.get("pinyin", ""), "meaning": word.get("meaning", ""),
           "chars": [], "parts": [], "radical": None, "literal": "", "note": ""}
    if not hanzi_notes:
        return out
    bd = hanzi_notes.word_breakdown(w)
    if len(bd["chars"]) > 1:
        out["chars"] = [{"char": c["char"], "pinyin": c["pinyin"], "meaning": c["meaning"].split(";")[0]} for c in bd["chars"]]
        out["literal"] = bd["literal"].split(": ", 1)[-1] if ": " in bd["literal"] else ""
    elif bd["chars"]:
        c = bd["chars"][0]
        out["parts"] = [{"char": p, "meaning": m} for p, m in c.get("parts", [])]
        out["radical"] = hanzi_notes.radical_info(c.get("radical", ""))
        out["note"] = c.get("note", "")
    return out


def _story_payload(story: dict) -> list[tuple]:
    return [(spk, cn, py, en) for spk, cn, py, en in story["lines"]]


_FALLBACK_STORY = {
    "id": None, "title": "你好，小学生", "title_en": "Hello, little student",
    "lines": [("", cn, py, en) for cn, py, en in [
        ("你好。", "Nǐ hǎo.", "Hello."),
        ("你好吗？", "Nǐ hǎo ma?", "How are you?"),
        ("我很好。", "Wǒ hěn hǎo.", "I'm very well."),
        ("我是学生。", "Wǒ shì xuésheng.", "I'm a student."),
        ("你是老师吗？", "Nǐ shì lǎoshī ma?", "Are you a teacher?"),
        ("我不是老师。", "Wǒ bú shì lǎoshī.", "I'm not a teacher."),
        ("我也是学生。", "Wǒ yě shì xuésheng.", "I'm a student too."),
        ("我很好，你呢？", "Wǒ hěn hǎo, nǐ ne?", "I'm very well. And you?"),
    ]],
    "questions": ["Who says hello?", "Is 我 a teacher?", "Which line asks a question?"],
    "note": ("吗 ma", "吗 at the end turns a sentence into a yes/no question: 你是老师吗？"),
}
_FALLBACK_DIALOGUE = {
    "id": None, "title": "Hi, and you?",
    "lines": [("A", "你好！", "Nǐ hǎo!", "Hi!"), ("B", "你好！你好吗？", "Nǐ hǎo! Nǐ hǎo ma?", "Hi! How are you?"),
              ("A", "我很好，你呢？", "Wǒ hěn hǎo, nǐ ne?", "I'm good. And you?"), ("B", "我也很好。", "Wǒ yě hěn hǎo.", "I'm good too.")],
    "phrases": [("你呢？", "nǐ ne?", "And you?", "Bounce any question back without repeating it.")],
}


def build_chinese_pages(ctx: dict) -> dict:
    """Chinese pages from HSK 1 progress: word and character anatomy, a story and a dialogue
    picked from hsk_stories to fit the words learned so far."""
    today_hsk = ctx["today_hsk"]
    lesson_words = today_hsk["lesson_words"][:LESSON_WORDS_PER_DAY]
    review_words = dedupe_words(today_hsk.get("review_words",[]) + today_hsk.get("lesson_words",[]))[:4]
    char_target  = today_hsk["char_practice"]
    day_num      = ctx["day_num"]
    pick_key     = f"workbook-{day_num}"   # varies the tie-break from one workbook to the next

    vocab   = set(WORD_INDEX)
    learned = {w["char"] for w in today_hsk.get("all_learned_words", []) + lesson_words}
    new     = [w["char"] for w in today_hsk.get("new_words", [])]
    focus   = new + [w["char"] for w in lesson_words if w["char"] not in new]

    story = dialogue = None
    if hsk_stories:
        recent_s, recent_d = _recent_story_picks(ctx.get("progress") or {}, day_num)
        story = hsk_stories.pick(hsk_stories.STORIES, vocab, learned, focus, recent_s, pick_key, today_hsk.get("story_id"))
        dialogue = hsk_stories.pick(hsk_stories.DIALOGUES, vocab, learned, focus, recent_d, pick_key, today_hsk.get("dialogue_id"))
    story    = story or _FALLBACK_STORY
    dialogue = dialogue or _FALLBACK_DIALOGUE
    today_hsk["story_id"], today_hsk["dialogue_id"] = story["id"], dialogue["id"]
    lines = _story_payload(story)

    # Words in the story that aren't on the HSK list yet
    bonus = []
    if hsk_stories and story["id"]:
        for w in hsk_stories.bonus_words(story, vocab):
            py, en, lit = hanzi_notes.BONUS[w]
            bonus.append({"char": w, "pinyin": py, "meaning": en, "literal": lit})

    # Characters on today's writing page and the radicals they're built on
    practice_chars = []
    for v in lesson_words:
        for ch in v["char"]:
            if "一" <= ch <= "鿿" and ch not in practice_chars:
                practice_chars.append(ch)
    practice_chars = practice_chars[:6]
    known_chars = [c for w in today_hsk.get("all_learned_words", []) + lesson_words for c in w["char"]]
    spotlight = []
    if hanzi_notes:
        for ch in practice_chars:
            info = hanzi_notes.char_info(ch)
            if not info or any(r["radical"] == info["radical"] for r in spotlight):
                continue
            rad = hanzi_notes.radical_info(info["radical"])
            if rad:
                rad["chars"] = hanzi_notes.same_radical(info["radical"], [ch] + known_chars)[:10]
                spotlight.append(rad)
        spotlight = spotlight[:4]

    # Review quiz from today's words
    quiz = []
    multi = next((w for w in lesson_words if len(w["char"]) > 1), None)
    if multi:
        quiz.append(f"Split {multi['char']} into its characters and write what each one means on its own.")
    if spotlight:
        r = spotlight[0]
        quiz.append(f"Find the radical {r['radical']} ({r['meaning']}) in today's characters. Circle it each time.")
    if lesson_words:
        quiz.append(f"Write the meaning of {lesson_words[-1]['char']} without looking.")
    quiz.append("Copy one line of the story without looking, then check it.")

    return {
        "chinese_lesson_page": {
            "title": "Mandarin Mini Noodle Shop",
            "lesson_intro": "Learn each word, then take it apart: what each character means and what it's built from.",
            "new_words_banner": "Today's word basket",
            "review_banner": "Review sprinkles",
            "vocab": lesson_words,
            "review_words": review_words,
            "word_anatomy": [_word_anatomy(w) for w in lesson_words],
            "practice_chars": practice_chars,
            "character_practice": {
                "char": char_target["char"], "pinyin": char_target["pinyin"],
                "meaning": char_target["meaning"],
                "stroke_hint": "Write slowly and copy the shape like a tiny drawing.",
                "example_word": char_target["char"],
            },
            "dialogue_title": dialogue["title"],
            "mini_dialogue": [{"speaker": spk, "chinese": cn, "pinyin": py, "meaning": en} for spk, cn, py, en in dialogue["lines"]],
            "dialogue_phrases": [{"chinese": cn, "pinyin": py, "meaning": en, "usage": use} for cn, py, en, use in dialogue.get("phrases", [])],
            "tiny_game": "Cover the English and say each line out loud. Then write the phrase you'll actually use this week:",
        },
        "chinese_reference_page": {
            "title": "Tiny Mandarin Menu Card",
            "reference_intro": "Use this page when the story feels slippery. Check the words and line helper, then go back.",
            "word_bank_title": "New in this story",
            "bonus_words": bonus,
            "radical_spotlight": spotlight,
            "grammar_title": story["note"][0],
            "grammar_note": story["note"][1],
            "reader_helper_words": [],
            "reader_translation_title": "Story line helper",
            "reader_line_glosses": [{"line_no": i+1, "chinese": cn, "pinyin": py, "meaning": en} for i, (_, cn, py, en) in enumerate(lines)],
            "review_quiz_prompts": quiz,
        },
        "chinese_reader_page": {
            "title": "Tiny HSK 1 Story",
            "reader_intro": "Read once with pinyin, then cover the pinyin and try again.",
            "story_title": story["title"],
            "story_title_en": story["title_en"],
            "story_speakers": [spk for spk, _, _, _ in lines],
            "story_lines":  [cn for _, cn, _, _ in lines],
            "pinyin_lines": [py for _, _, py, _ in lines],
            "comprehension_questions": story["questions"],
            "copywork_prompt": "Copy 3 short lines from the story. Add a sticker next to the neatest one.",
        },
    }


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
Rules: JSON only. Gentle and cozy."""
    return generate_json_object("reflection_back", prompt, ["reflection_page","back_page"], fallback, 900)


def generate_workbook_content() -> dict:
    ctx = get_day_context()
    print(f"\n📓 {workbook_label()}")
    print("⏳ Generating workbook section by section...\n")

    wb = {"day_num": ctx["day_num"]}

    wb.update(generate_theme_and_cover(ctx))
    wb["_morning"]    = generate_morning_page(ctx)
    wb["_algorithms"] = generate_algorithms_page(ctx)
    wb["_leetcode"]   = generate_leetcode_page(ctx)
    wb["_italian"]    = italian.daily_set(ctx["day_num"]) if italian else {}
    wb["_reading"]    = generate_reading_page(ctx)
    wb["chores_page"] = generate_chores_page(ctx)
    wb["_admin_parking"] = generate_admin_parking(ctx)
    wb["_offline"] = offline_plan.general_summary() if offline_plan else {}
    wb.update(build_chinese_pages(ctx))
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

  .reader-line { margin-bottom:8px; position:relative; }
  .reader-spk { position:absolute; left:-20px; top:4px; font-family:Menlo,Monaco,monospace; font-size:10px; font-weight:800; color:#7b67a8; border:1.5px solid #d7c6ff; border-radius:6px; padding:0 4px; }
  .reader-line:has(.reader-spk) { margin-left:22px; }
  .wa-row { display:flex; gap:12px; align-items:flex-start; border-top:2px dashed #e3d9f5; padding:7px 0; }
  .wa-row:first-of-type { border-top:none; }
  .wa-word { width:96px; flex-shrink:0; }
  .wa-big { font-size:24px; font-weight:900; color:#23675e; line-height:1.1; }
  .wa-py { font-family:Menlo,Monaco,monospace; font-size:10px; color:#56867f; }
  .wa-en { font-size:11px; color:#375b56; }
  .wa-body { flex:1; }
  .wa-parts { display:flex; align-items:center; flex-wrap:wrap; gap:4px; }
  .wa-chip { border:2px solid #bee9e2; background:#f3fffd; border-radius:10px; padding:3px 9px; text-align:center; min-width:52px; }
  .wa-chip.part { border-style:dashed; border-color:#c8b6ff; background:#f8f6ff; }
  .wa-c { font-size:20px; font-weight:900; color:#2c3e50; line-height:1.15; }
  .wa-cpy { font-family:Menlo,Monaco,monospace; font-size:9px; color:#56867f; }
  .wa-cen { font-size:10.5px; color:#4a4a4a; }
  .wa-plus { font-size:16px; font-weight:800; color:#b7a8d8; }
  .wa-lit { font-size:12px; color:#5d4d85; font-weight:700; margin-top:4px; line-height:1.35; }
  .wa-rad { font-size:11px; color:#2B9C8E; margin-top:4px; }
  .hz-anat { font-size:11.5px; color:#4a4a4a; margin-top:3px; line-height:1.4; }
  .hz-rad { color:#2B9C8E; font-weight:800; }
  .hz-why { font-size:11px; color:#7a665b; margin-top:2px; line-height:1.4; font-style:italic; }
  .phrase-row { display:flex; gap:12px; align-items:baseline; border-top:2px dashed #eadff7; padding:6px 0; }
  .phrase-row:first-of-type { border-top:none; }
  .phrase-cn { font-size:18px; font-weight:900; color:#4c3d6a; min-width:120px; }
  .phrase-sub { font-family:Menlo,Monaco,monospace; font-size:10.5px; color:#7b7190; }
  .phrase-use { font-size:12px; color:#5f5770; margin-top:2px; }
  .bonus-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; }
  .bonus-lit { font-size:10.5px; color:#6a7f7c; font-style:italic; margin-top:-4px; }
  .rad-row { display:flex; gap:12px; align-items:flex-start; border-top:2px dashed #cdeee9; padding:7px 0; }
  .rad-row:first-of-type { border-top:none; }
  .rad-glyph { font-size:34px; font-weight:900; color:#2B9C8E; width:48px; height:48px; border:2px solid #9DD9D2; border-radius:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:#F3FFFD; }
  .rad-name { font-size:13px; font-weight:800; color:#2B665E; }
  .rad-tip { font-size:12px; color:#4a5f5c; margin-top:2px; line-height:1.4; }
  .rad-chars { font-size:11px; color:#6a7f7c; margin-top:3px; }
  .rad-chars span { font-size:17px; font-weight:800; color:#2c3e50; letter-spacing:4px; }
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
  .moon-grid { overflow:hidden; margin:8px 0 2px; }
  .moon-cell { float:left; width:23.5%; margin:0 1.5% 8px 0; box-sizing:border-box; border:1.5px solid #9B8EC4; border-radius:12px; padding:7px 6px; text-align:center; min-height:176px; }
  .moon-cell-emoji { font-size:28px; line-height:1.1; }
  .moon-cell-name { font-size:12.5px; font-weight:800; color:#2b2540; margin:2px 0; }
  .moon-cell-spot { font-family:Menlo,Monaco,monospace; font-size:9px; color:#555; margin-bottom:4px; }
  .moon-cell-kw { font-size:10.5px; color:#333; line-height:1.3; }
  .moon-cell-q { font-size:10.5px; color:#444; font-style:italic; line-height:1.3; margin-top:4px; }
  .moon-draw { width:130px; height:130px; border:2px dashed #9B8EC4; border-radius:50%; margin:8px auto 4px; }
  .chore-menu { overflow:hidden; }
  .chore-menu-item { float:left; width:48%; margin:0 2% 6px 0; box-sizing:border-box; font-size:12.5px; color:#222; line-height:1.35; }
  .chore-pts { display:inline-block; min-width:34px; text-align:center; font-family:Menlo,Monaco,monospace; font-size:10.5px; font-weight:700; border:1.5px solid #C8B6FF; border-radius:8px; padding:1px 4px; margin-right:6px; color:#5D4D85; background:#F8F6FF; }
  .chore-commit-row { overflow:hidden; margin-bottom:9px; }
  .chore-commit-box { float:left; width:18px; height:18px; border:2px solid #C8B6FF; border-radius:5px; margin-right:8px; }
  .chore-commit-line { float:left; width:68%; border-bottom:2px dashed #D8D0C8; height:20px; }
  .chore-commit-pts { float:right; width:70px; border-bottom:2px dashed #D8D0C8; height:20px; text-align:right; font-family:Menlo,Monaco,monospace; font-size:10.5px; color:#888; }
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

    .card, .hero-card,
    .moon-card, .moon-reflection, .moon-ritual,
    .full-moon-alert, .new-moon-alert,
    .cycle-card, .cycle-block, .cycle-alert, .cycle-emotional,
    .dog-block, .morning-checklist, .one-thing-box, .brain-dump-box,
    .stretch-card, .exercise-card, .dinner-card,
    .admin-card, .parking-card, .offline-card, .algo-card, .algo-intro, .walk-step, .prompt-card, .lc-card, .hz-card, .evening-dog,
    .vocab-card, .check-card, .dialogue-card, .gloss-card, .wa-row, .rad-row, .phrase-row,
    .doodle-cloud, .sticker-slot {
      page-break-inside: avoid !important;
      break-inside: avoid !important;
    }

    .section-head, .section-title, .mini-title {
      page-break-after: avoid !important;
      break-after: avoid !important;
    }

    .vocab-grid, .sticker-grid, .gloss-grid, .doodle-grid,
    .cycle-row, .split, .split-3,
    .trace-row, .moon-grid, .chore-menu {
      page-break-inside: avoid !important;
      break-inside: avoid !important;
    }

    .card.split-ok, .split-ok .gloss-grid, .split-ok .bonus-grid { page-break-inside: auto !important; break-inside: auto !important; }

    .page { font-size: 95% !important; }
    .card, .hero-card, .moon-card, .cycle-card { margin-bottom:9px !important; }
  }
</style>
"""


def page_footer_label() -> str:
    """Stamped next to each page number, e.g. 'Workbook 3'."""
    return workbook_label()


def page_number_style() -> str:
    """Stamp 'Workbook 3 · 3 / 54' in the bottom margin of every printed sheet.

    Uses @page margin boxes, so it numbers physical sheets — including the
    extra sheets that .flow pages (articles, worked problems) spill onto — and
    the workbook number keeps them apart when several are printed and bound
    together.
    """
    return ("<style>@page { @bottom-right {"
            f" content: \"{page_footer_label()} · \" counter(page) \" / \" counter(pages);"
            " font-family: Menlo, Monaco, monospace; font-size: 8pt; color: #8a7a6a;"
            " vertical-align: middle; } }</style>")


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
    admin_parking  = wb.get("_admin_parking", {})
    day_num        = wb.get("day_num", 1)

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
    chore_menu_html = "".join(
        f'<div class="chore-menu-item"><span class="chore-pts">{c["points"]} pt{"" if c["points"] == 1 else "s"}</span>'
        f'{esc(c["task"])} <span class="mini-note">{esc(c["time_estimate"])}</span></div>' for c in chores["menu"])
    chore_commit_html = "".join(
        '<div class="chore-commit-row"><div class="chore-commit-box"></div><div class="chore-commit-line"></div>'
        '<div class="chore-commit-pts">pts</div></div>' for _ in range(5))
    spotlight = chores["spotlight"]
    lesson_vocab_html = "".join(vocab_card(v) for v in chinese_lesson["vocab"])
    review_vocab_html = "".join(vocab_card(v) for v in chinese_lesson["review_words"][:3])
    dialogue_html = "".join(dialogue_row(l) for l in chinese_lesson["mini_dialogue"])
    helper_html = "".join(vocab_card(v) for v in chinese_ref["reader_helper_words"])
    gloss_html = "".join(f'<div class="gloss-card"><div class="gloss-line-no">Line {esc(str(item.get("line_no","")))} </div><div class="gloss-cn">{esc(item.get("chinese",""))}</div><div class="gloss-pinyin">{esc(item.get("pinyin",""))}</div><div class="gloss-en">{esc(item.get("meaning",""))}</div></div>' for item in chinese_ref["reader_line_glosses"])
    speakers = chinese_reader.get("story_speakers") or [""] * len(chinese_reader["story_lines"])
    reader_html = "".join(
        f'<div class="reader-line">{f"""<span class="reader-spk">{esc(spk)}</span>""" if spk else ""}<div class="reader-cn">{esc(cn)}</div><div class="reader-pinyin">{esc(py)}</div></div>'
        for spk, cn, py in zip(speakers, chinese_reader["story_lines"], chinese_reader["pinyin_lines"]))
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
        f"<title>{esc(workbook_label())}</title>",
        STYLES,
        page_number_style(),
        "</head><body>",
    ]

    parts.append("<!--SECTION:cover-->")
    # ── PAGE 1: Cover + Morning ───────────────────────────────────────────────
    parts.append(f"""
<div class="page"><div class="frame">
  <div class="eyebrow">Workbook {day_num} · pick it up whenever you're ready</div>
  <div class="main-title">✨ {esc(theme["title"])} ✨</div>
  <div class="sub-title">{esc(theme["subtitle"])} · started on: ______________</div>
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
            extra = (f'<div class="footer-note">{esc(r.get("topic",""))} Q{r.get("question_number","")}'
                     f' · from workbook {esc(r.get("from_workbook",""))}</div>')
            cards += practice_card(r.get("practice") or {}, "Redo it cold", extra)
        return f"""
<div class="page flow"><div class="frame">
  {section_title("cs311 · spaced review", "Can you still do it?", f"{len(reviews)} from earlier workbooks")}
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

        def examples_html(p):
            return "".join(
                f'<div class="lc-example"><b>Input:</b> {esc(i)}<br><b>Output:</b> {esc(o)}'
                + (f'<br><span class="lc-why">{esc(w)}</span>' if w else "") + "</div>"
                for i, o, w in p.get("examples", []))

        reviews_html = ""
        for r in lc.get("reviews", []):
            reviews_html += (f'<div class="card lc-card"><div class="mini-title">🔁 Re-solve: #{r["lc"]} {esc(r["title"])} '
                             f'<span class="lc-meta">from {r["workbooks_ago"]} workbooks ago</span></div>'
                             f'<div class="lc-statement">{esc(r.get("statement", ""))}</div>'
                             f'<div class="lc-ex-grid">{examples_html(r)}</div>'
                             f'<div class="footer-note" style="margin-top:4px;"><b>Constraints:</b> {esc(r.get("constraints", ""))}</div>'
                             f'<div class="footer-note" style="margin-top:6px;">Without looking back: name the pattern, write the key idea, then the code. '
                             f'Check it against the solution on the LeetCode answer page.</div>'
                             f'{blank_lines(7, "#C9D6E8", 22)}</div>')
        if lp:
            ex_html = examples_html(lp)
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
    # ── Chores: a points menu to commit to ────────────────────────────────────
    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("home quest", chores["title"], "pick your points")}

  <div class="card">
    <div class="mini-title">1 · Energy check: circle your budget</div>
    <div>{chip("Low energy → 3 points")}{chip("Medium → 5 points")}{chip("High → 8 points")}</div>
    <div class="footer-note" style="margin-top:6px;">Points are effort, not minutes. A small budget you finish beats a big one you avoid.</div>
  </div>

  <div class="card">
    <div class="mini-title">2 · The menu</div>
    <div class="chore-menu">{chore_menu_html}</div>
    <div class="footer-note" style="margin-top:4px;">⭐ In the spotlight this time: <b>{esc(spotlight["task"])}</b> ({spotlight["points"]} pts, plus 1 bonus point if you pick it).</div>
    <div class="footer-note">Put a ! next to anything overdue, smelly, or nagging at you. Those go into your sprint first.</div>
  </div>

  <div class="card">
    <div class="mini-title">3 · My sprint: what I'm committing to</div>
    {chore_commit_html}
    <div class="footer-note" style="margin-top:4px;">Committed: ______ pts &nbsp;·&nbsp; Done: ______ pts &nbsp;·&nbsp; Carrying over to next time: ______________________</div>
  </div>

  <div class="split">
    <div class="card">
      <div class="mini-title">Speed-run challenge</div>
      <div class="footer-note">{esc(chores["speed_run"])}</div>
    </div>
    <div class="card">
      <div class="mini-title">Reward snack bar</div>
      <div>{reward_chips}</div>
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
        if offline.get("mode") == "weekly_day":
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
        lens_colors = {"Summary": ("#EFF7FF", "#A8C4D8", "#2F5277"),
                       "My take": ("#FFF0F5", "#F2B5CF", "#7B4C62")}
        def prompt_card(n, pr):
            bg, border, fg = lens_colors.get(pr["lens"], ("#F9F9F9", "#C8C8C8", "#555"))
            return (f'<div class="card prompt-card"><div>{chip(pr["lens"], bg, border, fg)}</div>'
                    f'<div class="prompt-text">{n}. {esc(pr["text"])}</div>'
                    f'<div class="prompt-follow">{esc(pr.get("follow",""))}</div>{blank_lines(pr.get("lines", 6))}</div>')
        prs = art.get("prompts", [])
        first = "".join(prompt_card(n, pr) for n, pr in enumerate(prs[:1], 1))
        second = "".join(prompt_card(n, pr) for n, pr in enumerate(prs[1:], 2))
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

    parts.append("<!--SECTION:moon-->")
    # ── Moon: look up, work out the phase, reflect ───────────────────────────
    moon_cells = "".join(
        f'<div class="moon-cell"><div class="moon-cell-emoji">{sym}</div><div class="moon-cell-name">{esc(name)}</div>'
        f'<div class="moon-cell-spot">{esc(spot)}</div><div class="moon-cell-kw">{esc(kw)}</div>'
        f'<div class="moon-cell-q">{esc(q)}</div></div>'
        for sym, name, spot, kw, q in MOON_PHASES)
    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("tonight\'s sky", "Which moon is it?", "look up")}

  <div class="moon-card">
    <div class="moon-text">Find the moon tonight, outside or through a window, and circle the one that matches. Can\'t see it? Go from the last one you remember: it moves one box along about every 3 to 4 days, and the whole loop takes 29.5.</div>
    <div class="moon-grid">{moon_cells}</div>
    <div class="moon-text" style="font-size:11.5px;color:#555;margin-bottom:0;">Growing night to night = waxing. Shrinking = waning. Each box has what the phase is about and the question it asks.</div>
  </div>

  <div class="split">
    <div class="card">
      <div class="mini-title">Draw what you see</div>
      <div class="moon-draw"></div>
      <div class="mini-note" style="text-align:center;">shade the dark part</div>
    </div>
    <div class="card">
      <div class="mini-title">Tonight it is</div>
      <div class="moon-write-line"></div>
      <div class="mini-title" style="margin-top:8px;">My answer to its question</div>
      {''.join('<div class="moon-write-line"></div>' for _ in range(3))}
    </div>
  </div>

  <div class="card">
    <div class="moon-reflection">
      <div class="moon-reflection-q">✦ {esc(rotate(MOON_REFLECTIONS))}</div>
    </div>
    <div style="margin-top:6px;">
      {''.join('<div class="moon-write-line"></div>' for _ in range(4))}
    </div>
    <div class="moon-ritual">
      <div class="moon-section-label">A two-minute ritual</div>
      <div class="moon-ritual-text">{esc(rotate(MOON_RITUALS))}</div>
    </div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")


    parts.append("<!--SECTION:cycle-->")
    # ── Cycle: a reference for every phase; you mark where you are ───────────
    def _first_sentence(text):
        return text.split(". ")[0].rstrip(".") + "."
    cycle_blocks = "".join(
        f'''<div class="cycle-block" style="margin-bottom:8px;border-color:{ph["accent"]};">
      <div class="cycle-block-title">{ph["emoji"]} {esc(ph["name"])} · {esc(ph["days"])} · {esc(ph["energy"])}</div>
      <div class="cycle-block-text">{esc(ph["keywords"])}. {esc(_first_sentence(ph["task_tone"]))}</div>
      <div class="cycle-block-text" style="color:#555;">🍵 {esc(ph.get("tea", {}).get("blend", ""))}</div>
    </div>''' for ph in CYCLE_PHASES.values())
    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("inner season", "Where am I in my cycle?", "body wisdom")}

  <div class="cycle-card">
    <div class="cycle-text"><strong>Cycle day: ______</strong> &nbsp;(day 1 is the first day of your period; a full cycle runs about {CYCLE_LENGTH_AVG} days)</div>
    <div class="cycle-text">Circle the phase that fits. Go by how you actually feel as much as by the day count.</div>
    {cycle_blocks}
  </div>

  <div class="card">
    <div class="mini-title">For the phase I circled</div>
    <div class="cycle-emotional-q">💬 What is my body asking for?</div>
    {''.join('<div class="cycle-write-line"></div>' for _ in range(2))}
    <div class="cycle-emotional-q" style="margin-top:8px;">How I\'ll pace this workbook</div>
    <div>{chip("gentle")}{chip("steady")}{chip("push")}<span class="mini-note" style="margin-left:8px;">circle one</span></div>
    <div class="cycle-emotional-q" style="margin-top:10px;">One kind thing I\'ll do for myself</div>
    <div class="cycle-write-line"></div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")


    parts.append("<!--SECTION:chinese-->")
    # ── PAGES 5-7: Chinese ────────────────────────────────────────────────────────
    def anatomy_row(a):
        head = (f'<div class="wa-word"><div class="wa-big">{esc(a["word"])}</div>'
                f'<div class="wa-py">{esc(a["pinyin"])}</div><div class="wa-en">{esc(a["meaning"])}</div></div>')
        if a.get("chars"):
            chips = '<span class="wa-plus">+</span>'.join(
                f'<div class="wa-chip"><div class="wa-c">{esc(c["char"])}</div><div class="wa-cpy">{esc(c["pinyin"])}</div>'
                f'<div class="wa-cen">{esc(c["meaning"])}</div></div>' for c in a["chars"])
            lit = f'<div class="wa-lit">→ {esc(a["literal"])}</div>' if a.get("literal") else ""
            body = f'<div class="wa-parts">{chips}</div>{lit}'
        else:
            chips = '<span class="wa-plus">+</span>'.join(
                f'<div class="wa-chip part"><div class="wa-c">{esc(p["char"])}</div><div class="wa-cen">{esc(p["meaning"])}</div></div>'
                for p in a.get("parts", []))
            rad = a.get("radical")
            rad_html = (f'<div class="wa-rad">radical <b>{esc(rad["radical"])}</b> {esc(rad["pinyin"])} · {esc(rad["meaning"])}</div>'
                        if rad else "")
            body = (f'<div class="wa-parts">{chips}</div>' if chips else "") + rad_html + \
                   (f'<div class="wa-lit">{esc(a["note"])}</div>' if a.get("note") else "")
        return f'<div class="wa-row">{head}<div class="wa-body">{body}</div></div>'

    anatomy_html = "".join(anatomy_row(a) for a in chinese_lesson.get("word_anatomy", []))
    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("Chinese lesson", chinese_lesson["title"], "learn & review")}
  <div class="card">
    <div class="mini-title">Lesson intro</div>
    <div class="footer-note">{esc(chinese_lesson["lesson_intro"])}</div>
  </div>
  <div class="card">
    <div class="mini-title">{esc(chinese_lesson["new_words_banner"])}</div>
    <div class="vocab-grid">{lesson_vocab_html}</div>
  </div>
  {f'''<div class="card split-ok">
    <div class="mini-title">Take it apart 拆字</div>
    <div class="mini-note" style="margin-bottom:6px;">Words: what each character means on its own. Single characters: the pieces they're built from.</div>
    {anatomy_html}
  </div>''' if anatomy_html else ""}
  <div class="card">
    <div class="mini-title">{esc(chinese_lesson["review_banner"])}</div>
    <div class="vocab-grid">{review_vocab_html}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    # Writing practice: stroke order, radical and parts, 田字格 squares for each character
    seen_chars, practice_cards = list(chinese_lesson.get("practice_chars") or []), []
    if not seen_chars:
        for v in chinese_lesson.get("vocab", []):
            for ch in v.get("char", ""):
                if "一" <= ch <= "鿿" and ch not in seen_chars:
                    seen_chars.append(ch)
    for ch in seen_chars[:6]:
        word = WORD_INDEX.get(ch) or next((w for w in chinese_lesson.get("vocab", []) if ch in w.get("char", "")), {})
        info = hanzi_notes.char_info(ch) if hanzi_notes else None
        pinyin = info["pinyin"] if info else word.get("pinyin", "")
        meaning = info["meaning"] if info else word.get("meaning", "")
        in_word = "" if word.get("char") == ch else f' · in {esc(word.get("char",""))}'
        n = hanzi.stroke_count(ch) if hanzi else None
        strip = hanzi.stroke_order(ch) if hanzi else ""
        boxes1 = "".join(hanzi.box(ch, 0.7, "trace") for _ in range(3)) + "".join(hanzi.box(None, 0.7) for _ in range(6)) if hanzi else ""
        boxes2 = "".join(hanzi.box(None, 0.7) for _ in range(9)) if hanzi else ""
        anat = ""
        if info:
            pieces = " + ".join(f'<b>{esc(p)}</b> {esc(m)}' if m else f'<b>{esc(p)}</b>' for p, m in info["parts"])
            if info["is_radical"]:
                rad_line = f'<span class="hz-rad">{esc(ch)} is a radical itself</span> · {esc(info["radical_meaning"])}'
            else:
                rad_line = (f'<span class="hz-rad">radical {esc(info["radical"])}</span> '
                            f'{esc(info["radical_pinyin"])} · {esc(info["radical_meaning"])}')
            anat = (f'<div class="hz-anat">{rad_line}{" &nbsp;|&nbsp; parts: " + pieces if pieces else ""}</div>'
                    f'<div class="hz-why">{esc(info["note"])}</div>')
        practice_cards.append(f'''
  <div class="card hz-card">
    <div class="hz-head">
      {hanzi.box(ch, 0.95, "model", radical=True) if hanzi else f'<div class="vocab-char">{esc(ch)}</div>'}
      <div>
        <div class="hz-title">{esc(ch)} <span class="hz-pinyin">{esc(pinyin)}</span></div>
        <div class="footer-note">{esc(meaning)}{in_word}{f" · {n} strokes" if n else ""}</div>
        {anat}
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
  <div class="footer-note" style="margin-bottom:8px;">Trace the gray characters first, then write on your own. Say the sound out loud each time you write it.
  <span style="color:#2B9C8E;font-weight:800;">Teal strokes</span> are the radical; the red stroke in the strip is the new one and the circle shows where the pen starts.</div>
  {"".join(practice_cards)}
  <div style="flex:1"></div>
</div></div>
""")

    phrases_html = "".join(
        f'<div class="phrase-row"><div class="phrase-cn">{esc(p["chinese"])}</div>'
        f'<div><div class="phrase-sub">{esc(p["pinyin"])}{" · " if p["pinyin"] and p["meaning"] else ""}{esc(p["meaning"])}</div>'
        f'<div class="phrase-use">{esc(p["usage"])}</div></div></div>'
        for p in chinese_lesson.get("dialogue_phrases", []))
    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("Chinese lesson", "Everyday talk: " + chinese_lesson.get("dialogue_title", "Mini dialogue"), "read it aloud")}
  <div class="card">
    {dialogue_html}
  </div>
  {f'<div class="card"><div class="mini-title">Phrases to steal</div>{phrases_html}</div>' if phrases_html else ""}
  <div class="card">
    <div class="mini-title">Tiny game</div>
    <div class="footer-note">{esc(chinese_lesson["tiny_game"])}</div>
    <div class="ms-grid">{ms_grid(2)}</div>
  </div>
  <div style="flex:1"></div>
</div></div>
""")

    bonus_html = "".join(
        f'<div class="vocab-card"><div class="vocab-char">{esc(b["char"])}</div><div class="vocab-pinyin">{esc(b["pinyin"])}</div>'
        f'<div class="vocab-meaning">{esc(b["meaning"])}</div>'
        f'{f"""<div class="bonus-lit">{esc(b["literal"])}</div>""" if b.get("literal") else ""}</div>'
        for b in chinese_ref.get("bonus_words", []))
    spotlight_html = "".join(
        f'<div class="rad-row"><div class="rad-glyph">{esc(r["radical"])}</div>'
        f'<div><div class="rad-name">{esc(r["pinyin"])} · {esc(r["meaning"])}</div>'
        f'<div class="rad-tip">{esc(r["tip"])}</div>'
        f'<div class="rad-chars">In characters you know: <span>{" ".join(esc(c) for c in r["chars"])}</span></div></div></div>'
        for r in chinese_ref.get("radical_spotlight", []))
    parts.append(f"""
<div class="page flow"><div class="frame">
  {section_title("reference page", chinese_ref["title"], "cheat sheet")}
  {f'''<div class="card split-ok">
    <div class="mini-title">{esc(chinese_ref["word_bank_title"])}</div>
    <div class="mini-note" style="margin-bottom:6px;">Not on your HSK list yet. Read them, don't memorise them.</div>
    <div class="bonus-grid">{bonus_html}</div>
  </div>''' if bonus_html else ""}
  {f'''<div class="card split-ok">
    <div class="mini-title">Radical spotlight 部首</div>
    <div class="mini-note" style="margin-bottom:6px;">The radical is the part a dictionary files a character under. It often hints at the meaning; the other part often hints at the sound.</div>
    {spotlight_html}
  </div>''' if spotlight_html else ""}
  <div class="card">
    <div class="mini-title">Grammar & phrase note: {esc(chinese_ref.get("grammar_title", ""))}</div>
    <div class="footer-note">{esc(chinese_ref["grammar_note"])}</div>
  </div>
  <div class="card split-ok">
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
    <div class="mini-title" style="font-size:20px;">{esc(chinese_reader["story_title"])} <span style="font-size:12px;font-weight:600;color:#85756d;">{esc(chinese_reader.get("story_title_en", ""))}</span></div>
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
            f'<div class="card lc-card"><div class="mini-title">Re-solve check: #{r["lc"]} {esc(r["title"])} '
            f'<span class="lc-meta">{esc(r["pattern"])}</span></div>'
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


# Order the printed sections. Gentle check-in pages (moon, cycle) come before
# the brain-heavy study pages; answer keys stay at the back.
SECTION_ORDER = [
    "cover", "moon", "cycle",
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
    out_path = OUTPUT_DIR / f"workbook-{progression.label(WORKBOOK_NUM)}.html"
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

def find_headless_shells() -> list[str]:
    """Playwright's chrome-headless-shell builds, newest first.

    Chrome 157 fails to print long workbooks ("Printing failed", no file), so
    these are the fallback when the regular browser doesn't produce a PDF.
    """
    root = Path.home() / "Library" / "Caches" / "ms-playwright"
    shells = root.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell")
    return [str(p) for p in sorted(shells, key=lambda p: p.parts[-3], reverse=True)]

def export_pdf(html_path: Path) -> Path | None:
    browsers = [b for b in [find_browser_binary(), *find_headless_shells()] if b]
    if not browsers:
        print("⚠ No Chrome/Chromium/Brave found. Skipping PDF export.")
        return None
    pdf_path = html_path.with_suffix(".pdf")
    print("⏳ Exporting PDF...")
    for browser in browsers:
        pdf_path.unlink(missing_ok=True)
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
               f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header", "--no-pdf-header-footer",
               str(html_path.resolve())]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        except Exception as e:
            print(f"⚠ PDF export with {Path(browser).name} failed: {e}")
            continue
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            print(f"✓ PDF saved: {pdf_path} ({Path(browser).name})")
            return pdf_path
        print(f"⚠ {Path(browser).name} ran but made no PDF; trying the next browser.")
    print("⚠ PDF export failed with every browser.")
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
    # --number N rebuilds workbook N (same problems, words and article as
    # before); with no number, the next workbook in the progression is built.
    global WORKBOOK_NUM
    WORKBOOK_NUM = progression.next_number()
    if "--number" in sys.argv:
        idx = sys.argv.index("--number")
        try:
            WORKBOOK_NUM = int(sys.argv[idx + 1])
            if not 1 <= WORKBOOK_NUM <= progression.next_number():
                raise ValueError
        except (IndexError, ValueError):
            print(f"✗ --number needs a workbook from 1 to {progression.next_number()} (the next new one)")
            return 1
    # --no-open: don't open Preview, and exit non-zero if no PDF was made
    no_open = "--no-open" in sys.argv

    print(f"\n🖍  Workbook Generator — Whimsical Edition")
    print(f"   {workbook_label()}\n")

    try:
        wb = generate_workbook_content()
        print("✓ Content generated")
    except Exception as e:
        print(f"✗ Generation failed: {e}"); traceback.print_exc(); return 1

    try:
        update_hsk_progress(
            progress=wb.get("_progress") or load_hsk_progress(),
            day_num=wb["day_num"], today_pack=wb["_hsk_internal"],
        )
        print("✓ HSK progress updated")
    except Exception as e:
        print(f"⚠ HSK progress update failed: {e}"); traceback.print_exc()

    try:
        html_path = save_workbook_html(wb)
        progression.mark_built(wb["day_num"])
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
            # wkhtmltopdf ignores @page margin boxes, so number pages its own way
            'footer-right': f'{page_footer_label()} · [page] / [topage]',
            'footer-font-size': '7',
            'footer-spacing': '1',
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
