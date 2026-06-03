import Foundation

struct ResolvedSidecar {
    let executableURL: URL
    let leadingArguments: [String]

    func arguments(for runtimeArguments: [String]) -> [String] {
        leadingArguments + runtimeArguments
    }
}

enum SidecarBinaryResolver {
    static func resolve(environment: [String: String] = ProcessInfo.processInfo.environment) -> ResolvedSidecar {
        if let configured = environment["AKI_BINARY"], !configured.isEmpty {
            return ResolvedSidecar(executableURL: URL(fileURLWithPath: configured), leadingArguments: [])
        }

        if let resourceURL = Bundle.main.resourceURL?.appendingPathComponent("aki"),
           FileManager.default.isExecutableFile(atPath: resourceURL.path) {
            return ResolvedSidecar(executableURL: resourceURL, leadingArguments: [])
        }

        let cwd = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        let localDebug = cwd.appendingPathComponent("target/debug/aki")
        if FileManager.default.isExecutableFile(atPath: localDebug.path) {
            return ResolvedSidecar(executableURL: localDebug, leadingArguments: [])
        }

        for path in ["/opt/homebrew/bin/aki", "/usr/local/bin/aki"] {
            if FileManager.default.isExecutableFile(atPath: path) {
                return ResolvedSidecar(executableURL: URL(fileURLWithPath: path), leadingArguments: [])
            }
        }

        return ResolvedSidecar(executableURL: URL(fileURLWithPath: "/usr/bin/env"), leadingArguments: ["aki"])
    }
}
