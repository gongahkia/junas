import Foundation

enum TerminalLauncher {
  static func open(command: String) throws {
    let script = """
    tell application "Terminal"
      activate
      do script "\(escape(command))"
    end tell
    """
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    process.arguments = ["-e", script]
    try process.run()
  }

  private static func escape(_ value: String) -> String {
    value.replacingOccurrences(of: "\\", with: "\\\\")
      .replacingOccurrences(of: "\"", with: "\\\"")
  }
}
