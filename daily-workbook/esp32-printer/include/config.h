#pragma once

// ── When to print ────────────────────────────────────────────────────────────
#define PRINT_HOUR        6
#define PRINT_MINUTE      30
// If the printer is off or busy, keep retrying for this long, then give up
// for the day (so a workbook never comes out in the afternoon).
#define PRINT_WINDOW_MIN  180
#define RETRY_EVERY_MIN   10

// POSIX time zone for America/New_York (handles daylight saving)
#define TZ_INFO "EST5EDT,M3.2.0,M11.1.0"

// ── Printer (HP ENVY Inspire 7900, found with ippfind on the Mac) ────────────
#define PRINTER_HOST  "HP846993D5E29E.local"   // or a fixed IP like "192.168.1.40"
#define PRINTER_PORT  631
#define PRINTER_PATH  "/ipp/print"
#define PRINTER_SIDES "one-sided"   // or "two-sided-long-edge" (see README)

// ── This device ──────────────────────────────────────────────────────────────
#define DEVICE_HOSTNAME "workbook-printer"      // reachable as workbook-printer.local

// ── microSD card wiring (SPI) ────────────────────────────────────────────────
// Defaults are the ESP32-S3 DevKitC's FSPI pins; for a classic ESP32 DevKit use
// SCK 18, MISO 19, MOSI 23, CS 5.
#if CONFIG_IDF_TARGET_ESP32S3
  #define SD_SCK  12
  #define SD_MISO 13
  #define SD_MOSI 11
  #define SD_CS   10
#else
  #define SD_SCK  18
  #define SD_MISO 19
  #define SD_MOSI 23
  #define SD_CS   5
#endif
