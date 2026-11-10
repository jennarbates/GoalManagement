# Workbook printer (ESP32)

Prints each morning's workbook on the HP ENVY Inspire 7900 without the Mac
being on.

```
Mac, once a week                         ESP32, every morning at 06:30
────────────────                         ─────────────────────────────
print_batch.py  → 7 × YYYY-MM-DD.pclm    reads today's file from microSD
push_to_esp.py  → uploads over Wi-Fi  →  sends it to the HP over Wi-Fi (IPP)
```

The HP doesn't accept PDFs over the network, so the Mac converts each day to
PCLm (a raster format the HP lists as supported) ahead of time. The ESP32 just
stores the files and sends the right one at the right time. Its clock comes
from the internet (NTP) and handles daylight saving.

## Parts (~$20)

- **Any ESP32 dev board.** Printing is over Wi-Fi, so it doesn't need USB host;
  an ESP32-S3-DevKitC-1 or a classic ESP32 DevKit both work.
- **microSD card module (SPI)** and a **microSD card**, 8–32 GB, formatted
  **FAT32**. A week is about 70 MB.
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

The ESP32 only joins **2.4 GHz** Wi-Fi. Print time, time zone and the printer's
address are in `include/config.h`.

## First run: check it actually prints

From `daily-workbook/`:

```bash
python3 push_to_esp.py check-printer    # asks the HP if it accepts the job (prints nothing)
python3 push_to_esp.py                  # upload the week
python3 push_to_esp.py test-print 2026-11-10 --pages 1-1   # one real page
```

## Every week

```bash
cd daily-workbook
HF_HUB_OFFLINE=1 ../.venv/bin/python print_batch.py   # build the next 7 days
python3 push_to_esp.py                                # send them to the ESP32
python3 push_to_esp.py status                         # what it has, what it last did
```

Or open `http://workbook-printer.local` in a browser for the same status.

## How it behaves

- At 06:30 it prints today's file once. If the printer doesn't answer, it
  retries every 10 minutes until 09:30, then gives up for the day.
- It remembers the last day it printed, so a reboot won't print twice.
- Files for past days are deleted after each print.
- If there's no file for today it prints nothing; `status` shows
  "no print file for …".

## Things to know

- **Paper:** a day is 45–55 pages, and the HP's tray holds about 125 sheets.
- **Two-sided printing** (`PRINTER_SIDES` in `config.h`) isn't tested. The HP
  expects back pages of PCLm pre-rotated, and Ghostscript doesn't do that, so
  backs may come out upside down. Try `test-print … --pages 1-2` before
  switching.
- **If the printer's name stops resolving**, give it a fixed IP in your router
  and put that IP in `PRINTER_HOST` (and in `push_to_esp.py` for
  `check-printer`).
