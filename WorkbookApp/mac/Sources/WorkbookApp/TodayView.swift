import SwiftUI
import AppKit

struct RunningAction: Identifiable {
    let id = UUID()
    let card: Card
    let action: ActionInfo
}

struct TodayView: View {
    @Environment(Bridge.self) private var bridge
    @Environment(AppModel.self) private var app
    @State private var today: TodayResponse?
    @State private var loadError: String?
    @State private var dayOffset = 0
    @State private var running: RunningAction?

    private var reloadKey: String { "\(dayOffset)-\(bridge.health != nil)" }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                if let loadError {
                    Banner(text: loadError)
                }
                if let today {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 300), spacing: 14)], spacing: 14) {
                        ForEach(today.cards) { card in
                            CardView(
                                card: card,
                                actions: app.actions.filter { $0.applies(to: card.kind) },
                                canRun: bridge.isReady,
                                onAction: { running = RunningAction(card: card, action: $0) },
                                onChat: { app.askInChat(about: card) }
                            )
                        }
                    }
                    if !today.parkingLot.isEmpty {
                        parkingLot(today.parkingLot)
                    }
                } else if loadError == nil {
                    ProgressView().frame(maxWidth: .infinity).padding(40)
                }
            }
            .padding(22)
        }
        .task(id: reloadKey) { await load() }
        .sheet(item: $running) { run in
            ActionRunView(run: run)
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text(today?.label ?? "Today").font(.largeTitle.bold())
                if let t = today {
                    Text("\(dayTypeLabel(t.dayType))  ·  Study day \(t.certDay)")
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            HStack(spacing: 4) {
                Button { dayOffset -= 1 } label: { Image(systemName: "chevron.left") }
                Button("Today") { dayOffset = 0 }.disabled(dayOffset == 0)
                Button { dayOffset += 1 } label: { Image(systemName: "chevron.right") }
                Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") }
                    .help("Reload")
            }
        }
    }

    private func parkingLot(_ ideas: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("PARKING LOT").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            FlowLayout(spacing: 8) {
                ForEach(Array(ideas.enumerated()), id: \.offset) { _, idea in
                    Text(idea)
                        .font(.callout)
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .background(Capsule().fill(Color.secondary.opacity(0.12)))
                }
            }
        }
    }

    private func dayTypeLabel(_ t: String) -> String {
        switch t {
        case "work": return "Work day, lighter study"
        case "free": return "Free day, deep study"
        case "therapy": return "Light day"
        case "weekend": return "Weekend, your pace"
        default: return t.capitalized
        }
    }

    @MainActor
    private func load() async {
        guard bridge.health != nil else { return }
        let date = Calendar.current.date(byAdding: .day, value: dayOffset, to: Date()) ?? Date()
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        do {
            let t: TodayResponse = try await bridge.client.get("/today?date=\(f.string(from: date))")
            let a: ActionsResponse = try await bridge.client.get("/actions")
            today = t
            app.actions = a.actions
            loadError = nil
        } catch {
            loadError = error.localizedDescription
        }
    }
}

struct CardView: View {
    let card: Card
    let actions: [ActionInfo]
    let canRun: Bool
    let onAction: (ActionInfo) -> Void
    let onChat: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(card.course.uppercased())
                    .font(.caption.weight(.bold))
                    .foregroundStyle(card.tint)
                Spacer()
                if let link = card.link {
                    Link(destination: link) { Image(systemName: "arrow.up.right.square") }
                        .help("Open reference in your browser: \(link.absoluteString)")
                }
            }
            Text(card.title).font(.headline)
            Text(card.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if let words = card.words, !words.isEmpty {
                FlowLayout(spacing: 6) {
                    ForEach(words, id: \.char) { w in
                        VStack(spacing: 0) {
                            Text(w.char).font(.title3)
                            Text(w.pinyin).font(.caption2).foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(RoundedRectangle(cornerRadius: 6).fill(card.tint.opacity(0.1)))
                        .help(w.meaning)
                    }
                }
            }
            Spacer(minLength: 4)
            FlowLayout(spacing: 6) {
                ForEach(actions) { a in
                    Button { onAction(a) } label: { Label(a.label, systemImage: a.icon) }
                }
                Button(action: onChat) { Label("Ask in chat", systemImage: "bubble.left") }
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(!canRun)
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 12).fill(card.tint.opacity(0.06)))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(card.tint.opacity(0.25)))
    }
}

struct ActionRunView: View {
    let run: RunningAction
    @Environment(Bridge.self) private var bridge
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var output = ""
    @State private var status = "Thinking…"
    @State private var finished = false
    @State private var task: Task<Void, Never>?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(run.action.label, systemImage: run.action.icon).font(.headline)
                Text(run.card.title).foregroundStyle(.secondary).lineLimit(1)
                Spacer()
                Text(status).font(.caption).foregroundStyle(.secondary)
            }
            ScrollView {
                Text(output.isEmpty ? " " : output)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
            }
            .background(RoundedRectangle(cornerRadius: 8).fill(Color(nsColor: .textBackgroundColor)))
            HStack {
                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(output, forType: .string)
                }
                .disabled(output.isEmpty)
                Button("Continue in chat") {
                    app.continueInChat(prompt: "\(run.action.label): \(run.card.course), \(run.card.title)", answer: output)
                    dismiss()
                }
                .disabled(!finished || output.isEmpty)
                Spacer()
                if !finished {
                    Button("Stop") { task?.cancel() }
                }
                Button("Close") {
                    task?.cancel()
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)
            }
        }
        .padding(20)
        .frame(width: 660, height: 540)
        .onAppear(perform: start)
        .onDisappear { task?.cancel() }
    }

    @MainActor
    private func start() {
        guard task == nil else { return }
        let client = bridge.client
        let body = ActionRunRequest(action: run.action.id, item: run.card)
        task = Task {
            do {
                for try await event in client.stream("/actions/run", body) {
                    switch event.t {
                    case "token":
                        output += event.text ?? ""
                        status = "Writing…"
                    case "done":
                        status = event.statsLine
                    case "error":
                        status = event.error ?? "Error"
                    default:
                        break
                    }
                }
            } catch {
                if !Task.isCancelled { status = error.localizedDescription }
            }
            if Task.isCancelled { status = "Stopped" }
            finished = true
        }
    }
}
