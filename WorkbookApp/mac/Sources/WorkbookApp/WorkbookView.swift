import SwiftUI
import AppKit

struct WorkbookView: View {
    @Environment(Bridge.self) private var bridge
    @Environment(AppModel.self) private var app

    private var job: Job? {
        get { app.workbookJob }
        nonmutating set { app.workbookJob = newValue }
    }
    @State private var jobError: String?
    @State private var files: [WorkbookFile] = []

    @State private var printers: [String] = []
    @State private var printer = ""
    @State private var taskDays = 7
    @State private var printDays = 1
    @State private var force = false
    @State private var printerOutput = ""
    @State private var printerBusy = false

    private var jobRunning: Bool { job?.status == "running" }

    var body: some View {
        Form {
            Section("Daily workbook") {
                HStack {
                    Button {
                        Task { await generateWorkbook() }
                    } label: {
                        Label("Generate today's workbook", systemImage: "wand.and.stars")
                    }
                    .disabled(!bridge.isReady || jobRunning)
                    if jobRunning { ProgressView().controlSize(.small) }
                    Spacer()
                    if let j = job, j.status == "done" {
                        openButtons(html: j.result["html"] ?? "", pdf: j.result["pdf"] ?? "")
                    }
                }
                Text("Runs dailyWorkbookLocal.py with the model that is already loaded. Chat waits until it finishes.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let jobError {
                    Text(jobError).foregroundStyle(.red)
                }
                if let j = job {
                    ScrollViewReader { proxy in
                        ScrollView {
                            Text(j.log.isEmpty ? "Starting…" : j.log)
                                .font(.system(.caption, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Color.clear.frame(height: 1).id("end")
                        }
                        .frame(height: 200)
                        .onChange(of: j.log) { _, _ in proxy.scrollTo("end") }
                    }
                }
            }

            Section("Receipt printer") {
                Stepper("Generate tasks for \(taskDays) day\(taskDays == 1 ? "" : "s")", value: $taskDays, in: 1...30)
                Button("Write workbook_tasks.json") { Task { await generateTasks() } }
                    .disabled(bridge.health == nil || printerBusy)
                Picker("Printer", selection: $printer) {
                    Text("Choose a printer").tag("")
                    ForEach(printers, id: \.self) { Text($0).tag($0) }
                }
                Stepper("Print window: next \(printDays) day\(printDays == 1 ? "" : "s")", value: $printDays, in: 1...14)
                Toggle("Reprint receipts that were already printed", isOn: $force)
                HStack {
                    Button("Preview") { Task { await printReceipts(preview: true) } }
                    Button("Print") { Task { await printReceipts(preview: false) } }
                        .disabled(printer.isEmpty)
                    if printerBusy { ProgressView().controlSize(.small) }
                }
                .disabled(bridge.health == nil || printerBusy)
                if !printerOutput.isEmpty {
                    Text(printerOutput)
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }
            }

            Section("Past workbooks") {
                if files.isEmpty {
                    Text("None found yet").foregroundStyle(.secondary)
                }
                ForEach(files) { f in
                    HStack {
                        Text(f.date)
                        Spacer()
                        openButtons(html: f.html, pdf: f.pdf)
                    }
                }
            }
        }
        .formStyle(.grouped)
        .task(id: bridge.health != nil) { await loadLists() }
    }

    @ViewBuilder
    private func openButtons(html: String, pdf: String) -> some View {
        HStack(spacing: 6) {
            if !pdf.isEmpty { Button("PDF") { openFile(pdf) } }
            if !html.isEmpty { Button("HTML") { openFile(html) } }
        }
        .controlSize(.small)
    }

    @MainActor
    private func loadLists() async {
        guard bridge.health != nil else { return }
        let wr: WorkbooksResponse? = try? await bridge.client.get("/workbooks")
        if let w = wr {
            files = w.workbooks
        }
        let pr: PrintersResponse? = try? await bridge.client.get("/printers")
        if let p = pr {
            printers = p.printers
            if printer.isEmpty { printer = p.saved }
            if !printer.isEmpty && !printers.contains(printer) { printers.append(printer) }
        }
    }

    @MainActor
    private func generateWorkbook() async {
        jobError = nil
        do {
            var j: Job = try await bridge.client.post("/workbook/generate", EmptyBody())
            job = j
            while j.status == "running" {
                try await Task.sleep(for: .seconds(1))
                j = try await bridge.client.get("/jobs/\(j.id)")
                job = j
            }
            if j.status == "error" { jobError = "Workbook generation failed. See the log below." }
            await loadLists()
        } catch {
            jobError = error.localizedDescription
        }
    }

    @MainActor
    private func generateTasks() async {
        printerBusy = true
        defer { printerBusy = false }
        do {
            let r: TasksResponse = try await bridge.client.post("/tasks/generate", DaysRequest(days: taskDays))
            printerOutput = "Wrote \(r.count) tasks to \(r.path)"
        } catch {
            printerOutput = error.localizedDescription
        }
    }

    @MainActor
    private func printReceipts(preview: Bool) async {
        printerBusy = true
        defer { printerBusy = false }
        do {
            let r: PrintResult = try await bridge.client.post(
                "/tasks/print",
                PrintRequest(printer: printer, days: printDays, preview: preview, force: force)
            )
            printerOutput = r.output.isEmpty ? (r.ok ? "Done." : "Failed.") : r.output
        } catch {
            printerOutput = error.localizedDescription
        }
    }
}
