import SwiftUI

struct StatusWindowView: View {
  @ObservedObject var store: PipelineStore

  var body: some View {
    VStack(alignment: .leading, spacing: 14) {
      HStack {
        Label(store.state.title, systemImage: store.state.systemImage)
          .font(.title3)
        Spacer()
        Text(store.stats.menuLine)
          .foregroundStyle(.secondary)
      }

      Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
        GridRow {
          Text("Source")
            .foregroundStyle(.secondary)
          Picker("Source", selection: $store.source) {
            ForEach(SourceOption.allCases) { option in
              Text(option.title).tag(option)
            }
          }
          .labelsHidden()
        }
        GridRow {
          Text("Transform")
            .foregroundStyle(.secondary)
          Picker("Transform", selection: $store.transform) {
            ForEach(TransformOption.allCases) { option in
              Text(option.title).tag(option)
            }
          }
          .labelsHidden()
        }
        GridRow {
          Text("Output")
            .foregroundStyle(.secondary)
          Picker("Output", selection: $store.output) {
            ForEach(OutputOption.allCases) { option in
              Text(option.title).tag(option)
            }
          }
          .labelsHidden()
        }
      }

      HStack {
        Button("Start") { store.start() }
          .keyboardShortcut("r", modifiers: [.command])
          .disabled(!store.canStart)
        Button("Pause") { store.pause() }
          .keyboardShortcut("p", modifiers: [.command])
          .disabled(!store.canPause)
        Button("Stop") { store.stop() }
          .keyboardShortcut(".", modifiers: [.command])
          .disabled(!store.canStop)
        Spacer()
        Button("Open TUI") { store.openTUI() }
      }

      LabeledContent("Frames", value: "\(store.stats.framesProcessed)")
      LabeledContent("Redactions", value: "\(store.stats.redactionCount)")
      LabeledContent("FPS", value: store.stats.fpsText)
      LabeledContent("CPU", value: store.stats.cpuText)

      if !store.lastError.isEmpty {
        Text(store.lastError)
          .foregroundStyle(.red)
          .textSelection(.enabled)
      }
    }
    .padding(18)
    .frame(minWidth: 420, minHeight: 300)
  }
}
