import Combine
import Foundation

@MainActor
final class PipelineStore: ObservableObject {
  @Published var source: SourceOption = .display
  @Published var transform: TransformOption = .redactionBox
  @Published var output: OutputOption = .preview
  @Published var state: PipelineRunState = .stopped
  @Published var stats = PipelineStats()
  @Published var lastError = ""

  private let sidecar: SidecarClient

  init(sidecar: SidecarClient = SidecarClient()) {
    self.sidecar = sidecar
    self.sidecar.onStats = { [weak self] stats in
      self?.stats = stats
    }
  }

  var canStart: Bool {
    state == .stopped || state == .paused || state == .error
  }

  var canPause: Bool {
    state == .running
  }

  var canStop: Bool {
    state == .running || state == .paused || state == .error
  }

  func start() {
    do {
      try sidecar.startIfNeeded()
      try sidecar.initialize()
      try sidecar.selectSource(source)
      try sidecar.selectTransform(transform)
      try sidecar.selectOutput(output)
      try sidecar.startCapture()
      state = .running
      lastError = ""
    } catch {
      fail(error)
    }
  }

  func pause() {
    do {
      try sidecar.pauseCapture()
      state = .paused
      lastError = ""
    } catch {
      fail(error)
    }
  }

  func stop() {
    do {
      try sidecar.stopCapture()
      state = .stopped
      lastError = ""
    } catch {
      fail(error)
    }
  }

  func openTUI() {
    do {
      try TerminalLauncher.open(command: "junas --tui")
    } catch {
      fail(error)
    }
  }

  func quit() {
    sidecar.shutdown()
  }

  private func fail(_ error: Error) {
    state = .error
    lastError = error.localizedDescription
    stats.lastError = lastError
  }
}
