import SwiftUI

// Everything the bridge sends back. Keys arrive in snake_case and are
// converted to camelCase by BridgeClient's decoder.

struct Health: Decodable, Equatable {
    struct Guard: Decodable, Equatable {
        var active: Bool
        var allowHosts: [String]
        var recentBlocked: [String]
    }
    var ok: Bool
    var modelId: String
    var modelStatus: String      // not_loaded | loading | ready | error
    var modelError: String
    var busy: String
    var offlineGuard: Guard
    var hfOffline: Bool
    var root: String
    var python: String
}

struct Word: Codable, Hashable {
    var char: String
    var pinyin: String
    var meaning: String
}

struct Card: Codable, Identifiable, Hashable {
    var id: String
    var kind: String
    var course: String
    var title: String
    var detail: String
    var url: String
    var dayType: String?
    var words: [Word]?

    var link: URL? { url.isEmpty ? nil : URL(string: url) }

    var tint: Color {
        switch kind {
        case "algorithms": return .purple
        case "hsk": return .red
        case "chore": return .green
        default: return .gray
        }
    }
}

struct TodayResponse: Decodable {
    var date: String
    var label: String
    var dayType: String
    var certDay: Int
    var cards: [Card]
    var parkingLot: [String]
}

struct ActionInfo: Decodable, Identifiable, Hashable {
    var id: String
    var label: String
    var kinds: [String]
    var icon: String

    func applies(to kind: String) -> Bool { kinds.contains("*") || kinds.contains(kind) }
}

struct ActionsResponse: Decodable { var actions: [ActionInfo] }

struct Job: Decodable {
    var id: String
    var kind: String
    var status: String           // running | done | error
    var log: String
    var result: [String: String]
}

struct WorkbookFile: Decodable, Identifiable {
    var date: String
    var html: String
    var pdf: String
    var id: String { date }
}

struct WorkbooksResponse: Decodable { var workbooks: [WorkbookFile] }

struct PrintersResponse: Decodable {
    var printers: [String]
    var saved: String
}

struct TasksResponse: Decodable {
    var path: String
    var count: Int
}

struct PrintResult: Decodable {
    var ok: Bool
    var output: String
}

struct BridgeConfig: Codable, Equatable {
    var modelId: String = ""
    var allowWeather: Bool = false
    var maxTokens: Int = 1200
    var temperature: Double = 0.6
    var systemPrompt: String = ""
}

struct StreamEvent: Decodable {
    var t: String                // token | done | error
    var text: String?
    var error: String?
    var tokens: Int?
    var tps: Double?
    var seconds: Double?

    var statsLine: String {
        var parts: [String] = []
        if let tokens { parts.append("\(tokens) tokens") }
        if let tps { parts.append(String(format: "%.1f tok/s", tps)) }
        if let seconds { parts.append(String(format: "%.1fs", seconds)) }
        return parts.joined(separator: ", ")
    }
}

// Request bodies

struct EmptyBody: Codable {}

struct ChatPayloadMessage: Codable {
    var role: String
    var content: String
}

struct ChatRequest: Encodable {
    var messages: [ChatPayloadMessage]
}

struct ActionRunRequest: Encodable {
    var action: String
    var item: Card
}

struct DaysRequest: Encodable { var days: Int }

struct PrintRequest: Encodable {
    var printer: String
    var days: Int
    var preview: Bool
    var force: Bool
}
