"""Check the CS311 question bank (cs311_problems.json) or one topic file.

    python3 test_cs311_bank.py                 # the whole bank
    python3 test_cs311_bank.py topic.json ...  # topic files ({"key", "name", ..., "problems", "practice"})

Every question is problems[i] + practice[i] and is printed as:

  1. warm-up      a 1-minute check that primes the one idea the question needs
  2. walk         4-8 small steps, each a short bit of text beside its own picture
  3. why / tip    why the method works
  4. on your own  practice[i]: a picture to mark up, a hint, and a full answer

Exits non-zero and lists every problem it finds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cs311_visuals  # noqa: E402

MIN_STEPS, MAX_STEPS = 4, 8
MAX_SAY_WORDS = 70        # one step's text: short enough to take in at a glance
MAX_STEP_PIC_W = 420      # step pictures print beside their text, so keep them narrow
REQUIRED_KEYS = ["stable-matching", "analysis", "graphs", "greedy", "divide-and-conquer",
                 "dynamic-programming", "network-flow", "intractability", "approximation",
                 "randomized"]


def _visual(errs, where, spec, max_w=None):
    if not isinstance(spec, dict) or not spec.get("type"):
        errs.append(f"{where}: missing visual")
        return
    try:
        cs311_visuals.render(spec)
        w, _ = cs311_visuals.size_of(spec)
    except Exception as e:  # noqa: BLE001
        errs.append(f"{where}: visual does not render: {e}")
        return
    if max_w and w > max_w:
        errs.append(f"{where}: picture is {w}px wide, keep it under {max_w}px")


def _text(errs, where, value, max_words=None):
    if not isinstance(value, str) or not value.strip():
        errs.append(f"{where}: missing text")
    elif max_words and len(value.split()) > max_words:
        errs.append(f"{where}: {len(value.split())} words, keep it under {max_words}")


def check_topic(t: dict) -> list[str]:
    errs: list[str] = []
    key = t.get("key", "?")
    for k in ("key", "name", "chapter", "lectures", "intro", "problems", "practice"):
        if k not in t:
            errs.append(f"{key}: missing {k}")
    P, Q = t.get("problems", []), t.get("practice", [])
    if len(P) != len(Q):
        errs.append(f"{key}: {len(P)} problems but {len(Q)} practice")
    for i, p in enumerate(P, 1):
        w = f"{key} Q{i}"
        for k in ("title", "problem", "why"):
            _text(errs, f"{w} {k}", p.get(k))
        _visual(errs, f"{w} setup visual", p.get("visual"))
        warm = p.get("warmup") or {}
        _text(errs, f"{w} warmup.question", warm.get("question"), 60)
        _text(errs, f"{w} warmup.answer", warm.get("answer"), 60)
        if warm.get("visual"):
            _visual(errs, f"{w} warmup visual", warm["visual"])
        walk = p.get("walk") or []
        if not MIN_STEPS <= len(walk) <= MAX_STEPS:
            errs.append(f"{w}: walk has {len(walk)} steps, want {MIN_STEPS}-{MAX_STEPS}")
        for j, st in enumerate(walk, 1):
            _text(errs, f"{w} step {j} say", st.get("say"), MAX_SAY_WORDS)
            _visual(errs, f"{w} step {j}", st.get("visual"), MAX_STEP_PIC_W)
            if st.get("look") is not None:
                _text(errs, f"{w} step {j} look", st.get("look"), 25)
        for k in ("steps", "walkthrough"):
            if k in p:
                errs.append(f"{w}: drop the old '{k}' key (walk replaces it)")
    for i, q in enumerate(Q, 1):
        w = f"{key} practice {i}"
        _text(errs, f"{w} problem", q.get("problem"))
        _text(errs, f"{w} answer", q.get("answer"))
        _text(errs, f"{w} hint", q.get("hint"), 40)
        _visual(errs, f"{w} visual", q.get("visual"))
    return errs


def main(argv: list[str]) -> int:
    if argv:
        topics = [json.loads(Path(a).read_text(encoding="utf-8")) for a in argv]
    else:
        topics = json.loads((HERE / "cs311_problems.json").read_text(encoding="utf-8"))["topics"]
        keys = [t.get("key") for t in topics]
        if keys != REQUIRED_KEYS:
            print(f"topic keys or order changed: {keys}")
            return 1
    errs = [e for t in topics for e in check_topic(t)]
    for e in errs:
        print(e)
    n = sum(len(t.get("problems", [])) for t in topics)
    print(f"{len(errs)} problem(s) in {len(topics)} topic(s), {n} questions")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
