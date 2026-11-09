#!/usr/bin/env python3
"""Workbook Bridge: a tiny local HTTP server between the Mac app and your
MLX model + daily-workbook scripts.

  * Listens on 127.0.0.1 only (never on your network).
  * Loads the model ONCE from the local Hugging Face cache, fully offline.
  * Blocks every outbound connection from this process (see offline_guard.py),
    except hosts you explicitly allow in Settings (only the weather lookup).
  * Reuses dailyWorkbookLocal.py and generate_workbook_tasks.py as-is, so the
    curriculum and HSK logic stay in one place.

The Mac app starts and stops this for you. To run it by hand:

    .venv/bin/python WorkbookApp/bridge/workbook_bridge.py --port 8765

Endpoints (JSON unless noted, streaming ones are newline-delimited JSON):

    GET  /health             model + guard status
    GET  /config             bridge settings
    POST /config             update settings
    GET  /today?date=        today's cards (CS311, HSK, chore)
    GET  /actions            lesson-help actions from actions.py
    POST /actions/run        run one action on a card        (stream)
    POST /chat               chat with the model              (stream)
    POST /workbook/generate  run dailyWorkbookLocal.py in-process (job)
    GET  /jobs/<id>          job status + log
    GET  /workbooks          past workbook files
    POST /tasks/generate     write workbook_tasks.json
    GET  /printers           CUPS printers + saved default
    POST /tasks/print        print (or preview) today's receipts
"""
from __future__ import annotations

# The guard must be imported before anything that could reach the network.
import offline_guard  # noqa: E402  (sets HF offline env vars on import)

import argparse
import contextlib
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BRIDGE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BRIDGE_DIR / "config.json"
sys.path.insert(0, str(BRIDGE_DIR))

import actions  # noqa: E402

DEFAULT_CONFIG = {
    "model_id": "",                 # empty = use LOCAL_MODEL_ID from dailyWorkbookLocal.py
    "allow_weather": False,         # lets ONLY api.weather.gov through, for the workbook
    "max_tokens": 1200,
    "temperature": 0.6,
    "system_prompt": (
        "You are a friendly, concise study companion running fully offline on "
        "the user's Mac. You help with CS311 algorithms (Kleinberg & Tardos), LeetCode practice, HSK 1 Chinese, "
        "and daily planning. Keep answers short unless asked for detail."
    ),
}
WEATHER_HOST = "api.weather.gov"


# ── State ─────────────────────────────────────────────────────────────────────

class State:
    root: Path
    cfg: dict
    dwl = None                     # dailyWorkbookLocal module
    gwt = None                     # generate_workbook_tasks module
    model = None
    tokenizer = None
    model_id = ""
    model_status = "not_loaded"    # not_loaded | loading | ready | error
    model_error = ""
    model_lock = threading.Lock()  # one generation at a time
    busy_reason = ""
    jobs: dict[str, dict] = {}
    token = os.environ.get("WORKBOOK_BRIDGE_TOKEN", "")


S = State()


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def apply_guard() -> None:
    offline_guard.install([WEATHER_HOST] if S.cfg.get("allow_weather") else [])


def import_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_project_modules() -> None:
    wb_dir = S.root / "daily-workbook"
    S.dwl = import_path("dailyWorkbookLocal", wb_dir / "workbooks" / "dailyWorkbookLocal.py")
    S.gwt = import_path("generate_workbook_tasks", wb_dir / "generate_workbook_tasks.py")


def load_model_async() -> None:
    def run():
        S.model_status, S.model_error = "loading", ""
        try:
            from mlx_lm import load
            mid = S.cfg.get("model_id") or getattr(S.dwl, "LOCAL_MODEL_ID", "")
            kwargs = {}
            if getattr(S.dwl, "TRUST_REMOTE_CODE", False):
                kwargs["tokenizer_config"] = {"trust_remote_code": True}
            t0 = time.time()
            model, tok = load(mid, **kwargs)
            S.model, S.tokenizer, S.model_id = model, tok, mid
            # Share the loaded model with dailyWorkbookLocal so workbook
            # generation does not load a second copy into memory.
            S.dwl._MODEL, S.dwl._TOKENIZER = model, tok
            S.model_status = "ready"
            print(f"[bridge] model ready: {mid} ({time.time() - t0:.1f}s)", flush=True)
        except Exception as e:  # noqa: BLE001
            S.model_status, S.model_error = "error", f"{type(e).__name__}: {e}"
            if isinstance(e, offline_guard.OfflineViolation) or "offline" in str(e).lower():
                S.model_error += (" (the model is not in your local cache; download it "
                                  "once while online, then the app runs offline)")
            traceback.print_exc()
    threading.Thread(target=run, daemon=True).start()


# ── Model helpers ─────────────────────────────────────────────────────────────

def format_prompt(messages: list[dict]):
    tok = S.tokenizer
    try:
        if getattr(tok, "chat_template", None) is not None:
            return tok.apply_chat_template(messages, add_generation_prompt=True)
    except Exception:  # noqa: BLE001
        pass
    lines = [f"{m['role'].upper()}: {m['content']}" for m in messages]
    return "\n\n".join(lines + ["ASSISTANT:"])


def stream_generate(messages, max_tokens, temperature, emit) -> None:
    """Run the model and call emit(dict) for each chunk. Stops early if emit raises."""
    from mlx_lm import stream_generate as mlx_stream
    kwargs = {"max_tokens": int(max_tokens)}
    try:
        from mlx_lm.sample_utils import make_sampler
        kwargs["sampler"] = make_sampler(temp=float(temperature))
    except Exception:  # noqa: BLE001
        pass
    prompt = format_prompt(messages)
    last = None
    t0 = time.time()
    for resp in mlx_stream(S.model, S.tokenizer, prompt, **kwargs):
        last = resp
        if resp.text:
            emit({"t": "token", "text": resp.text})
    emit({
        "t": "done",
        "tokens": getattr(last, "generation_tokens", None),
        "tps": round(getattr(last, "generation_tps", 0.0) or 0.0, 1),
        "seconds": round(time.time() - t0, 1),
    })


# ── Today ─────────────────────────────────────────────────────────────────────

def read_parking_lot() -> list[str]:
    p = S.root / "daily-workbook" / "parking_lot.txt"
    try:
        return [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")]
    except FileNotFoundError:
        return []


def today_payload(d: date) -> dict:
    dwl, gwt = S.dwl, S.gwt
    dtype = dwl.day_type(d.weekday())
    cday = gwt.cert_day_for(d)
    algo = dwl.cs311.daily_set(d) if dwl.cs311 else None
    chore = dwl.CHORE_SCHEDULE[d.weekday()]

    progress = dwl.load_hsk_progress()
    pack = dwl.choose_hsk_words_for_today(progress, d.isoformat())
    hsk_words = pack.get("lesson_words") or pack.get("new_words") or []
    practice = pack.get("char_practice") or {}

    cards = []
    if algo:
        cards.append({
            "id": f"cs311-{d}", "kind": "algorithms", "course": "CS311",
            "title": f"{algo['topic']} ({algo['chapter']})",
            "detail": "Worked: " + "; ".join(p["title"] for p in algo["worked"]),
            "url": "https://people.cs.umass.edu/~sheldon/teaching/cs311/index.html"})
    lcmod = getattr(dwl, "leetcode", None)
    lc = lcmod.daily_set(d, mark=False) if lcmod else None
    if lc and lc.get("problem"):
        p = lc["problem"]
        cards.append({
            "id": f"leetcode-{d}", "kind": "leetcode", "course": "LeetCode",
            "title": f"#{p['lc']} {p['title']}",
            "detail": f"{lc['level'].title()} · {p['pattern']}. {p['statement']}",
            "url": f"https://leetcode.com/problems/{p['slug']}/"})
    cards += [
        {"id": f"hsk-{d}", "kind": "hsk", "course": "HSK 1",
         "title": f"Practice: {practice.get('char', '')} {practice.get('pinyin', '')}".strip(),
         "detail": f"New: {', '.join(w['char'] for w in pack.get('new_words', [])) or 'none'}",
         "url": "", "words": hsk_words},
        {"id": f"chore-{d}", "kind": "chore", "course": "Chore",
         "title": chore[0], "detail": f"{chore[1]} ({chore[2]})", "url": ""},
    ]
    for c in cards:
        c["day_type"] = dtype
    return {
        "date": d.isoformat(),
        "label": d.strftime("%A, %B %-d"),
        "day_type": dtype,
        "cert_day": cday,
        "cards": cards,
        "parking_lot": read_parking_lot(),
    }


# ── Jobs (long-running tasks with a log) ──────────────────────────────────────

class JobLog:
    def __init__(self, job: dict):
        self.job = job

    def write(self, s: str) -> int:
        if s:
            self.job["log"] += s
        return len(s)

    def flush(self) -> None:
        pass


def start_workbook_job() -> dict:
    job = {"id": uuid.uuid4().hex[:8], "kind": "workbook", "status": "running",
           "log": "", "started": datetime.now().isoformat(timespec="seconds"),
           "result": {}}
    S.jobs[job["id"]] = job

    def run():
        with S.model_lock:
            S.busy_reason = "Generating workbook"
            log = JobLog(job)
            saved_argv = sys.argv
            try:
                sys.argv = [str(S.root / "daily-workbook" / "workbooks" / "dailyWorkbookLocal.py")]
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    S.dwl.main()
                stamp = datetime.now().strftime("%Y-%m-%d")
                html = Path(S.dwl.OUTPUT_DIR) / f"daily-workbook-{stamp}.html"
                job["result"] = {"html": str(html) if html.exists() else "",
                                 "pdf": str(html.with_suffix(".pdf")) if html.with_suffix(".pdf").exists() else ""}
                job["status"] = "done"
            except BaseException as e:  # noqa: BLE001  (also catches sys.exit inside the script)
                job["log"] += f"\n{type(e).__name__}: {e}\n{traceback.format_exc()}"
                job["status"] = "error"
            finally:
                sys.argv = saved_argv
                S.busy_reason = ""
    threading.Thread(target=run, daemon=True).start()
    return job


# ── Tasks + printing ──────────────────────────────────────────────────────────

def tasks_path() -> Path:
    return S.root / "daily-workbook" / "workbook_tasks.json"


def printer_file() -> Path:
    return S.root / "daily-workbook" / ".printer"


def generate_tasks(days: int) -> dict:
    gwt = S.gwt
    progress = gwt.load_hsk_progress()
    today = date.today()
    items = []
    for off in range(max(1, days)):
        items.extend(gwt.items_for_date(today + timedelta(days=off), progress))
    tasks_path().write_text(json.dumps({"timezone": "America/New_York", "items": items},
                                       indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(tasks_path()), "count": len(items), "items": items}


def list_printers() -> dict:
    names = []
    try:
        out = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.startswith("printer "):
                names.append(line.split()[1])
    except Exception:  # noqa: BLE001
        pass
    saved = ""
    try:
        saved = printer_file().read_text().strip()
    except FileNotFoundError:
        pass
    return {"printers": names, "saved": saved}


def print_tasks(printer: str, days: int, preview: bool, force: bool) -> dict:
    if not tasks_path().exists():
        generate_tasks(7)
    script = S.root / "TaskPrinter" / "taskprinter.py"
    cmd = [sys.executable, str(script), "print-window", "--file", str(tasks_path()),
           "--printer", printer or "preview", "--days", str(days)]
    if preview:
        cmd.append("--preview")
    if force:
        cmd.append("--force")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode == 0 and printer and not preview:
        printer_file().write_text(printer)
    return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()}


def list_workbooks() -> list[dict]:
    dirs = [Path(S.dwl.OUTPUT_DIR), S.root / "daily-workbook" / "workbooks"]
    found: dict[str, dict] = {}
    for d in dirs:
        if not d.exists():
            continue
        for p in d.glob("*workbook-*.*"):
            if p.suffix.lower() not in (".html", ".pdf"):
                continue
            key = p.stem.split("workbook-")[-1]
            entry = found.setdefault(key, {"date": key, "html": "", "pdf": ""})
            entry[p.suffix.lower().lstrip(".")] = str(p)
    return sorted(found.values(), key=lambda e: e["date"], reverse=True)


# ── HTTP ──────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "WorkbookBridge/1.0"

    def log_message(self, *args):  # keep stdout clean
        pass

    # helpers
    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _authorized(self) -> bool:
        # Browsers send Origin; the Mac app does not. This stops web pages
        # from poking the bridge through localhost.
        if self.headers.get("Origin"):
            return False
        return not S.token or self.headers.get("X-Bridge-Token") == S.token

    def _stream(self, messages, max_tokens, temperature) -> None:
        if S.model_status != "ready":
            return self._json(503, {"error": f"Model is {S.model_status}. {S.model_error}".strip()})
        if not S.model_lock.acquire(timeout=1.0):
            return self._json(409, {"error": f"Busy: {S.busy_reason or 'another reply is running'}"})
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def emit(obj):
                self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()

            S.busy_reason = "Replying"
            try:
                stream_generate(messages, max_tokens, temperature, emit)
            except (BrokenPipeError, ConnectionResetError):
                pass  # user pressed Stop
            except Exception as e:  # noqa: BLE001
                with contextlib.suppress(Exception):
                    emit({"t": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            S.busy_reason = ""
            S.model_lock.release()

    # routing
    def do_GET(self):
        if not self._authorized():
            return self._json(403, {"error": "forbidden"})
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/health":
                return self._json(200, {
                    "ok": True, "model_id": S.model_id or S.cfg.get("model_id") or getattr(S.dwl, "LOCAL_MODEL_ID", ""),
                    "model_status": S.model_status, "model_error": S.model_error,
                    "busy": S.busy_reason, "offline_guard": offline_guard.status(),
                    "hf_offline": os.environ.get("HF_HUB_OFFLINE") == "1",
                    "root": str(S.root), "python": sys.executable,
                })
            if u.path == "/config":
                return self._json(200, S.cfg)
            if u.path == "/today":
                d = date.fromisoformat(q["date"][0]) if q.get("date") else date.today()
                return self._json(200, today_payload(d))
            if u.path == "/actions":
                return self._json(200, {"actions": actions.public_list()})
            if u.path.startswith("/jobs/"):
                job = S.jobs.get(u.path.rsplit("/", 1)[-1])
                return self._json(200, job) if job else self._json(404, {"error": "no such job"})
            if u.path == "/workbooks":
                return self._json(200, {"workbooks": list_workbooks()})
            if u.path == "/printers":
                return self._json(200, list_printers())
            return self._json(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if not self._authorized():
            return self._json(403, {"error": "forbidden"})
        u = urlparse(self.path)
        try:
            body = self._body()
            if u.path == "/chat":
                msgs = [m for m in body.get("messages", []) if m.get("content")]
                system = body.get("system", S.cfg["system_prompt"])
                if system and not any(m["role"] == "system" for m in msgs):
                    msgs.insert(0, {"role": "system", "content": system})
                return self._stream(msgs, body.get("max_tokens", S.cfg["max_tokens"]),
                                    body.get("temperature", S.cfg["temperature"]))
            if u.path == "/actions/run":
                a = actions.ACTIONS.get(body.get("action", ""))
                if not a:
                    return self._json(404, {"error": "unknown action"})
                msgs = a["fn"](body.get("item", {}))
                return self._stream(msgs, a["max_tokens"], a["temperature"])
            if u.path == "/config":
                for k in DEFAULT_CONFIG:
                    if k in body:
                        S.cfg[k] = body[k]
                save_config(S.cfg)
                apply_guard()
                return self._json(200, S.cfg)
            if u.path == "/workbook/generate":
                if S.model_status != "ready":
                    return self._json(503, {"error": f"Model is {S.model_status}"})
                if S.model_lock.locked():
                    return self._json(409, {"error": f"Busy: {S.busy_reason}"})
                return self._json(200, start_workbook_job())
            if u.path == "/tasks/generate":
                return self._json(200, generate_tasks(int(body.get("days", 7))))
            if u.path == "/tasks/print":
                return self._json(200, print_tasks(body.get("printer", ""), int(body.get("days", 1)),
                                                   bool(body.get("preview")), bool(body.get("force"))))
            return self._json(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline bridge for the Workbook Mac app.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--root", default=str(BRIDGE_DIR.parent.parent),
                    help="GoalManagement folder (default: two levels up from this file).")
    ap.add_argument("--no-model", action="store_true", help="Skip loading the model (UI testing).")
    ap.add_argument("--exit-with-parent", action="store_true",
                    help="Quit automatically when the app that started us quits.")
    args = ap.parse_args()

    if args.exit_with_parent:
        parent = os.getppid()

        def watch_parent():
            while True:
                time.sleep(2)
                if os.getppid() != parent:
                    os._exit(0)
        threading.Thread(target=watch_parent, daemon=True).start()

    S.root = Path(args.root).expanduser().resolve()
    S.cfg = load_config()
    apply_guard()
    load_project_modules()
    if not args.no_model:
        load_model_async()

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    print(f"[bridge] listening on http://127.0.0.1:{args.port}  root={S.root}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
