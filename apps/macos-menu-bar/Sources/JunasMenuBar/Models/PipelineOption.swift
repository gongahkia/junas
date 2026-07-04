import Foundation

protocol PipelineOption: CaseIterable, Hashable, Identifiable where AllCases: RandomAccessCollection {
  var title: String { get }
  var jsonParams: [String: Any] { get }
}

enum SourceOption: String, PipelineOption {
  case display
  case window
  case file
  case clipboard

  var id: String { rawValue }

  var title: String {
    switch self {
    case .display: "Display"
    case .window: "Window"
    case .file: "File"
    case .clipboard: "Clipboard"
    }
  }

  var jsonParams: [String: Any] {
    switch self {
    case .display:
      ["kind": rawValue, "id": "main-display"]
    case .window:
      ["kind": rawValue, "id": "frontmost-window"]
    case .file:
      ["kind": rawValue, "id": "selected-file"]
    case .clipboard:
      ["kind": rawValue, "id": "clipboard"]
    }
  }
}

enum TransformOption: String, PipelineOption {
  case reviewOnly = "review_only"
  case redactionBox = "redaction_box"
  case anonymize

  var id: String { rawValue }

  var title: String {
    switch self {
    case .reviewOnly: "Review"
    case .redactionBox: "Redact"
    case .anonymize: "Anonymize"
    }
  }

  var jsonParams: [String: Any] {
    ["kind": rawValue]
  }
}

enum OutputOption: String, PipelineOption {
  case preview
  case mp4
  case obs
  case none

  var id: String { rawValue }

  var title: String {
    switch self {
    case .preview: "Preview"
    case .mp4: "MP4"
    case .obs: "OBS"
    case .none: "None"
    }
  }

  var jsonParams: [String: Any] {
    ["kind": rawValue]
  }
}
