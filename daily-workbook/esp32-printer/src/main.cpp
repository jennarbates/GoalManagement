// Workbook printer
//
// Keeps a week of workbook print files (YYYY-MM-DD.pclm, made on the Mac by
// print_batch.py and uploaded by push_to_esp.py) on a microSD card, and at
// PRINT_HOUR:PRINT_MINUTE sends today's to the HP over Wi-Fi with IPP.
//
// HTTP API (port 80, http://workbook-printer.local):
//   GET    /                       status JSON: clock, files, last print
//   PUT    /files/<name>           upload a file (raw body)
//   DELETE /files/<name>           delete a file
//   POST   /print/<date>/<pages>   print now; pages = "all" or e.g. "1-1"

#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <uri/UriBraces.h>
#include <SPI.h>
#include <SD.h>
#include <Preferences.h>
#include <time.h>
#include <vector>

#include "config.h"
#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #error "Copy include/secrets.example.h to include/secrets.h and fill in your Wi-Fi."
#endif

static WebServer server(80);
static Preferences prefs;

static bool   sdOk = false;
static String lastPrinted;              // date of the last successful scheduled print
static String lastResult = "nothing printed since boot";
static String attemptsDate;
static int    attemptsToday = 0;
static uint32_t lastAttemptMs = 0;

// ── Small helpers ────────────────────────────────────────────────────────────

static bool clockSet() { return time(nullptr) > 1700000000; }   // NTP has answered

static String fmtTime(time_t t, const char* fmt) {
  struct tm tm; localtime_r(&t, &tm);
  char b[40]; strftime(b, sizeof b, fmt, &tm);
  return b;
}
static String today() { return fmtTime(time(nullptr), "%Y-%m-%d"); }

static bool isDate(const String& s) {
  if (s.length() != 10) return false;
  for (int i = 0; i < 10; i++) {
    char c = s[i];
    if (i == 4 || i == 7) { if (c != '-') return false; }
    else if (!isDigit(c)) return false;
  }
  return true;
}
// Only these names may be written to the card — nothing with a path in it.
static bool validName(const String& n) {
  return n == "manifest.json" || (n.endsWith(".pclm") && isDate(n.substring(0, n.length() - 5)));
}

static String jsonEsc(const String& s) {
  String o; o.reserve(s.length() + 8);
  for (char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += c; }
    else if ((uint8_t)c < 0x20) o += ' ';
    else o += c;
  }
  return o;
}

static void logf(const char* fmt, ...) {
  char b[256]; va_list ap; va_start(ap, fmt); vsnprintf(b, sizeof b, fmt, ap); va_end(ap);
  Serial.printf("[%s] %s\n", clockSet() ? fmtTime(time(nullptr), "%m-%d %H:%M:%S").c_str() : "--", b);
}

// ── IPP (RFC 8010) request encoding ──────────────────────────────────────────

struct IppBuf {
  std::vector<uint8_t> b;
  void u8(uint8_t v)   { b.push_back(v); }
  void u16(uint16_t v) { u8(v >> 8); u8(v & 0xff); }
  void u32(uint32_t v) { u16(v >> 16); u16(v & 0xffff); }
  void raw(const void* p, size_t n) { auto c = (const uint8_t*)p; b.insert(b.end(), c, c + n); }
  void attr(uint8_t tag, const char* name, const String& value) {
    u8(tag); u16(strlen(name)); raw(name, strlen(name));
    u16(value.length()); raw(value.c_str(), value.length());
  }
  void range(const char* name, int32_t lo, int32_t hi) {
    u8(0x33); u16(strlen(name)); raw(name, strlen(name)); u16(8); u32(lo); u32(hi);
  }
};

static std::vector<uint8_t> printJobRequest(const String& jobName, int pageLo, int pageHi) {
  IppBuf r;
  r.u8(2); r.u8(0);          // IPP 2.0
  r.u16(0x0002);             // Print-Job
  r.u32(1);                  // request-id
  r.u8(0x01);                // operation attributes
  r.attr(0x47, "attributes-charset", "utf-8");
  r.attr(0x48, "attributes-natural-language", "en");
  r.attr(0x45, "printer-uri", String("ipp://") + PRINTER_HOST + ":" + PRINTER_PORT + PRINTER_PATH);
  r.attr(0x42, "requesting-user-name", "workbook");
  r.attr(0x42, "job-name", jobName);
  r.attr(0x49, "document-format", "application/PCLm");
  r.u8(0x02);                // job attributes
  r.attr(0x44, "media", "na_letter_8.5x11in");
  r.attr(0x44, "sides", PRINTER_SIDES);
  if (pageLo > 0) r.range("page-ranges", pageLo, pageHi);
  r.u8(0x03);                // end
  return r.b;
}

// ── Sending a print job ──────────────────────────────────────────────────────

static IPAddress resolvePrinter() {
  IPAddress ip;
  String host = PRINTER_HOST;
  if (ip.fromString(host)) return ip;
  if (host.endsWith(".local")) {
    ip = MDNS.queryHost(host.substring(0, host.length() - 6), 4000);
    if (ip != IPAddress(0, 0, 0, 0)) return ip;
  }
  if (WiFi.hostByName(host.c_str(), ip) == 1) return ip;
  return IPAddress(0, 0, 0, 0);
}

static bool readLine(WiFiClient& c, String& line, uint32_t timeoutMs) {
  line = "";
  uint32_t start = millis();
  while (millis() - start < timeoutMs) {
    while (c.available()) {
      char ch = c.read();
      if (ch == '\n') { line.trim(); return true; }
      line += ch;
    }
    if (!c.connected()) return line.length() > 0;
    delay(5);
  }
  return false;
}

static bool readBytes(WiFiClient& c, uint8_t* out, size_t n, uint32_t timeoutMs) {
  size_t got = 0; uint32_t start = millis();
  while (got < n && millis() - start < timeoutMs) {
    if (c.available()) out[got++] = c.read();
    else if (!c.connected()) break;
    else delay(5);
  }
  return got == n;
}

// Prints /<date>.pclm. pages "all" or "A-B". Returns true when the printer
// accepted the job; the reason either way goes into lastResult.
static bool printDay(const String& date, const String& pages) {
  String path = "/" + date + ".pclm";
  if (!sdOk) { lastResult = "no SD card"; return false; }
  File f = SD.open(path, FILE_READ);
  if (!f) { lastResult = "no print file for " + date; return false; }

  int lo = 0, hi = 0;
  if (pages != "all" && sscanf(pages.c_str(), "%d-%d", &lo, &hi) != 2) {
    f.close(); lastResult = "bad page range " + pages; return false;
  }

  IPAddress ip = resolvePrinter();
  if (ip == IPAddress(0, 0, 0, 0)) { f.close(); lastResult = "can't find printer " PRINTER_HOST; return false; }

  auto head = printJobRequest("Workbook " + date, lo, hi);
  size_t total = head.size() + f.size();
  logf("printing %s (%u bytes, pages %s) to %s", path.c_str(), (unsigned)f.size(), pages.c_str(), ip.toString().c_str());

  WiFiClient c;
  if (!c.connect(ip, PRINTER_PORT, 10000)) { f.close(); lastResult = "printer didn't answer"; return false; }
  c.printf("POST %s HTTP/1.1\r\nHost: %s:%d\r\nContent-Type: application/ipp\r\n"
           "Content-Length: %u\r\nConnection: close\r\n\r\n",
           PRINTER_PATH, PRINTER_HOST, PRINTER_PORT, (unsigned)total);
  c.write(head.data(), head.size());

  // Stream the file. The printer takes data as fast as it can spool it, which
  // can be slow while it's printing, so allow a long stall before giving up.
  static uint8_t buf[4096];
  size_t sent = 0; uint32_t lastProgress = millis();
  while (sent < f.size()) {
    size_t n = f.read(buf, sizeof buf);
    if (n == 0) break;
    size_t off = 0;
    while (off < n) {
      size_t w = c.write(buf + off, n - off);
      if (w > 0) { off += w; lastProgress = millis(); }
      else if (!c.connected() || millis() - lastProgress > 120000) {
        f.close(); c.stop(); lastResult = "printer stopped taking data at " + String(sent + off) + " bytes"; return false;
      } else delay(10);
    }
    sent += n;
  }
  f.close();

  // HTTP status line, headers, then the 8-byte IPP response header
  String line;
  if (!readLine(c, line, 180000)) { c.stop(); lastResult = "no reply from printer"; return false; }
  if (line.startsWith("HTTP/1.1 100")) { while (readLine(c, line, 5000) && line.length()) {} readLine(c, line, 180000); }
  int httpCode = line.length() > 12 ? line.substring(9, 12).toInt() : 0;
  bool chunked = false;
  while (readLine(c, line, 10000) && line.length()) {
    String l = line; l.toLowerCase();
    if (l.startsWith("transfer-encoding:") && l.indexOf("chunked") >= 0) chunked = true;
  }
  if (chunked) readLine(c, line, 10000);   // chunk size; IPP header follows
  uint8_t resp[8];
  bool gotIpp = readBytes(c, resp, 8, 10000);
  c.stop();

  if (httpCode != 200 || !gotIpp) { lastResult = "printer replied HTTP " + String(httpCode); return false; }
  uint16_t status = (resp[2] << 8) | resp[3];
  char hex[8]; snprintf(hex, sizeof hex, "0x%04x", status);
  if (status >= 0x0100) {        // 0x0000–0x00ff are the successful-ok codes
    lastResult = "printer refused the job (IPP status " + String(hex) + ")";
    return false;
  }
  lastResult = "printed " + date + (pages == "all" ? "" : " pages " + pages) + " at " + fmtTime(time(nullptr), "%H:%M");
  logf("%s", lastResult.c_str());
  return true;
}

// Remove print files for days that have passed.
static void cleanupOld() {
  if (!sdOk || !clockSet()) return;
  String t = today();
  File root = SD.open("/");
  std::vector<String> old;
  for (File e = root.openNextFile(); e; e = root.openNextFile()) {
    String n = e.name();
    if (n.startsWith("/")) n = n.substring(1);
    if (n.endsWith(".pclm") && validName(n) && n.substring(0, 10) < t) old.push_back(n);
    e.close();
  }
  root.close();
  for (auto& n : old) { SD.remove("/" + n); logf("removed old %s", n.c_str()); }
}

// ── Schedule ─────────────────────────────────────────────────────────────────

static void checkSchedule() {
  if (!clockSet()) return;
  time_t now = time(nullptr);
  struct tm tm; localtime_r(&now, &tm);
  String t = today();
  if (lastPrinted == t) return;

  int minute = tm.tm_hour * 60 + tm.tm_min;
  int start  = PRINT_HOUR * 60 + PRINT_MINUTE;
  if (minute < start || minute > start + PRINT_WINDOW_MIN) return;

  if (attemptsDate != t) { attemptsDate = t; attemptsToday = 0; }
  if (attemptsToday > 0 && millis() - lastAttemptMs < RETRY_EVERY_MIN * 60000UL) return;
  if (!SD.exists("/" + t + ".pclm")) {
    if (attemptsToday == 0) { lastResult = "no print file for " + t; logf("%s", lastResult.c_str()); }
    attemptsToday++; lastAttemptMs = millis();
    return;
  }

  attemptsToday++; lastAttemptMs = millis();
  if (printDay(t, "all")) {
    lastPrinted = t;
    prefs.putString("lastPrinted", t);   // survives a reboot, so it never prints twice
    cleanupOld();
  } else {
    logf("attempt %d failed: %s", attemptsToday, lastResult.c_str());
  }
}

// ── HTTP handlers ────────────────────────────────────────────────────────────

static void sendJson(int code, const String& body) { server.send(code, "application/json", body + "\n"); }

static void handleStatus() {
  String files = "[";
  if (sdOk) {
    File root = SD.open("/");
    bool first = true;
    for (File e = root.openNextFile(); e; e = root.openNextFile()) {
      String n = e.name(); if (n.startsWith("/")) n = n.substring(1);
      if (!e.isDirectory() && validName(n)) {
        files += String(first ? "" : ",") + "{\"name\":\"" + n + "\",\"bytes\":" + String((uint32_t)e.size()) + "}";
        first = false;
      }
      e.close();
    }
    root.close();
  }
  files += "]";
  char printAt[6]; snprintf(printAt, sizeof printAt, "%02d:%02d", PRINT_HOUR, PRINT_MINUTE);
  String s = "{";
  s += "\"clock\":\"" + (clockSet() ? fmtTime(time(nullptr), "%Y-%m-%d %H:%M:%S %Z") : String("not set yet")) + "\",";
  s += "\"print_time\":\"" + String(printAt) + "\",";
  s += "\"printer\":\"" PRINTER_HOST "\",";
  s += "\"last_printed\":\"" + lastPrinted + "\",";
  s += "\"last_result\":\"" + jsonEsc(lastResult) + "\",";
  s += "\"sd_ok\":" + String(sdOk ? "true" : "false") + ",";
  s += "\"free_bytes\":" + String(sdOk ? (double)(SD.totalBytes() - SD.usedBytes()) : 0.0, 0) + ",";
  s += "\"files\":" + files + "}";
  sendJson(200, s);
}

static File   upFile;
static String upName;
static bool   upOk = false;

static void handleUploadData() {
  HTTPRaw& raw = server.raw();
  if (raw.status == RAW_START) {
    upName = server.pathArg(0);
    upOk = sdOk && validName(upName);
    if (upOk) { upFile = SD.open("/" + upName + ".part", FILE_WRITE); upOk = (bool)upFile; }
  } else if (raw.status == RAW_WRITE && upOk) {
    if (upFile.write(raw.buf, raw.currentSize) != raw.currentSize) upOk = false;
  } else if (raw.status == RAW_END && upFile) {
    upFile.close();
    if (upOk) { SD.remove("/" + upName); upOk = SD.rename("/" + upName + ".part", "/" + upName); }
    else SD.remove("/" + upName + ".part");
  } else if (raw.status == RAW_ABORTED) {
    if (upFile) upFile.close();
    SD.remove("/" + upName + ".part");
    upOk = false;
  }
}

static void handleUploadDone() {
  if (!upOk) { sendJson(400, "{\"error\":\"upload failed (bad name, no SD card, or card full)\"}"); return; }
  File f = SD.open("/" + upName);
  uint32_t size = f ? f.size() : 0; if (f) f.close();
  logf("stored %s (%u bytes)", upName.c_str(), (unsigned)size);
  sendJson(200, "{\"name\":\"" + upName + "\",\"bytes\":" + String(size) + "}");
}

static void handleDelete() {
  String n = server.pathArg(0);
  if (!sdOk || !validName(n)) { sendJson(400, "{\"error\":\"bad name\"}"); return; }
  sendJson(SD.remove("/" + n) ? 200 : 404, "{\"deleted\":\"" + n + "\"}");
}

static void handlePrint() {
  String date = server.pathArg(0), pages = server.pathArg(1);
  if (!isDate(date)) { sendJson(400, "{\"error\":\"date must be YYYY-MM-DD\"}"); return; }
  bool ok = printDay(date, pages);
  sendJson(ok ? 200 : 502, "{\"ok\":" + String(ok ? "true" : "false") + ",\"result\":\"" + jsonEsc(lastResult) + "\"}");
}

// ── Setup / loop ─────────────────────────────────────────────────────────────

static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(DEVICE_HOSTNAME);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Wi-Fi");
  for (int i = 0; i < 60 && WiFi.status() != WL_CONNECTED; i++) { delay(500); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? " connected, " + WiFi.localIP().toString() : " not connected yet (will keep trying)");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nWorkbook printer");

  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  sdOk = SD.begin(SD_CS, SPI, 20000000);
  Serial.println(sdOk ? "SD card ok" : "SD card NOT found — check wiring and that it's FAT32");

  prefs.begin("workbook", false);
  lastPrinted = prefs.getString("lastPrinted", "");

  connectWifi();
  configTzTime(TZ_INFO, "pool.ntp.org", "time.nist.gov");
  MDNS.begin(DEVICE_HOSTNAME);
  MDNS.addService("http", "tcp", 80);

  server.on("/", HTTP_GET, handleStatus);
  server.on("/status", HTTP_GET, handleStatus);
  server.on(UriBraces("/files/{}"), HTTP_PUT, handleUploadDone, handleUploadData);
  server.on(UriBraces("/files/{}"), HTTP_DELETE, handleDelete);
  server.on(UriBraces("/print/{}/{}"), HTTP_POST, handlePrint);
  server.onNotFound([] { sendJson(404, "{\"error\":\"not found\"}"); });
  server.begin();
  logf("ready at http://%s.local  (prints at %02d:%02d)", DEVICE_HOSTNAME, PRINT_HOUR, PRINT_MINUTE);
}

void loop() {
  server.handleClient();
  static uint32_t lastCheck = 0;
  if (millis() - lastCheck > 20000) {
    lastCheck = millis();
    checkSchedule();
    static bool cleaned = false;
    if (!cleaned && clockSet()) { cleanupOld(); cleaned = true; }
  }
  delay(2);
}
