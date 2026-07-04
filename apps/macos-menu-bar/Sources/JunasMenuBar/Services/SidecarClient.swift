import Foundation

struct SidecarClientError: LocalizedError {
  let message: String

  var errorDescription: String? {
    message
  }
}

@MainActor
final class SidecarClient {
  var onStats: ((PipelineStats) -> Void)?

  private let executable: String
  private let arguments: [String]
  private var process: Process?
  private var inputHandle: FileHandle?
  private var outputHandle: FileHandle?
  private var nextID = 1

  init(environment: [String: String] = ProcessInfo.processInfo.environment) {
    let configured = environment["JUNAS_SIDECAR_COMMAND"]?.split(separator: " ").map(String.init) ?? []
    if let first = configured.first {
      executable = first
      arguments = Array(configured.dropFirst())
    } else if let bundled = Bundle.main.resourceURL?.appending(path: "aki-sidecar/aki-sidecar"),
      FileManager.default.isExecutableFile(atPath: bundled.path)
    {
      executable = bundled.path
      arguments = []
    } else {
      executable = "/usr/bin/env"
      arguments = ["aki", "sidecar", "stdio"]
    }
  }

  func startIfNeeded() throws {
    if process?.isRunning == true {
      return
    }
    let input = Pipe()
    let output = Pipe()
    let launched = Process()
    launched.executableURL = URL(fileURLWithPath: executable)
    launched.arguments = arguments
    launched.standardInput = input
    launched.standardOutput = output
    launched.standardError = Pipe()
    try launched.run()
    process = launched
    inputHandle = input.fileHandleForWriting
    outputHandle = output.fileHandleForReading
  }

  func initialize() throws {
    _ = try request(method: "initialize")
  }

  func selectSource(_ source: SourceOption) throws {
    _ = try request(method: "source.select", params: source.jsonParams)
  }

  func selectTransform(_ transform: TransformOption) throws {
    _ = try request(method: "transform.select", params: transform.jsonParams)
  }

  func selectOutput(_ output: OutputOption) throws {
    _ = try request(method: "output.select", params: output.jsonParams)
  }

  func startCapture() throws {
    _ = try request(method: "capture.start")
  }

  func pauseCapture() throws {
    _ = try request(method: "capture.pause")
  }

  func stopCapture() throws {
    _ = try request(method: "capture.stop")
  }

  func shutdown() {
    _ = try? request(method: "shutdown")
    inputHandle?.closeFile()
    process?.terminate()
    process = nil
    inputHandle = nil
    outputHandle = nil
  }

  private func request(method: String, params: [String: Any] = [:]) throws -> [String: Any] {
    try startIfNeeded()
    guard let inputHandle, let outputHandle else {
      throw SidecarClientError(message: "sidecar pipes are unavailable")
    }
    let requestID = nextID
    nextID += 1
    let payload: [String: Any] = [
      "jsonrpc": "2.0",
      "id": requestID,
      "method": method,
      "params": params,
    ]
    let data = try JSONSerialization.data(withJSONObject: payload)
    inputHandle.write(data)
    inputHandle.write(Data([10]))
    while true {
      let message = try readJSONLine(from: outputHandle)
      if let notification = message["method"] as? String, notification == "stats.update" {
        if let params = message["params"] as? [String: Any] {
          onStats?(Self.stats(from: params))
        }
        continue
      }
      if let id = message["id"] as? Int, id == requestID {
        if let error = message["error"] as? [String: Any] {
          let detail = error["message"] as? String ?? "sidecar request failed"
          throw SidecarClientError(message: detail)
        }
        return message["result"] as? [String: Any] ?? [:]
      }
    }
  }

  private func readJSONLine(from handle: FileHandle) throws -> [String: Any] {
    var data = Data()
    while true {
      guard let byte = try handle.read(upToCount: 1), !byte.isEmpty else {
        throw SidecarClientError(message: "sidecar closed stdout")
      }
      if byte.first == 10 {
        break
      }
      data.append(byte)
    }
    let object = try JSONSerialization.jsonObject(with: data)
    guard let message = object as? [String: Any] else {
      throw SidecarClientError(message: "sidecar emitted a non-object response")
    }
    return message
  }

  private static func stats(from params: [String: Any]) -> PipelineStats {
    PipelineStats(
      redactionCount: params["redaction_count"] as? Int ?? 0,
      framesProcessed: params["frames_processed"] as? Int ?? 0,
      fps: params["fps"] as? Double ?? 0,
      cpu: params["cpu"] as? Double ?? 0,
      lastError: params["last_error"] as? String ?? ""
    )
  }
}
