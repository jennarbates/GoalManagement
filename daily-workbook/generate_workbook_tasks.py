#!/usr/bin/env python3
"""Generate workbook_tasks.json from GoalManagement certification curriculum.

Run this to (re)generate upcoming study tasks for the receipt printer, then
use taskprinter.py to print them:

  python generate_workbook_tasks.py
  python vibeCode/taskprinter.py print-window \\
      --file workbook_tasks.json --printer <your-printer> --days 1

Curriculum data is kept in sync with dailyWorkbookLocal.py by hand.
"""
from __future__ import annotations

import argparse
import json
import os
import unicodedata
from datetime import date, timedelta

# ── Curriculum (keep in sync with dailyWorkbookLocal.py) ─────────────────────

CERT_START = date(2026, 5, 12)

PCAP_CURRICULUM = [
    ("Modules & Packages, Lesson 1", "Import syntax: import, from ... import, import ... as, import *"),
    ("Modules & Packages, Lesson 2", "The __name__ variable and __main__ guard"),
    ("Modules & Packages, Lesson 3", "sys.path and how Python finds modules"),
    ("Modules & Packages, Lesson 4", "Standard library: math module"),
    ("Modules & Packages, Lesson 5", "Standard library: random module"),
    ("Modules & Packages, Lesson 6", "Standard library: platform module"),
    ("Modules & Packages, Lesson 7", "Packages and __init__.py"),
    ("Modules & Packages, Lesson 8", "Installing packages with pip"),
    ("Modules & Packages, Lesson 9", "Python Package Index (PyPI)"),
    ("Exceptions, Lesson 1", "try / except basics"),
    ("Exceptions, Lesson 2", "Multiple except clauses and catching by type"),
    ("Exceptions, Lesson 3", "The exception hierarchy: BaseException and Exception"),
    ("Exceptions, Lesson 4", "raise and raise ... from"),
    ("Exceptions, Lesson 5", "Defining custom exception classes"),
    ("Exceptions, Lesson 6", "The assert statement"),
    ("Exceptions, Lesson 7", "The finally clause and else on try"),
    ("Strings, Lesson 1", "String encoding, ASCII table, ord() and chr()"),
    ("Strings, Lesson 2", "Case methods: upper, lower, title, capitalize, swapcase"),
    ("Strings, Lesson 3", "Search methods: find, rfind, index, rindex, startswith, endswith, count"),
    ("Strings, Lesson 4", "Edit methods: replace, split, rsplit, join"),
    ("Strings, Lesson 5", "Padding methods: strip, lstrip, rstrip, center, ljust, rjust, zfill"),
    ("Strings, Lesson 6", "String formatting: % operator"),
    ("Strings, Lesson 7", "String formatting: .format() and f-strings"),
    ("OOP, Lesson 1",  "Classes and objects: class keyword, instantiation"),
    ("OOP, Lesson 2",  "Instance variables and the __init__ method"),
    ("OOP, Lesson 3",  "Class variables vs instance variables"),
    ("OOP, Lesson 4",  "Methods and self; __str__ and __repr__"),
    ("OOP, Lesson 5",  "Properties: @property, setter, deleter"),
    ("OOP, Lesson 6",  "Inheritance basics and method overriding"),
    ("OOP, Lesson 7",  "super() and cooperative inheritance"),
    ("OOP, Lesson 8",  "Multiple inheritance and MRO (Method Resolution Order)"),
    ("OOP, Lesson 9",  "isinstance() and issubclass()"),
    ("OOP, Lesson 10", "Magic methods: __eq__, __lt__, __gt__, __add__, __len__"),
    ("OOP, Lesson 11", "Abstract classes and @abstractmethod"),
    ("Miscellaneous, Lesson 1", "Generators and the yield statement"),
    ("Miscellaneous, Lesson 2", "Iterators: __iter__ and __next__"),
    ("Miscellaneous, Lesson 3", "List comprehensions"),
    ("Miscellaneous, Lesson 4", "Dictionary and set comprehensions"),
    ("Miscellaneous, Lesson 5", "Lambda functions"),
    ("Miscellaneous, Lesson 6", "Closures"),
    ("Miscellaneous, Lesson 7", "map(), filter(), sorted(), reversed()"),
    ("Miscellaneous, Lesson 8", "The os.path module"),
    ("Miscellaneous, Lesson 9", "The datetime module"),
    ("Miscellaneous, Lesson 10", "Practice exam: full timed run-through"),
]

MATH_ML_CURRICULUM = [
    ("Linear Algebra, Week 1, Lesson 1", "Introduction to linear algebra and its role in ML"),
    ("Linear Algebra, Week 1, Lesson 2", "Vectors: what they are and basic operations"),
    ("Linear Algebra, Week 1, Lesson 3", "Vector addition and scalar multiplication"),
    ("Linear Algebra, Week 2, Lesson 1", "Modulus (magnitude) and inner product (dot product)"),
    ("Linear Algebra, Week 2, Lesson 2", "Projections and changing basis"),
    ("Linear Algebra, Week 2, Lesson 3", "Linear independence"),
    ("Linear Algebra, Week 3, Lesson 1", "Matrix operations: addition and multiplication"),
    ("Linear Algebra, Week 3, Lesson 2", "Matrix transformations in 2D"),
    ("Linear Algebra, Week 3, Lesson 3", "Gaussian elimination and solving linear systems"),
    ("Linear Algebra, Week 4, Lesson 1", "The inverse matrix"),
    ("Linear Algebra, Week 4, Lesson 2", "Determinants"),
    ("Linear Algebra, Week 4, Lesson 3", "Eigenvalues and eigenvectors: intuition"),
    ("Linear Algebra, Week 4, Lesson 4", "Eigenvalues and eigenvectors: computation"),
    ("Linear Algebra, Week 4, Lesson 5", "Special matrices: identity, diagonal, symmetric"),
    ("Multivariate Calculus, Week 1, Lesson 1", "What is calculus? Limits and derivatives"),
    ("Multivariate Calculus, Week 1, Lesson 2", "Differentiation rules: product rule, chain rule"),
    ("Multivariate Calculus, Week 1, Lesson 3", "Taylor series in one variable"),
    ("Multivariate Calculus, Week 2, Lesson 1", "Multivariate functions and partial derivatives"),
    ("Multivariate Calculus, Week 2, Lesson 2", "The Jacobian matrix"),
    ("Multivariate Calculus, Week 2, Lesson 3", "The Hessian matrix"),
    ("Multivariate Calculus, Week 3, Lesson 1", "The multivariate chain rule"),
    ("Multivariate Calculus, Week 3, Lesson 2", "Neural networks and backpropagation via the chain rule"),
    ("Multivariate Calculus, Week 4, Lesson 1", "Taylor series in multiple dimensions"),
    ("Multivariate Calculus, Week 4, Lesson 2", "Linearisation and approximation"),
    ("Multivariate Calculus, Week 5, Lesson 1", "Gradient descent: intuition and algorithm"),
    ("Multivariate Calculus, Week 5, Lesson 2", "Gradient descent in higher dimensions"),
    ("Multivariate Calculus, Week 6, Lesson 1", "Regression: fitting a straight line"),
    ("Multivariate Calculus, Week 6, Lesson 2", "Regression: non-linear and general models"),
    ("PCA, Week 1, Lesson 1", "Statistics of datasets: mean and variance"),
    ("PCA, Week 1, Lesson 2", "Covariance and correlation"),
    ("PCA, Week 2, Lesson 1", "Inner products"),
    ("PCA, Week 2, Lesson 2", "Inner product spaces and their properties"),
    ("PCA, Week 3, Lesson 1", "Orthogonal projections"),
    ("PCA, Week 3, Lesson 2", "Orthonormal bases"),
    ("PCA, Week 4, Lesson 1", "PCA: finding principal components"),
    ("PCA, Week 4, Lesson 2", "PCA: dimensionality reduction in practice"),
]

MATH_PORTFOLIO_PROJECTS = [
    ("Vector operations visualizer",   "add, subtract, scalar multiply, dot product; plot with matplotlib arrows"),
    ("Matrix multiplication step-by-step", "show each row x col step; print intermediate results"),
    ("Gradient descent animator",      "minimise f(x)=x^2+2x+1; plot loss curve and path of x"),
    ("Eigenvalue explorer",            "2x2 matrix; compute eigenvalues/vectors; visualise transformation"),
    ("Linear regression from scratch", "least-squares via normal equation; plot data + fit line"),
    ("PCA from scratch",               "covariance matrix, eigen-decompose, project 2D to 1D; visualise"),
    ("Gaussian elimination solver",    "row reduction with partial pivoting; print each step"),
    ("Taylor series approximation",    "plot sin/e^x/cos with N=1,3,5 term approximations"),
    ("Monte Carlo pi estimator",       "random point sampling to estimate pi; plot convergence"),
    ("Numerical differentiation",      "forward, backward, central difference; compare to true derivative"),
    ("Gradient field visualiser",      "quiver plot of grad-f for x^2+y^2 and sin(x)cos(y)"),
    ("Covariance & correlation explorer", "correlated datasets; covariance matrix heatmap"),
    ("Backpropagation by hand",        "tiny 1-hidden-layer network; manual gradients vs finite differences"),
    ("Markov chain simulator",         "weather chain (sunny/rainy); simulate 100 steps; plot distribution"),
    ("Fourier series visualiser",      "approximate square wave with N terms; animate N=1 to 20"),
    ("Power method for eigenvalues",   "power iteration; show convergence to dominant eigenvalue"),
    ("Numerical integration",          "Riemann, trapezoid, Simpson on integral of sin(x) 0 to pi"),
    ("Logistic regression from scratch", "sigmoid + cross-entropy + gradient descent; plot decision boundary"),
    ("SVD image compression",          "apply SVD to grayscale image; reconstruct with k=5,20,50"),
    ("Hessian & critical points",      "f(x,y)=x^3-3xy+y^3; compute Hessian; find/classify critical points"),
]

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

HSK_PROGRESS_PATH = os.path.expanduser("~/Documents/daily-workbook/hsk1_progress.json")
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

    pcap_section, pcap_desc = PCAP_CURRICULUM[(cday - 1) % len(PCAP_CURRICULUM)]
    math_section, math_desc = MATH_ML_CURRICULUM[(cday - 1) % len(MATH_ML_CURRICULUM)]
    portfolio_title, portfolio_desc = MATH_PORTFOLIO_PROJECTS[(cday - 1) % len(MATH_PORTFOLIO_PROJECTS)]

    hsk_label = practice_char_for_day(d, hsk_progress)

    items = [
        {
            "id": f"pcap-{date_str}",
            "type": "assignment",
            "course": "PCAP",
            "title": pcap_section,
            "due": date_str,
            "all_day": True,
        },
        {
            "id": f"math-ml-{date_str}",
            "type": "assignment",
            "course": "Math for ML",
            "title": math_section,
            "due": date_str,
            "all_day": True,
        },
        {
            "id": f"portfolio-{date_str}",
            "type": "project",
            "course": "Portfolio",
            "title": portfolio_title,
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
