#!/usr/bin/env python3
"""A daily reflection / journaling CLI backed by a local MLX LLM.

Usage:
    python main.py today                Start (or continue) today's journaling session
    python main.py history [--days N]   Show recent entries
    python main.py memory               Show what the companion has learned about you
    python main.py stats [--days N]     Quick analytics: mood trend, streaks, top themes
    python main.py digest [--days N]    Stats + an LLM-written weekly check-in note
    python main.py config               Show current config
    python main.py config KEY VALUE     Update a config value
"""
import argparse
import sys
import textwrap
from datetime import date, timedelta

import config as cfgmod
import storage
import memory
import analysis
from llm_client import generate_text, generate_json, LLMError


def multiline_input(prompt_label="You"):
    print(f"\n{prompt_label} (type on one or more lines; enter an empty line, or /done, to finish):")
    lines = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip() == "/done":
            break
        if line == "" and lines:
            break
        if line == "" and not lines:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def ask_mood():
    while True:
        raw = input("\nQuick check-in -- mood right now, 1-10 (or blank to skip): ").strip()
        if raw == "":
            return None
        try:
            val = int(raw)
            if 1 <= val <= 10:
                return val
        except ValueError:
            pass
        print("Enter a whole number 1-10, or just press enter to skip.")


def wrap(text, width=88):
    return "\n".join(textwrap.fill(p, width=width) for p in text.split("\n"))


def run_session(cfg):
    mem = storage.get_memory_summary()
    recent = storage.get_recent_entries(n=7)

    base_persona = memory.build_system_prompt(cfg["persona"], mem["summary"])
    
    # Updated Persona: Practical, action-oriented daily coach
    system_prompt = base_persona + (
        "\n\nYou are a practical, action-oriented daily coach and reflection guide. "
        "Your goal is to help the user translate their feelings, past goals, and recent trends into a clear, "
        "actionable goal for today. "
        "Rules:\n"
        "- Ask ONE short, practical follow-up question based on their last response.\n"
        "- Guide the user to break vague intentions into specific, manageable action items.\n"
        "- Keep the tone grounded, momentum-focused, and supportive.\n"
        "- Do NOT close the session prematurely. Wait for the user to initiate the end of the session."
    )
    
    messages = [{"role": "system", "content": system_prompt}]

    if recent:
        recent_moods = [str(e["mood_score"]) for e in recent if e.get("mood_score") is not None]
        mood_context = f"Their recent mood scores (1-10): {', '.join(recent_moods)}." if recent_moods else ""
        
        context_note = (
            f"Context: {mood_context}\n"
            f"Here are their recent journal entries. Pay close attention to their past goals, "
            f"struggles, and themes so you can help them build on them today:\n\n"
            + memory.format_entries_for_prompt(recent)
        )
        messages.append({"role": "user", "content": context_note})
        messages.append({"role": "assistant", "content": "Understood. I will help them set a focused, practical goal for today."})

    messages.append({
        "role": "user",
        "content": (
            "Start today's session: Acknowledge their recent mood/themes (if relevant), and ask ONE opening "
            "question to help them define a concrete, actionable goal for today based on how they are "
            "feeling right now."
        )
    })

    print("\n" + "=" * 70)
    print(" Today's Action Plan & Reflection")
    print("=" * 70)

    try:
        opening = generate_text(messages, cfg["model_id"], max_tokens=cfg["max_tokens"],
                                 trust_remote_code=cfg["trust_remote_code"])
    except LLMError as e:
        print(f"\n[Error] {e}")
        sys.exit(1)

    conversation = []
    print(f"\n🖊  {wrap(opening)}")
    conversation.append({"role": "assistant", "content": opening})
    messages.append({"role": "assistant", "content": opening})

    # Continuous loop
    while True:
        answer = multiline_input()
        if not answer:
            print("\n(Wrapping up your session...)")
            break
            
        conversation.append({"role": "user", "content": answer})
        messages.append({"role": "user", "content": answer})

        # Keep probing for actions
        messages.append({
            "role": "system",
            "content": "Continue the reflection. Keep digging for a concrete action item. Do not close the session."
        })
        
        try:
            reply = generate_text(messages, cfg["model_id"], max_tokens=cfg["max_tokens"],
                                   trust_remote_code=cfg["trust_remote_code"])
        except LLMError as e:
            print(f"\n[Error] {e}")
            break

        messages.pop() # Remove the system instruction

        conversation.append({"role": "assistant", "content": reply})
        messages.append({"role": "assistant", "content": reply})

        print(f"\n🖊  {wrap(reply)}")

    # Mood check-in happens after the loop breaks
    mood_score = ask_mood() if cfg.get("ask_mood", True) else None

    print("\n(Tagging today's themes...)")
    tag_result = generate_json(
        memory.build_tag_prompt(conversation),
        cfg["model_id"],
        required_keys=["tags"],
        fallback={"tags": []},
        max_tokens=150,
        trust_remote_code=cfg["trust_remote_code"],
    )
    tags = [t.strip().lower() for t in tag_result.get("tags", []) if isinstance(t, str)][:5]

    storage.save_entry(conversation, mood_score=mood_score, tags=tags)

    summary_bits = []
    if mood_score is not None:
        summary_bits.append(f"mood {mood_score}/10")
    if tags:
        summary_bits.append("tags: " + ", ".join(tags))
    footer = "  ·  ".join(summary_bits)
    print(f"\n(Saved to your journal.{'  ' + footer if footer else ''})")

    n = storage.count_entries()
    every_n = cfg.get("memory_update_every_n_entries", 1)
    if every_n > 0 and n % every_n == 0:
        print("\n(Updating what I understand about you so far...)")
        new_entries = storage.get_recent_entries(n=every_n)
        try:
            updated = memory.update_memory_summary(
                mem["summary"], new_entries, cfg["model_id"], cfg["trust_remote_code"]
            )
            storage.save_memory_summary(updated)
        except LLMError as e:
            print(f"[Note] Couldn't update memory summary: {e}")


def show_history(days):
    since = date.today() - timedelta(days=days)
    entries = storage.get_entries_since(since)
    if not entries:
        print("No entries yet. Run `python main.py today` to start.")
        return
    for e in entries:
        print("\n" + "-" * 70)
        header = e["timestamp"]
        if e["mood_score"] is not None:
            header += f"   ·   mood {e['mood_score']}/10"
        if e["tags"]:
            header += "   ·   " + ", ".join(e["tags"])
        print(header)
        print("-" * 70)
        print(wrap(memory.format_conversation(e["conversation"])))


def show_memory():
    mem = storage.get_memory_summary()
    if not mem["summary"]:
        print("No memory built up yet -- it forms after your first session.")
        return
    print(f"Last updated: {mem['updated_at']}\n")
    print(mem["summary"])


def show_stats(days):
    since = date.today() - timedelta(days=days)
    entries = storage.get_entries_since(since)
    all_entries = storage.get_all_entries()
    if not entries:
        print(f"No entries in the last {days} day(s). Run `python main.py today` to start.")
        return
    stats = analysis.compute_stats(entries, period_label=f"Last {days} days")
    current_streak, longest_streak = analysis.compute_streaks(all_entries)
    print(analysis.format_stats_report(stats, current_streak, longest_streak))


def show_digest(cfg, days):
    since = date.today() - timedelta(days=days)
    entries = storage.get_entries_since(since)
    all_entries = storage.get_all_entries()
    if not entries:
        print(f"No entries in the last {days} day(s) to build a digest from.")
        return
    stats = analysis.compute_stats(entries, period_label=f"Last {days} days")
    current_streak, longest_streak = analysis.compute_streaks(all_entries)

    print(analysis.format_stats_report(stats, current_streak, longest_streak))
    print("\n" + "-" * 70)
    print("Weekly check-in")
    print("-" * 70)
    try:
        narrative = analysis.build_digest_narrative(
            entries, stats, cfg["model_id"], cfg["trust_remote_code"]
        )
        print(wrap(narrative))
    except LLMError as e:
        print(f"[Error building narrative] {e}")


def handle_config(key, value):
    if key is None:
        cfg = cfgmod.load_config()
        for k, v in cfg.items():
            print(f"{k}: {v}")
        return
    # coerce simple types for known boolean/int keys
    if value is not None:
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        else:
            try:
                value = int(value)
            except ValueError:
                pass
    cfg = cfgmod.set_value(key, value)
    print(f"Set {key} = {value}")


def main():
    parser = argparse.ArgumentParser(description="Daily reflection journal backed by a local MLX LLM.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("today", help="Start today's journaling session")

    hist = sub.add_parser("history", help="Show recent entries")
    hist.add_argument("--days", type=int, default=7)

    sub.add_parser("memory", help="Show what the companion has learned about you")

    st = sub.add_parser("stats", help="Mood trend, streaks, and top themes")
    st.add_argument("--days", type=int, default=7)

    dg = sub.add_parser("digest", help="Stats plus an LLM-written weekly check-in note")
    dg.add_argument("--days", type=int, default=7)

    conf = sub.add_parser("config", help="View or set config (model_id, persona, ...)")
    conf.add_argument("key", nargs="?", default=None)
    conf.add_argument("value", nargs="?", default=None)

    args = parser.parse_args()
    cfg = cfgmod.load_config()

    if args.command == "today" or args.command is None:
        run_session(cfg)
    elif args.command == "history":
        show_history(args.days)
    elif args.command == "memory":
        show_memory()
    elif args.command == "stats":
        show_stats(args.days)
    elif args.command == "digest":
        show_digest(cfg, args.days)
    elif args.command == "config":
        handle_config(args.key, args.value)


if __name__ == "__main__":
    main()
