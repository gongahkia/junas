import Foundation

enum CaptureSource: String, CaseIterable, Identifiable {
    case screen = "Screen capture"
    case pty = "PTY terminal"

    var id: String { rawValue }
    var sidecarArguments: [String] {
        switch self {
        case .screen:
            []
        case .pty:
            ["--pty"]
        }
    }
}

enum TransformChoice: String, CaseIterable, Identifiable, Codable {
    case blur = "Blur"
    case pixelate = "Pixelate"
    case cartoon = "Cartoon"
    case ascii = "ASCII"
    case neural = "Neural"

    var id: String { rawValue }
    var sidecarValue: String { rawValue.lowercased() }
}

enum OutputChoice: String, CaseIterable, Identifiable {
    case auto = "Auto"
    case coremedia = "Virtual camera"
    case mjpeg = "MJPEG"
    case obs = "OBS browser"

    var id: String { rawValue }
    var sidecarValue: String {
        switch self {
        case .auto:
            "auto"
        case .coremedia:
            "coremedia"
        case .mjpeg:
            "mjpeg"
        case .obs:
            "obs"
        }
    }
}

struct AkiStats: Equatable {
    var redactions: UInt64 = 0
    var fps: Double = 0
    var cpu: Double?
    var droppedFrames: UInt64 = 0

    var summary: String {
        let cpuText = cpu.map { "\(Int($0.rounded()))% CPU" } ?? "--% CPU"
        return "\(redactions) redactions · \(String(format: "%.0f", fps)) fps · \(cpuText)"
    }
}

struct ControlStatsResponse: Decodable {
    let ok: Bool
    let mode: String?
    let paused: Bool?
    let fps: Double?
    let redactions: UInt64?
    let droppedFrames: UInt64?

    enum CodingKeys: String, CodingKey {
        case ok
        case mode
        case paused
        case fps
        case redactions
        case droppedFrames = "dropped_frames"
    }
}
