import Foundation

@MainActor
final class AkiMenuController: ObservableObject {
    static let shared = AkiMenuController()

    @Published var source: CaptureSource = .screen
    @Published var transform: TransformChoice = .ascii
    @Published var output: OutputChoice = .auto
    @Published private(set) var isRunning = false
    @Published private(set) var isPaused = false
    @Published private(set) var stats = AkiStats()
    @Published private(set) var statusText = "Stopped"

    private var process: Process?
    private var refreshTask: Task<Void, Never>?
    private let controlClient = AkiControlClient()

    func start() {
        guard process == nil else { return }

        let sidecar = SidecarBinaryResolver.resolve()
        let process = Process()
        process.executableURL = sidecar.executableURL
        process.arguments = sidecar.arguments(for: sidecarArguments())
        process.standardOutput = Pipe()
        process.standardError = Pipe()

        do {
            try process.run()
        } catch {
            statusText = "Could not start sidecar"
            return
        }

        self.process = process
        isRunning = true
        isPaused = false
        statusText = "Starting"
        startStatsRefresh()
    }

    func stop() {
        refreshTask?.cancel()
        refreshTask = nil

        if let process {
            process.terminate()
            process.waitUntilExit()
        }

        process = nil
        isRunning = false
        isPaused = false
        stats = AkiStats()
        statusText = "Stopped"
    }

    func togglePause() {
        guard isRunning else { return }
        Task {
            do {
                if isPaused {
                    try await controlClient.resume()
                    await MainActor.run {
                        isPaused = false
                        statusText = "Running"
                    }
                } else {
                    try await controlClient.pause()
                    await MainActor.run {
                        isPaused = true
                        statusText = "Paused"
                    }
                }
            } catch {
                await MainActor.run {
                    statusText = "Control unavailable"
                }
            }
        }
    }

    func applyTransformSelection() {
        guard isRunning else { return }
        let transform = transform
        Task {
            do {
                try await controlClient.switchMode(transform)
                await refreshStats()
            } catch {
                await MainActor.run {
                    statusText = "Transform pending"
                }
            }
        }
    }

    func restartIfRunning() {
        guard isRunning else { return }
        stop()
        start()
    }

    func openTUI() {
        TerminalLauncher.openTUI()
    }

    private func sidecarArguments() -> [String] {
        var args = ["--headless", "--transform", transform.sidecarValue, "--output", output.sidecarValue]
        args.append(contentsOf: source.sidecarArguments)
        return args
    }

    private func startStatsRefresh() {
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                await self?.refreshStats()
            }
        }
    }

    private func refreshStats() async {
        guard let process else { return }

        if !process.isRunning {
            await MainActor.run {
                self.process = nil
                self.isRunning = false
                self.isPaused = false
                self.statusText = "Sidecar exited"
            }
            return
        }

        do {
            let response = try await controlClient.stats()
            let cpu = ProcessSampler.cpuPercent(pid: process.processIdentifier)
            await MainActor.run {
                isPaused = response.paused ?? isPaused
                statusText = isPaused ? "Paused" : "Running"
                stats = AkiStats(
                    redactions: response.redactions ?? stats.redactions,
                    fps: response.fps ?? stats.fps,
                    cpu: cpu,
                    droppedFrames: response.droppedFrames ?? stats.droppedFrames
                )
            }
        } catch {
            await MainActor.run {
                statusText = "Waiting for control server"
                stats.cpu = ProcessSampler.cpuPercent(pid: process.processIdentifier)
            }
        }
    }
}
