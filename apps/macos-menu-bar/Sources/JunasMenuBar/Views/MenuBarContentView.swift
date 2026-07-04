import AppKit
import SwiftUI

struct MenuBarContentView: View {
  @Environment(\.openWindow) private var openWindow
  @ObservedObject var store: PipelineStore

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      Label(store.state.title, systemImage: store.state.systemImage)
      Picker("Source", selection: $store.source) {
        ForEach(SourceOption.allCases) { option in
          Text(option.title).tag(option)
        }
      }
      Picker("Transform", selection: $store.transform) {
        ForEach(TransformOption.allCases) { option in
          Text(option.title).tag(option)
        }
      }
      Picker("Output", selection: $store.output) {
        ForEach(OutputOption.allCases) { option in
          Text(option.title).tag(option)
        }
      }
      Divider()
      HStack {
        Button("Start") {
          store.start()
        }
        .disabled(!store.canStart)

        Button("Pause") {
          store.pause()
        }
        .disabled(!store.canPause)

        Button("Stop") {
          store.stop()
        }
        .disabled(!store.canStop)
      }
      Text(store.stats.menuLine)
        .font(.caption)
        .foregroundStyle(.secondary)
      if !store.lastError.isEmpty {
        Text(store.lastError)
          .font(.caption)
          .foregroundStyle(.red)
          .lineLimit(2)
      }
      Divider()
      Button("Open Status") {
        openWindow(id: "main")
      }
      Button("Open TUI") {
        store.openTUI()
      }
      Button("Quit") {
        store.quit()
        NSApplication.shared.terminate(nil)
      }
    }
    .padding(10)
    .frame(width: 260)
  }
}
