"""Analysis over saved entries: mood trends, streaks, recurring themes, and
an LLM-written narrative digest that ties the numbers back to what was
actually written.
"""
from collections import Counter
from datetime import date, timedelta

from llm_client import generate_text
import memory as memory_mod

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _entry_date(entry):
    return date.fromisoformat(entry["timestamp"][:10])


def sparkline(values):
    """values: list of numbers (e.g. mood 1-10, None allowed for gaps)."""
    present = [v for v in values if v is not None]
    if not present:
        return ""
    lo, hi = min(present), max(present)
    span = (hi - lo) or 1
    chars = []
    for v in values:
        if v is None:
            chars.append("·")
            continue
        idx = int(((v - lo) / span) * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    return "".join(chars)


def compute_streaks(all_entries):
    """Current streak = consecutive days up to today/yesterday with an entry.
    Longest streak = longest run of consecutive days with an entry, all-time."""
    days = sorted({_entry_date(e) for e in all_entries})
    if not days:
        return 0, 0

    # longest streak
    longest = 1
    run = 1
    for i in range(1, len(days)):
        if (days[i] - days[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    # current streak: walk backward from today (allow "today not yet logged")
    day_set = set(days)
    today = date.today()
    cursor = today if today in day_set else today - timedelta(days=1)
    current = 0
    while cursor in day_set:
        current += 1
        cursor -= timedelta(days=1)

    return current, longest


def compute_stats(entries, period_label="period"):
    n = len(entries)
    moods = [e["mood_score"] for e in entries]
    mood_present = [m for m in moods if m is not None]
    avg_mood = round(sum(mood_present) / len(mood_present), 1) if mood_present else None

    tag_counter = Counter()
    for e in entries:
        tag_counter.update(e.get("tags") or [])

    word_counts = [e.get("word_count") or 0 for e in entries]
    total_words = sum(word_counts)
    avg_words = round(total_words / n, 0) if n else 0

    days_covered = len({_entry_date(e) for e in entries})

    return {
        "period_label": period_label,
        "entry_count": n,
        "days_covered": days_covered,
        "avg_mood": avg_mood,
        "mood_trend": [(e["timestamp"][:10], e["mood_score"]) for e in entries],
        "tag_counts": tag_counter,
        "total_words": total_words,
        "avg_words_per_entry": avg_words,
    }


def format_stats_report(stats, current_streak, longest_streak):
    lines = []
    lines.append(f"📊 {stats['period_label']}")
    lines.append(f"   Entries: {stats['entry_count']}  ·  Days written: {stats['days_covered']}")
    lines.append(f"   Current streak: {current_streak} day(s)  ·  Longest streak: {longest_streak} day(s)")

    if stats["avg_mood"] is not None:
        moods = [m for _, m in stats["mood_trend"]]
        lines.append(f"   Avg mood: {stats['avg_mood']}/10   {sparkline(moods)}")
    else:
        lines.append("   Avg mood: (no mood check-ins logged yet)")

    lines.append(f"   Words written: {stats['total_words']} total  ·  ~{int(stats['avg_words_per_entry'])} per entry")

    if stats["tag_counts"]:
        top = stats["tag_counts"].most_common(8)
        tag_line = ", ".join(f"{tag} ({n})" for tag, n in top)
        lines.append(f"   Top themes: {tag_line}")
    else:
        lines.append("   Top themes: (none tagged yet)")

    return "\n".join(lines)


DIGEST_PROMPT = """You are a thoughtful journaling companion writing a short weekly \
check-in note for someone based on their entries and stats below. Do NOT just restate the \
numbers -- notice what actually seems to be going on, in a warm, grounded, non-clinical way. \
Mention at most one gentle observation or pattern, and end with one open question for the \
week ahead. Keep it to 4-6 sentences total. No headers, no bullet points, no diagnosis.

STATS:
- Entries this period: {entry_count} (over {days_covered} distinct days)
- Average mood: {avg_mood}
- Most common themes: {top_tags}
- Total words written: {total_words}

RECENT ENTRIES:
{entries_text}

Write the check-in note now, directly addressed to the person ("you")."""


def build_digest_narrative(entries, stats, model_id, trust_remote_code=False):
    if not entries:
        return "No entries in this period yet -- nothing to reflect on just yet."

    top_tags = ", ".join(t for t, _ in stats["tag_counts"].most_common(5)) or "none tagged"
    prompt = DIGEST_PROMPT.format(
        entry_count=stats["entry_count"],
        days_covered=stats["days_covered"],
        avg_mood=f"{stats['avg_mood']}/10" if stats["avg_mood"] is not None else "not logged",
        top_tags=top_tags,
        total_words=stats["total_words"],
        entries_text=memory_mod.format_entries_for_prompt(entries),
    )
    return generate_text(
        [{"role": "user", "content": prompt}],
        model_id, max_tokens=350, trust_remote_code=trust_remote_code,
    )
