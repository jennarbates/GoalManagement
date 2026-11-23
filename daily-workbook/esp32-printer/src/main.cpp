// Workbook printer
//
// Keeps a queue of numbered workbook print files (NNN.pclm, made on the Mac by
// print_batch.py and uploaded by push_to_esp.py) on a microSD card. Nothing
// prints on a schedule: when asked, it sends the lowest-numbered file to the
// HP over Wi-Fi with IPP, then removes it so the next request gets the next one.
//
// HTTP API (port 80, http://workbook-printer.local):
//   GET    /                       a small page with a "Print next workbook" button
//   GET    /status                 status JSON: files, next workbook, last print
//   PUT    /files/<name>           upload a file (raw body)
//   DELETE /files/<name>           delete a file
//   POST   /print/next             print the next workbook and take it off the queue
//   POST   /print/<number>/<pages> print now, keep the file; pages = "all" or e.g. "1-1"

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
static int    lastPrinted = 0;          // number of the last workbook printed with "print next"
static String lastResult = "nothing printed since boot";
static uint32_t lastPrintMs = 0;        // when "print next" last succeeded (0 = not since boot)

// ── Small helpers ────────────────────────────────────────────────────────────

static bool clockSet() { return time(nullptr) > 1700000000; }   // NTP has answered

static String fmtTime(time_t t, const char* fmt) {
  struct tm tm; localtime_r(&t, &tm);
  char b[40]; strftime(b, sizeof b, fmt, &tm);
  return b;
}
// A workbook number: 1 to 4 digits, not zero. Returns 0 if it isn't one.
static int parseNumber(const String& s) {
  if (s.length() < 1 || s.length() > 4) return 0;
  for (char c : s) if (!isDigit(c)) return 0;
  return s.toInt();
}
// Print files are named by workbook number, zero-padded: 007.pclm
static String fileFor(int number) {
  char b[16]; snprintf(b, sizeof b, "%03d.pclm", number);
  return b;
}
static int numberOf(const String& name) {
  return name.endsWith(".pclm") ? parseNumber(name.substring(0, name.length() - 5)) : 0;
}
// Only these names may be written to the card — nothing with a path in it.
static bool validName(const String& n) {
  return n == "manifest.json" || (numberOf(n) > 0 && n == fileFor(numberOf(n)));
}

// The lowest-numbered workbook on the card, or 0 if the queue is empty.
static int nextQueued() {
  if (!sdOk) return 0;
  int best = 0;
  File root = SD.open("/");
  for (File e = root.openNextFile(); e; e = root.openNextFile()) {
    String n = e.name();
    if (n.startsWith("/")) n = n.substring(1);
    int num = (!e.isDirectory() && validName(n)) ? numberOf(n) : 0;
    if (num > 0 && (best == 0 || num < best)) best = num;
    e.close();
  }
  root.close();
  return best;
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

// Prints workbook <number>. pages "all" or "A-B". Returns true when the printer
// accepted the job; the reason either way goes into lastResult.
static bool printWorkbook(int number, const String& pages) {
  String label = "workbook " + String(number);
  String path = "/" + fileFor(number);
  if (!sdOk) { lastResult = "no SD card"; return false; }
  File f = SD.open(path, FILE_READ);
  if (!f) { lastResult = "no print file for " + label; return false; }

  int lo = 0, hi = 0;
  if (pages != "all" && sscanf(pages.c_str(), "%d-%d", &lo, &hi) != 2) {
    f.close(); lastResult = "bad page range " + pages; return false;
  }

  IPAddress ip = resolvePrinter();
  if (ip == IPAddress(0, 0, 0, 0)) { f.close(); lastResult = "can't find printer " PRINTER_HOST; return false; }

  auto head = printJobRequest("Workbook " + String(number), lo, hi);
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
  lastResult = "sent " + label + (pages == "all" ? "" : " pages " + pages) + " to the printer"
             + (clockSet() ? " at " + fmtTime(time(nullptr), "%b %d %H:%M") : String(""));
  logf("%s", lastResult.c_str());
  return true;
}

// Remove files left over from the old dated firmware (YYYY-MM-DD.pclm).
static void removeDatedFiles() {
  if (!sdOk) return;
  File root = SD.open("/");
  std::vector<String> old;
  for (File e = root.openNextFile(); e; e = root.openNextFile()) {
    String n = e.name();
    if (n.startsWith("/")) n = n.substring(1);
    if (n.endsWith(".pclm") && n.length() == 15 && n[4] == '-' && n[7] == '-') old.push_back(n);
    e.close();
  }
  root.close();
  for (auto& n : old) { SD.remove("/" + n); logf("removed old dated file %s", n.c_str()); }
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
  String s = "{";
  s += "\"clock\":\"" + (clockSet() ? fmtTime(time(nullptr), "%Y-%m-%d %H:%M:%S %Z") : String("not set yet")) + "\",";
  s += "\"printer\":\"" PRINTER_HOST "\",";
  s += "\"next\":" + String(nextQueued()) + ",";
  s += "\"last_printed\":" + String(lastPrinted) + ",";
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
  int number = parseNumber(server.pathArg(0));
  String pages = server.pathArg(1);
  if (number == 0) { sendJson(400, "{\"error\":\"workbook must be a number\"}"); return; }
  bool ok = printWorkbook(number, pages);
  sendJson(ok ? 200 : 502, "{\"ok\":" + String(ok ? "true" : "false") + ",\"result\":\"" + jsonEsc(lastResult) + "\"}");
}

// Print the lowest-numbered workbook, then take it off the queue so the next
// request prints the one after it.
static void handlePrintNext() {
  // A second tap right after the first would print two workbooks in a row.
  if (lastPrintMs != 0 && millis() - lastPrintMs < PRINT_NEXT_COOLDOWN_S * 1000UL) {
    sendJson(409, "{\"ok\":false,\"result\":\"workbook " + String(lastPrinted) + " was just sent to the printer; wait a few minutes before asking for another\"}");
    return;
  }
  int number = nextQueued();
  if (number == 0) {
    lastResult = sdOk ? "nothing queued: build and upload more workbooks from the Mac" : "no SD card";
    sendJson(404, "{\"ok\":false,\"result\":\"" + jsonEsc(lastResult) + "\"}");
    return;
  }
  bool ok = printWorkbook(number, "all");
  if (ok) {
    lastPrinted = number;
    lastPrintMs = millis() | 1;
    prefs.putInt("lastNum", number);     // survives a reboot
    SD.remove("/" + fileFor(number));
  }
  sendJson(ok ? 200 : 502, "{\"ok\":" + String(ok ? "true" : "false") + ",\"number\":" + String(number)
           + ",\"result\":\"" + jsonEsc(lastResult) + "\"}");
}

static const char HOME_PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workbook printer</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 26rem; margin: 2rem auto; padding: 0 1rem; color: #2b2540; background: #fffaf3; }
  h1 { font-size: 1.3rem; }
  button { font-size: 1.15rem; width: 100%; padding: 1rem; border: 2px solid #9B8EC4; border-radius: 14px; background: #f3efff; color: #2b2540; }
  button:disabled { opacity: .5; }
  p { line-height: 1.5; }
  #msg { font-weight: 600; }
  small { color: #777; }
</style></head><body>
<h1>Workbook printer</h1>
<p id="next">Checking the queue…</p>
<button id="go" disabled>Print next workbook</button>
<p id="msg"></p>
<p><small id="detail"></small></p>
<script>
const $ = id => document.getElementById(id);
async function refresh() {
  try {
    const s = await (await fetch('/status')).json();
    const queued = s.files.filter(f => f.name.endsWith('.pclm')).length;
    $('next').textContent = s.next ? `Next up: workbook ${s.next} (${queued} queued)` : 'Nothing queued. Build and upload more from the Mac.';
    $('go').disabled = !s.next;
    $('detail').textContent = `Last printed: ${s.last_printed ? 'workbook ' + s.last_printed : 'none yet'}. ${s.last_result}.`;
  } catch (e) { $('next').textContent = 'Could not read the status.'; }
}
$('go').onclick = async () => {
  $('go').disabled = true;
  $('msg').textContent = 'Sending to the printer… this takes a few minutes. Keep this page open.';
  try {
    const r = await (await fetch('/print/next', {method: 'POST'})).json();
    $('msg').textContent = (r.ok ? 'Done: ' : 'Did not print: ') + r.result;
  } catch (e) { $('msg').textContent = 'Lost the connection. Check the printer, then reload this page.'; }
  refresh();
};
refresh();
</script></body></html>)HTML";

static void handleHome() { server.send_P(200, "text/html", HOME_PAGE); }

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
  lastPrinted = prefs.getInt("lastNum", 0);
  removeDatedFiles();

  connectWifi();
  configTzTime(TZ_INFO, "pool.ntp.org", "time.nist.gov");
  MDNS.begin(DEVICE_HOSTNAME);
  MDNS.addService("http", "tcp", 80);

  server.on("/", HTTP_GET, handleHome);
  server.on("/status", HTTP_GET, handleStatus);
  server.on(UriBraces("/files/{}"), HTTP_PUT, handleUploadDone, handleUploadData);
  server.on(UriBraces("/files/{}"), HTTP_DELETE, handleDelete);
  server.on("/print/next", HTTP_POST, handlePrintNext);
  server.on(UriBraces("/print/{}/{}"), HTTP_POST, handlePrint);
  server.onNotFound([] { sendJson(404, "{\"error\":\"not found\"}"); });
  server.begin();
  logf("ready at http://%s.local  (prints the next workbook when asked)", DEVICE_HOSTNAME);
}

void loop() {
  server.handleClient();
  delay(2);
}
