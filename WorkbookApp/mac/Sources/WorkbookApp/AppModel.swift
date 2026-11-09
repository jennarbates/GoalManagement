import Foundation
import Observation

enum AppTab: String, CaseIterable, Identifiable, Hashable {
    case today, chat, workbook, settings

    var id: String { rawValue }
    var title: String {
        switch self {
        case .today: return "Today"
        case .chat: return "Chat"
        case .workbook: return "Workbook & Printer"
        case .settings: return "Settings"
        }
    }
    var icon: String {
        switch self {
        case .today: return "sun.max"
        case .chat: return "bubble.left.and.bubble.right"
        case .workbook: return "printer"
        case .settings: return "gearshape"
        }
    }
}

@Observable
final class AppModel {
    var tab: AppTab? = .today
    var actions: [ActionInfo] = []
    let chat = ChatStore()
    /// Kept here so a running workbook job survives switching tabs.
    var workbookJob: Job?

    @MainActor
    func askInChat(about card: Card) {
        chat.draft = "Help me with today's \(card.course) task: \(card.title). \(card.detail)"
        tab = .chat
    }

    @MainActor
    func continueInChat(prompt: String, answer: String) {
        chat.reset()
        chat.messages = [
            ChatMessage(role: "user", content: prompt),
            ChatMessage(role: "assistant", content: answer),
        ]
        tab = .chat
    }
}

struct ChatMessage: Identifiable, Equatable {
    let id = UUID()
    var role: String
    var content: String
}

@Observable
final class ChatStore {
    var messages: [ChatMessage] = []
    var draft = ""
    var isStreaming = false
    var stats = ""
    var error: String?

    /// How many past messages to send with each request (keeps prompts fast).
    let historyLimit = 20

    @ObservationIgnored private var task: Task<Void, Never>?
    @ObservationIgnored private var generation = 0

    @MainActor
    func send(client: BridgeClient) {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isStreaming else { return }
        draft = ""
        error = nil
        messages.append(ChatMessage(role: "user", content: text))
        let history = messages.suffix(historyLimit).map { ChatPayloadMessage(role: $0.role, content: $0.content) }
        messages.append(ChatMessage(role: "assistant", content: ""))
        let index = messages.count - 1
        isStreaming = true
        stats = "Thinking…"
        generation += 1
        let myGeneration = generation

        task = Task {
            do {
                for try await event in client.stream("/chat", ChatRequest(messages: Array(history))) {
                    guard myGeneration == generation else { break }
                    switch event.t {
                    case "token":
                        if index < messages.count { messages[index].content += event.text ?? "" }
                        stats = "Writing…"
                    case "done":
                        stats = event.statsLine
                    case "error":
                        self.error = event.error
                    default:
                        break
                    }
                }
            } catch {
                if !Task.isCancelled && myGeneration == generation {
                    self.error = error.localizedDescription
                    stats = ""
                }
            }
            guard myGeneration == generation else { return }   // chat was reset meanwhile
            if Task.isCancelled { stats = "Stopped" }
            if index < messages.count, messages[index].content.isEmpty {
                messages.remove(at: index)
            }
            isStreaming = false
        }
    }

    @MainActor
    func stop() {
        task?.cancel()
    }

    @MainActor
    func reset() {
        task?.cancel()
        task = nil
        generation += 1
        isStreaming = false
        messages = []
        stats = ""
        error = nil
    }
}
