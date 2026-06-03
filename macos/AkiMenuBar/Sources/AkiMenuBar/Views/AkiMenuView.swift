import SwiftUI

struct AkiMenuView: View {
    @ObservedObject var controller: AkiMenuController

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header

            Divider()

            Picker("Source", selection: sourceBinding) {
                ForEach(CaptureSource.allCases) { source in
                    Text(source.rawValue).tag(source)
                }
            }

            Picker("Transform", selection: transformBinding) {
                ForEach(TransformChoice.allCases) { transform in
                    Text(transform.rawValue).tag(transform)
                }
            }

            Picker("Output", selection: outputBinding) {
                ForEach(OutputChoice.allCases) { output in
                    Text(output.rawValue).tag(output)
                }
            }

            HStack(spacing: 10) {
                Button {
                    controller.isRunning ? controller.stop() : controller.start()
                } label: {
                    Label(controller.isRunning ? "Stop" : "Start", systemImage: controller.isRunning ? "stop.fill" : "play.fill")
                }

                Button {
                    controller.togglePause()
                } label: {
                    Label(controller.isPaused ? "Resume" : "Pause", systemImage: controller.isPaused ? "playpause.fill" : "pause.fill")
                }
                .disabled(!controller.isRunning)

                Button {
                    controller.openTUI()
                } label: {
                    Label("Open TUI", systemImage: "terminal")
                }
            }
            .buttonStyle(.bordered)

            Divider()

            statsLine
        }
        .padding(16)
        .frame(width: 340)
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image(systemName: controller.isRunning ? "record.circle.fill" : "circle")
                .foregroundStyle(controller.isRunning ? .red : .secondary)
            Text("Aki")
                .font(.headline)
            Spacer()
            Text(controller.statusText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var statsLine: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(controller.stats.summary)
                .font(.caption)
                .foregroundStyle(.secondary)
            if controller.stats.droppedFrames > 0 {
                Text("\(controller.stats.droppedFrames) dropped frames")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }
        }
    }

    private var sourceBinding: Binding<CaptureSource> {
        Binding(
            get: { controller.source },
            set: {
                controller.source = $0
                controller.restartIfRunning()
            }
        )
    }

    private var transformBinding: Binding<TransformChoice> {
        Binding(
            get: { controller.transform },
            set: {
                controller.transform = $0
                controller.applyTransformSelection()
            }
        )
    }

    private var outputBinding: Binding<OutputChoice> {
        Binding(
            get: { controller.output },
            set: {
                controller.output = $0
                controller.restartIfRunning()
            }
        )
    }
}

#Preview {
    AkiMenuView(controller: AkiMenuController())
}
