import SwiftUI
import AppKit

struct SettingsView: View {
    @Environment(Bridge.self) private var bridge
    @State private var config = BridgeConfig()
    @State private var configLoaded = false
    @State private var saveNote = ""

    var body: some View {
        @Bindable var bridge = bridge
        Form {
            Section("Bridge") {
                LabeledContent("Status") { StatusPill() }
                HStack {
                    TextField("GoalManagement folder", text: $bridge.projectRoot)
                    Button("Choose…") { chooseFolder() }
                }
                TextField("Python (your .venv)", text: $bridge.pythonPath)
                TextField("Port", value: $bridge.port, format: .number.grouping(.never))
                HStack {
                    Button(bridge.isRunning ? "Restart bridge" : "Start bridge") {
                        bridge.saveSettings()
                        Task { await bridge.restart() }
                    }
                    Button("Stop") { bridge.stop() }.disabled(!bridge.isRunning)
                }
                Text("Restart after editing actions.py or changing the model.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Section("Offline") {
                if let h = bridge.health {
                    LabeledContent("Network guard", value: h.offlineGuard.active ? "On" : "Off")
                    LabeledContent("Hugging Face offline mode", value: h.hfOffline ? "On" : "Off")
                    LabeledContent("Allowed hosts",
                                   value: h.offlineGuard.allowHosts.isEmpty
                                       ? "None (fully offline)"
                                       : h.offlineGuard.allowHosts.joined(separator: ", "))
                    if !h.offlineGuard.recentBlocked.isEmpty {
                        LabeledContent("Recently blocked",
                                       value: h.offlineGuard.recentBlocked.suffix(5).joined(separator: "\n"))
                    }
                } else {
                    Text("Bridge not connected").foregroundStyle(.secondary)
                }
                Toggle("Allow the workbook's weather lookup (api.weather.gov only)", isOn: $config.allowWeather)
                    .disabled(!configLoaded)
                Text("Off means the model process cannot reach the internet at all; the workbook just skips the weather card.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Section("Model") {
                TextField("Model ID (blank = LOCAL_MODEL_ID from dailyWorkbookLocal.py)", text: $config.modelId)
                Stepper("Max reply length: \(config.maxTokens) tokens", value: $config.maxTokens, in: 100...4000, step: 100)
                HStack {
                    Text("Temperature")
                    Slider(value: $config.temperature, in: 0...1.2, step: 0.1)
                    Text(String(format: "%.1f", config.temperature)).monospacedDigit().frame(width: 32)
                }
                VStack(alignment: .leading) {
                    Text("Chat system prompt")
                    TextEditor(text: $config.systemPrompt)
                        .font(.body)
                        .frame(minHeight: 90)
                }
                HStack {
                    Button("Save model settings") { Task { await saveConfig() } }
                        .disabled(!configLoaded)
                    Text(saveNote).font(.caption).foregroundStyle(.secondary)
                }
            }

            Section("Bridge log") {
                ScrollView {
                    Text(bridge.log.suffix(200).joined(separator: "\n"))
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 220)
            }
        }
        .formStyle(.grouped)
        .task(id: bridge.health != nil) { await loadConfig() }
    }

    @MainActor
    private func loadConfig() async {
        guard bridge.health != nil else { return }
        let loaded: BridgeConfig? = try? await bridge.client.get("/config")
        if let c = loaded {
            config = c
            configLoaded = true
        }
    }

    @MainActor
    private func saveConfig() async {
        do {
            let old = bridge.health?.modelId ?? ""
            let c: BridgeConfig = try await bridge.client.post("/config", config)
            config = c
            let modelChanged = !c.modelId.isEmpty && c.modelId != old
            saveNote = modelChanged ? "Saved. Restart the bridge to load the new model." : "Saved."
            await bridge.refreshHealth()
        } catch {
            saveNote = error.localizedDescription
        }
    }

    @MainActor
    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.directoryURL = URL(fileURLWithPath: bridge.projectRoot)
        if panel.runModal() == .OK, let url = panel.url {
            bridge.projectRoot = url.path
            bridge.pythonPath = url.appendingPathComponent(".venv/bin/python3").path
            bridge.saveSettings()
        }
    }
}
