import Foundation

actor AkiControlClient {
    private let url = URL(string: "ws://127.0.0.1:9877")!
    private let decoder = JSONDecoder()

    func pause() async throws {
        _ = try await send(["cmd": "pause"])
    }

    func resume() async throws {
        _ = try await send(["cmd": "resume"])
    }

    func switchMode(_ mode: TransformChoice) async throws {
        _ = try await send(["cmd": "switch_mode", "mode": mode.sidecarValue])
    }

    func stats() async throws -> ControlStatsResponse {
        let data = try await send(["cmd": "get_stats"])
        return try decoder.decode(ControlStatsResponse.self, from: data)
    }

    private func send(_ payload: [String: String]) async throws -> Data {
        let task = URLSession.shared.webSocketTask(with: url)
        task.resume()
        defer {
            task.cancel(with: .goingAway, reason: nil)
        }

        let data = try JSONSerialization.data(withJSONObject: payload)
        let text = String(decoding: data, as: UTF8.self)
        try await task.send(.string(text))
        let response = try await task.receive()

        switch response {
        case .data(let data):
            return data
        case .string(let text):
            return Data(text.utf8)
        @unknown default:
            throw URLError(.badServerResponse)
        }
    }
}
