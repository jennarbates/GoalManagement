# journal-cli

A daily reflection / journaling CLI backed by a **local** LLM (MLX, running
in-process — no server, no network calls). It asks you dynamic, open-ended
questions, has a short back-and-forth if useful, tags themes, logs a quick
mood check-in, and saves everything. Over time it distills a private
"memory" of your recurring themes, values, and goals, and surfaces trends
through `stats` and `digest`.

Everything is stored locally in SQLite (`~/.journal_cli/journal.db`).

## 1. Install

```bash
cd journal-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`mlx-lm` requires Apple Silicon. Pick any chat-capable model from the
[mlx-community](https://huggingface.co/mlx-community) org on Hugging Face —
the default is `mlx-community/LFM2-8B-A1B-8bit-MLX`, but anything in the
7-8B+ range will give noticeably better, more natural questions than very
small models. Change it any time with `python main.py config model_id <id>`.

## 2. Use it

```bash
python main.py today            # start (or continue) today's session
python main.py history --days 7 # review recent entries
python main.py memory           # see what it has learned about you so far
python main.py stats --days 7   # mood trend, streaks, top themes -- no LLM call, instant
python main.py digest --days 7  # stats + an LLM-written weekly check-in note
python main.py config           # view current settings
python main.py config model_id mlx-community/Llama-3.1-8B-Instruct-4bit
```

Tip: alias it for convenience —
```bash
alias journal="python /path/to/journal-cli/main.py"
```
then just run `journal` each day.

## What happens during a session

1. It loads your memory profile + last few entries as quiet context.
2. The LLM asks one opening question, tailored by that context.
3. You answer (multi-line; blank line or `/done` to finish). It may ask up
   to `max_followups` short follow-ups, then wraps up.
4. You get a quick "mood right now, 1-10" prompt (press enter to skip).
5. The LLM tags the entry with 2-5 short themes (e.g. "work stress",
   "gratitude") for later analysis.
6. Everything's saved, and your memory profile is refreshed.

## Analysis: `stats` and `digest`

- **`stats`** is instant, no LLM call: entry count, days written, current
  and longest streaks, a mood sparkline (`▁▂▃▄▅▆▇█`), average mood, words
  written, and your most common themes over the period.
- **`digest`** runs `stats` and then asks the LLM to write a short, warm
  check-in note — not just restating numbers, but noticing what actually
  seems to be going on, with one gentle observation and one open question
  for the week ahead.

Both take `--days N` (default 7) so you can look at a day, a week, a month.

## How the "understanding you over time" part works

- After every session (configurable via `memory_update_every_n_entries`),
  the LLM merges the new entry into a running bullet-point profile:
  recurring stressors, values, goals, emotional patterns, and anything
  you've explicitly asked it to remember.
- That profile (never shown to you unless you run `memory`) quietly feeds
  the system prompt on future sessions, so questions get more specific to
  you rather than generic ("What's one thing weighing on you from the
  project deadline you mentioned?" instead of "How was your day?").
- Mood scores and tags accumulate separately in the `entries` table
  specifically so `stats`/`digest` can spot trends without needing the LLM
  to re-read your whole journal every time.

## Customizing the persona

Edit `persona` in `~/.journal_cli/config.json` (created on first run) if you
want a different tone — more Stoic, more casual, more coach-like, etc.

## A note on privacy & wellbeing

This tool is a reflection aid, not a therapist, and it says so in its own
system prompt. If entries surface something heavier than journaling can
hold, it's worth talking to a person — a friend, or a professional.
