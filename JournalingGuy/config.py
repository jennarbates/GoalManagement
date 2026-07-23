"""Config handling for the journaling CLI."""
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".journal_cli"
CONFIG_PATH = CONFIG_DIR / "config.json"
DB_PATH = CONFIG_DIR / "journal.db"

DEFAULT_CONFIG = {
    "model_id": "mlx-community/LFM2-8B-A1B-8bit-MLX",  # any mlx-lm compatible model
    "trust_remote_code": False,
    "max_tokens": 600,
    "persona": (
        "You are a warm, perceptive journaling companion. You ask short, "
        "open-ended reflection questions -- never more than one at a time. "
        "You are not a therapist and never diagnose. You gently notice "
        "patterns over time (recurring stressors, values, goals, moods) and "
        "use them to ask better, more personal questions, but you do not "
        "lecture or give unsolicited advice unless asked. You keep replies "
        "brief -- a sentence or two -- so the person does most of the writing."
    ),
    "max_followups": 2,   # how many follow-up questions per session, max
    "memory_update_every_n_entries": 1,  # refine memory after every N sessions
    "ask_mood": True,     # quick 1-10 mood check-in at the end of each session
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_config_dir()
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    # backfill any missing keys from defaults (handles upgrades)
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def save_config(cfg):
    ensure_config_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def set_value(key, value):
    cfg = load_config()
    if key not in DEFAULT_CONFIG:
        raise KeyError(f"Unknown config key: {key}. Valid keys: {list(DEFAULT_CONFIG)}")
    cfg[key] = value
    save_config(cfg)
    return cfg
