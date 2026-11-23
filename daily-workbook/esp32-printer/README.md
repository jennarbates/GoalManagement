# Workbook printer (ESP32)

Prints the next workbook on the HP ENVY Inspire 7900 when you ask for it,
without the Mac being on.

```
Mac, whenever the queue runs low          ESP32, when you tap "Print next workbook"
────────────────────────────────          ─────────────────────────────────────────
print_batch.py  → NNN.pclm, numbered      takes the lowest-numbered file on the microSD
push_to_esp.py  → uploads over Wi-Fi  →   sends it to the HP over Wi-Fi (IPP), then removes it
```

Workbooks are numbered, not dated, so nothing prints on a schedule and nothing
goes stale: workbook 4 waits on the card until workbook 3 is done and you ask
for the next one.

The HP doesn't accept PDFs over the network, so the Mac converts each workbook
to PCLm (a raster format the HP lists as supported) ahead of time. The ESP32
just stores the files and sends the next one when asked.

## Parts (~$20)

- **Any ESP32 dev board.** Printing is over Wi-Fi, so it doesn't need USB host;
  an ESP32-S3-DevKitC-1 or a classic ESP32 DevKit both work.
- **microSD card module (SPI)** and a **microSD card**, 8–32 GB, formatted
  **FAT32**. Seven workbooks are about 70 MB.
- A USB power supply and cable, and 6 jumper wires.

## Wiring

| SD module | ESP32-S3 DevKitC | Classic ESP32 DevKit |
|---|---|---|
| VCC | 3V3 (or 5V if the module has a regulator — most blue ones do) | same |
| GND | GND | GND |
| SCK | GPIO 12 | GPIO 18 |
| MISO | GPIO 13 | GPIO 19 |
| MOSI | GPIO 11 | GPIO 23 |
| CS | GPIO 10 | GPIO 5 |

Different pins? Change them in `include/config.h`.

## Flashing (once)

```bash
pip3 install platformio            # or: brew install platformio
cd daily-workbook/esp32-printer
cp include/secrets.example.h include/secrets.h   # then put your Wi-Fi name/password in it
pio run -e esp32-s3 -t upload      # classic ESP32: -e esp32
pio device monitor                 # shows its IP, SD card status and clock
```

The ESP32 only joins **2.4 GHz** Wi-Fi. The printer's address is in
`include/config.h`.

Coming from the old dated firmware? Flash this one the same way. On its first
boot it clears the old `YYYY-MM-DD.pclm` files off the card.

## First run: check it actually prints

From `daily-workbook/`:

```bash
python3 push_to_esp.py check-printer    # asks the HP if it accepts the job (prints nothing)
python3 push_to_esp.py                  # upload the queued workbooks
python3 push_to_esp.py test-print 1 --pages 1-1   # one real page of workbook 1
```

## Printing the next workbook

Open `http://workbook-printer.local` on your phone or laptop and tap
**Print next workbook**, or from the Mac:

```bash
python3 push_to_esp.py print-next
```

## When the queue runs low

```bash
cd daily-workbook
HF_HUB_OFFLINE=1 ../.venv/bin/python print_batch.py   # build the next 7 workbooks
python3 push_to_esp.py                                # send them to the ESP32
python3 push_to_esp.py status                         # what's queued, what it last did
```

## How it behaves

- It prints only when asked. "Print next" sends the lowest-numbered workbook
  on the card and, once the printer accepts it, removes that file.
- It remembers the last workbook it printed, so a reboot doesn't lose its place.
- For a few minutes after a print it refuses another "print next", so a double
  tap can't print two workbooks.
- If the printer doesn't answer, nothing is removed: fix the printer and ask again.
- `test-print` prints pages of a queued workbook without taking it off the queue.

## Things to know

- **Paper:** a workbook is 45–55 pages, and the HP's tray holds about 125 sheets.
- **Two-sided printing** (`PRINTER_SIDES` in `config.h`) isn't tested. The HP
  expects back pages of PCLm pre-rotated, and Ghostscript doesn't do that, so
  backs may come out upside down. Try `test-print … --pages 1-2` before
  switching.
- **If the printer's name stops resolving**, give it a fixed IP in your router
  and put that IP in `PRINTER_HOST` (and in `push_to_esp.py` for
  `check-printer`).
