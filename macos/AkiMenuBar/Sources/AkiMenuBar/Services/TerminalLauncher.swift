import AppKit
import Foundation

enum TerminalLauncher {
    static func openTUI() {
        let sidecar = SidecarBinaryResolver.resolve()
        let command = shellCommand(executable: sidecar.executableURL.path, arguments: sidecar.leadingArguments + ["run"])
        let script = """
        tell application "Terminal"
          activate
          do script "\(escapeAppleScript(command))"
        end tell
        """
        var error: NSDictionary?
        NSAppleScript(source: script)?.executeAndReturnError(&error)
    }

    private static func shellCommand(executable: String, arguments: [String]) -> String {
        ([executable] + arguments).map(shellQuote).joined(separator: " ")
    }

    private static func shellQuote(_ value: String) -> String {
        "'\(value.replacingOccurrences(of: "'", with: "'\\''"))'"
    }

    private static func escapeAppleScript(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
    }
}
