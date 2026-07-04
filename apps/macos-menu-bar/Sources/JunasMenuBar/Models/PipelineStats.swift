import Foundation

enum PipelineRunState: String {
  case stopped
  case running
  case paused
  case error

  var title: String {
    switch self {
    case .stopped: "Stopped"
    case .running: "Running"
    case .paused: "Paused"
    case .error: "Error"
    }
  }

  var systemImage: String {
    switch self {
    case .stopped: "shield"
    case .running: "shield.lefthalf.filled"
    case .paused: "pause.circle"
    case .error: "exclamationmark.triangle"
    }
  }
}

struct PipelineStats: Equatable {
  var redactionCount = 0
  var framesProcessed = 0
  var fps = 0.0
  var cpu = 0.0
  var lastError = ""

  var menuLine: String {
    "Redactions \(redactionCount) | \(fpsText) FPS | CPU \(cpuText)"
  }

  var fpsText: String {
    String(format: "%.1f", fps)
  }

  var cpuText: String {
    String(format: "%.0f%%", cpu)
  }
}
