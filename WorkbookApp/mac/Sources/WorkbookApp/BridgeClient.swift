import Foundation

enum BridgeError: LocalizedError {
    case http(Int, String)
    case badResponse

    var errorDescription: String? {
        switch self {
        case .http(let code, let message):
            return message.isEmpty ? "Bridge returned HTTP \(code)" : message
        case .badResponse:
            return "Unexpected response from the bridge"
        }
    }
}

/// Talks to workbook_bridge.py on 127.0.0.1. Proxies are disabled so traffic
/// never leaves the machine, even if a system proxy is configured.
struct BridgeClient: Sendable {
    let port: Int
    let token: String

    static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.connectionProxyDictionary = [:]
        config.timeoutIntervalForRequest = 600
        config.timeoutIntervalForResource = 3600
        config.waitsForConnectivity = false
        config.urlCache = nil
        return URLSession(configuration: config)
    }()

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    private func request(_ path: String, method: String, body: Data?) -> URLRequest {
        var r = URLRequest(url: URL(string: "http://127.0.0.1:\(port)\(path)")!)
        r.httpMethod = method
        r.setValue(token, forHTTPHeaderField: "X-Bridge-Token")
        if let body {
            r.httpBody = body
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return r
    }

    func get<T: Decodable>(_ path: String) async throws -> T {
        try await send(request(path, method: "GET", body: nil))
    }

    func post<T: Decodable, B: Encodable>(_ path: String, _ body: B) async throws -> T {
        try await send(request(path, method: "POST", body: try Self.encoder.encode(body)))
    }

    private func send<T: Decodable>(_ req: URLRequest) async throws -> T {
        let (data, response) = try await Self.session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw BridgeError.badResponse }
        guard http.statusCode == 200 else {
            throw BridgeError.http(http.statusCode, Self.errorMessage(data))
        }
        return try Self.decoder.decode(T.self, from: data)
    }

    static func errorMessage(_ data: Data) -> String {
        if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let msg = obj["error"] as? String {
            return msg
        }
        return String(data: data, encoding: .utf8) ?? ""
    }

    /// POST and read newline-delimited JSON events as they arrive.
    /// Cancelling the consuming task closes the connection, which makes the
    /// bridge stop generating.
    func stream<B: Encodable>(_ path: String, _ body: B) -> AsyncThrowingStream<StreamEvent, Error> {
        let req = request(path, method: "POST", body: try? Self.encoder.encode(body))
        return AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let (bytes, response) = try await Self.session.bytes(for: req)
                    guard let http = response as? HTTPURLResponse else { throw BridgeError.badResponse }
                    if http.statusCode != 200 {
                        var data = Data()
                        for try await b in bytes { data.append(b) }
                        throw BridgeError.http(http.statusCode, Self.errorMessage(data))
                    }
                    for try await line in bytes.lines {
                        guard let d = line.data(using: .utf8),
                              let event = try? Self.decoder.decode(StreamEvent.self, from: d) else { continue }
                        continuation.yield(event)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
