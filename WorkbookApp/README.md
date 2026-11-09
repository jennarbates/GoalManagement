# Workbook (Mac app for your local model)

A native SwiftUI app for the MLX model that powers `dailyWorkbookLocal.py`.
Everything runs on your Mac. The model never touches the internet.

## What's inside

```
WorkbookApp/
  bridge/
    workbook_bridge.py   local server the app talks to (127.0.0.1 only)
    offline_guard.py     blocks all outbound network from the model process
    actions.py           lesson-help buttons (add your own here)
  mac/                   SwiftUI app source (Swift Package)
  build_app.sh           builds Workbook.app
```

The app starts `bridge/workbook_bridge.py` with your `.venv` Python. The bridge
loads `mlx-community/LFM2-8B-A1B-8bit-MLX` once (the `LOCAL_MODEL_ID` in
`dailyWorkbookLocal.py`) and reuses your existing scripts directly, so the
curriculum, HSK progress and chore schedule stay in one place.

## Tabs

* **Today**: CS311 algorithms, HSK 1 and chore cards for the day,
  plus your parking lot. Each card has buttons like Explain it, Quiz me,
  Pseudocode, Break it down, Example sentences, and Ask in chat.
* **Chat**: streaming chat with the model. Stop at any time.
* **Workbook & Printer**: generate today's workbook (same output as running
  `dailyWorkbookLocal.py`), write `workbook_tasks.json`, preview or print
  receipts, and open past workbooks.
* **Settings**: folder paths, port, offline status, model settings, bridge log.

## How "fully offline" is enforced

1. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set before anything
   loads, so the model is read only from your local Hugging Face cache.
2. `offline_guard.py` patches Python's socket layer in the bridge process.
   Only loopback connections are allowed. Proxies are ignored so they can't
   be used as a side door. Any other attempt fails and is listed under
   Settings > Offline > Recently blocked.
3. The app itself only talks to `127.0.0.1` with proxies turned off.
4. The bridge only listens on `127.0.0.1`, requires a random per-launch token,
   and rejects anything sent from a web page.

One opt-in exception: `dailyWorkbookLocal.py` fetches weather from
`api.weather.gov`. That is off by default (the workbook just shows no weather).
Turn on "Allow the workbook's weather lookup" in Settings to allow that one
hostname and nothing else.

Reference links on the cards (Python docs, Coursera) open in your browser
only when you click them.

## Build and run

Needs macOS 14+ and Xcode 16+ (or its Command Line Tools).

```bash
cd ~/Documents/Development/GoalManagement/WorkbookApp
chmod +x build_app.sh
./build_app.sh
open Workbook.app
```

* `cd <path>` moves into the WorkbookApp folder.
* `chmod +x build_app.sh` marks the script as executable. `+x` adds the
  execute permission.
* `./build_app.sh` runs the build. Inside it:
  * `swift build -c release` compiles the app. `-c release` picks the
    optimized release configuration instead of debug.
  * `swift build -c release --show-bin-path` prints the folder the binary
    was built into, without building again.
  * `codesign --force --sign - Workbook.app` gives the app an ad hoc
    signature so macOS will run it. `--force` replaces any old signature,
    `--sign -` means "ad hoc" (no developer certificate needed).
* `open Workbook.app` launches it like double clicking it in Finder.

You can drag `Workbook.app` into `/Applications` afterwards. If you move the
GoalManagement folder, update the path in Settings.

To work on the UI in Xcode instead: `open mac/Package.swift` opens the
package in Xcode, then press Run.

### Run the bridge by hand (for debugging)

```bash
cd ~/Documents/Development/GoalManagement
.venv/bin/python WorkbookApp/bridge/workbook_bridge.py --port 8765
```

* `.venv/bin/python` uses your venv's Python directly, so no `activate` needed.
* `--port 8765` sets the local port (the app uses 8765 by default).
* Other flags: `--root <folder>` points at a different GoalManagement folder,
  `--no-model` skips loading the model (fast UI testing),
  `--exit-with-parent` quits when the app that launched it quits (the app
  passes this for you).

When run by hand with no `WORKBOOK_BRIDGE_TOKEN` set, the token check is
skipped, so you can poke it with `curl`:

```bash
curl -s http://127.0.0.1:8765/health
```

* `curl` makes an HTTP request. `-s` is silent mode (hides the progress bar).

## Adding features as you go

**New lesson-help button (Python only, no Swift).** Add a function to
`bridge/actions.py`:

```python
@action("mnemonic", "Memory trick", kinds=("hsk",), icon="brain")
def mnemonic(item):
    return [
        {"role": "system", "content": TUTOR},
        {"role": "user", "content": _describe(item) + "\n\nGive a short memory trick for each word."},
    ]
```

Then Settings > Restart bridge. The button shows up on every matching card.
`kinds` can be `algorithms`, `hsk`, `chore`, or `"*"` for all.
`icon` is any SF Symbols name.

**New data or tool (Python + a little Swift).**

1. Add a route in `workbook_bridge.py` inside `do_GET` or `do_POST`
   (for example `/journal` that reads from JournalingGuy).
2. Add a `Decodable` struct for the response in `mac/Sources/WorkbookApp/Models.swift`.
3. Add a case to `AppTab` in `AppModel.swift` and a new view file. Call the
   bridge with `let r: MyType = try await bridge.client.get("/journal")`.
   For streamed model output use `bridge.client.stream(...)` like `ChatView`.
4. Rebuild with `./build_app.sh`.

## Notes

* The model loads once and is shared with workbook generation, so there is
  only ever one copy in memory. While the workbook is generating, chat waits.
* The first launch takes a bit while the model loads (status in the sidebar).
* If the status says the model is not in the local cache, run the workbook
  script once while online so it downloads, then everything is offline.
* `generate_workbook_tasks.py` looks for `taskprinter.py` in the
  `daily-workbook` folder, but it lives in `TaskPrinter/`. The app calls
  `TaskPrinter/taskprinter.py` directly, so printing from the app works either way.
* `dailyWorkbookLocal.py` reads `parking_lot.txt` from the `workbooks/`
  folder, while yours is in `daily-workbook/`. The Today tab reads the one in
  `daily-workbook/`.
