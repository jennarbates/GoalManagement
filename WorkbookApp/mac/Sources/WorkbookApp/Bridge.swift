import Foundation
import Observation

/// Owns the Python bridge process: starts it with your .venv Python, reads its
/// log, polls /health, and stops it when the app quits.
@MainActor
@Observable
final class Bridge {
    static let shared = Bridge()

    enum RunState: Equatable {
        case stopped
        case starting
        case running
        case failed(String)
    }

    // Settings (saved with saveSettings())
    var projectRoot: String
    var pythonPath: String
    var port: Int

    private(set) var runState: RunState = .stopped
    private(set) var health: Health?
    private(set) var log: [String] = []
    private(set) var connectionProblem: String?

    @ObservationIgnored private var process: Process?
    @ObservationIgnored private var pollTask: Task<Void, Never>?
    @ObservationIgnored private var stopping = false
    let token = UUID().uuidString

    /// Port of the bridge that is actually running (settings may differ until restart).
    private(set) var activePort = 8765

    var client: BridgeClient { BridgeClient(port: activePort, token: token) }
    var isReady: Bool { health?.modelStatus == "ready" }
    var isRunning: Bool { runState == .starting || runState == .running }

    /// One line describing anything that needs attention, or nil.
    var problem: String? {
        if case .failed(let msg) = runState { return msg }
        if let connectionProblem { return connectionProblem }
        if let h = health, h.modelStatus == "error" { return "Model failed to load: \(h.modelError)" }
        return nil
    }

    private init() {
        let d = UserDefaults.standard
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let root = d.string(forKey: "projectRoot") ?? "\(home)/Documents/Development/GoalManagement"
        projectRoot = root
        pythonPath = d.string(forKey: "pythonPath") ?? "\(root)/.venv/bin/python3"
        let p = d.integer(forKey: "port")
        port = p == 0 ? 8765 : p
    }

    func saveSettings() {
        let d = UserDefaults.standard
        d.set(projectRoot, forKey: "projectRoot")
        d.set(pythonPath, forKey: "pythonPath")
        d.set(port, forKey: "port")
    }

    // MARK: Process lifecycle

    func start() {
        guard process == nil else { return }
        connectionProblem = nil
        let fm = FileManager.default
        let script = URL(fileURLWithPath: projectRoot)
            .appendingPathComponent("WorkbookApp/bridge/workbook_bridge.py")

        guard fm.isExecutableFile(atPath: pythonPath) else {
            runState = .failed("Python not found at \(pythonPath). Fix it in Settings.")
            return
        }
        guard fm.fileExists(atPath: script.path) else {
            runState = .failed("Bridge script not found at \(script.path). Check the project folder in Settings.")
            return
        }

        activePort = port
        let p = Process()
        p.executableURL = URL(fileURLWithPath: pythonPath)
        p.arguments = ["-u", script.path, "--port", String(port), "--root", projectRoot, "--exit-with-parent"]
        p.currentDirectoryURL = URL(fileURLWithPath: projectRoot)

        var env = ProcessInfo.processInfo.environment
        env["WORKBOOK_BRIDGE_TOKEN"] = token
        env["PYTHONUNBUFFERED"] = "1"
        // Apps opened from Finder get a minimal PATH; add Homebrew so tools
        // like wkhtmltopdf (used for the PDF) are found.
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        p.environment = env

        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in self?.appendLog(text) }
        }
        p.terminationHandler = { [weak self] proc in
            let code = proc.terminationStatus
            let pid = proc.processIdentifier
            pipe.fileHandleForReading.readabilityHandler = nil
            Task { @MainActor in self?.processEnded(pid: pid, code: code) }
        }

        do {
            try p.run()
            process = p
            stopping = false
            runState = .starting
            appendLog("[app] started bridge (pid \(p.processIdentifier)) on port \(port)\n")
            startPolling()
        } catch {
            runState = .failed("Could not start the bridge: \(error.localizedDescription)")
        }
    }

    func stop() {
        guard let p = process else { return }
        stopping = true
        p.terminate()
    }

    /// Used on app quit: synchronous and quick.
    func stopNow() {
        pollTask?.cancel()
        process?.terminate()
    }

    func restart() async {
        stop()
        var waited = 0
        while process != nil && waited < 40 {
            try? await Task.sleep(for: .milliseconds(100))
            waited += 1
        }
        if let p = process {                // did not exit in 4s, force it
            kill(p.processIdentifier, SIGKILL)
            try? await Task.sleep(for: .milliseconds(300))
            process = nil
            runState = .stopped
        }
        start()
    }

    private func processEnded(pid: Int32, code: Int32) {
        // Ignore a late exit from an older process after a restart.
        if let current = process, current.processIdentifier != pid { return }
        process = nil
        pollTask?.cancel()
        health = nil
        appendLog("[app] bridge exited with code \(code)\n")
        if stopping || code == 0 || code == 15 {
            runState = .stopped
        } else {
            runState = .failed("The bridge stopped unexpectedly (exit code \(code)). See the log in Settings.")
        }
        stopping = false
    }

    private func appendLog(_ text: String) {
        let lines = text.split(separator: "\n", omittingEmptySubsequences: true).map(String.init)
        log.append(contentsOf: lines)
        if log.count > 500 { log.removeFirst(log.count - 500) }
    }

    // MARK: Health polling

    private func startPolling() {
        pollTask?.cancel()
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refreshHealth()
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    func refreshHealth() async {
        do {
            let h: Health = try await client.get("/health")
            if health != h { health = h }
            connectionProblem = nil
            if runState == .starting { runState = .running }
        } catch BridgeError.http(403, _) {
            connectionProblem = "Port \(port) is taken by another program (maybe an old bridge). Change the port in Settings or quit that program."
        } catch {
            // Still booting; only complain once we had a connection before.
            if runState == .running {
                connectionProblem = "Lost connection to the bridge: \(error.localizedDescription)"
            }
        }
    }
}
