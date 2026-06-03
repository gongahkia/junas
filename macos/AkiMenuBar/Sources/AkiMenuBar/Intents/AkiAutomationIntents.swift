import AppIntents
import Foundation

enum AkiAutomationAction: String, AppEnum {
    case start
    case stop
    case pauseOrResume
    case openTUI

    static var typeDisplayName: LocalizedStringResource { "Aki Action" }
    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Aki Action"

    static var caseDisplayRepresentations: [Self: DisplayRepresentation] {
        [
            .start: "Start",
            .stop: "Stop",
            .pauseOrResume: "Pause or Resume",
            .openTUI: "Open TUI"
        ]
    }
}

struct ControlAkiIntent: AppIntent {
    static let title: LocalizedStringResource = "Control Aki"
    static let description = IntentDescription("Start, stop, pause, resume, or open the Aki TUI.")
    static let openAppWhenRun = true

    @Parameter(title: "Action")
    var action: AkiAutomationAction

    init() {
        self.action = .start
    }

    init(action: AkiAutomationAction) {
        self.action = action
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let message = await MainActor.run {
            AkiAutomationBridge.perform(action)
        }
        return .result(dialog: "\(message)")
    }
}

struct AkiAppShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: ControlAkiIntent(action: .start),
            phrases: [
                "Start \(.applicationName)",
                "Start privacy filter with \(.applicationName)"
            ],
            shortTitle: "Start Aki",
            systemImageName: "play.fill"
        )

        AppShortcut(
            intent: ControlAkiIntent(action: .stop),
            phrases: [
                "Stop \(.applicationName)",
                "Stop privacy filter with \(.applicationName)"
            ],
            shortTitle: "Stop Aki",
            systemImageName: "stop.fill"
        )

        AppShortcut(
            intent: ControlAkiIntent(action: .pauseOrResume),
            phrases: [
                "Pause \(.applicationName)",
                "Resume \(.applicationName)"
            ],
            shortTitle: "Pause or Resume",
            systemImageName: "pause.circle"
        )

        AppShortcut(
            intent: ControlAkiIntent(action: .openTUI),
            phrases: [
                "Open TUI in \(.applicationName)",
                "Open terminal UI in \(.applicationName)"
            ],
            shortTitle: "Open TUI",
            systemImageName: "terminal"
        )
    }
}

@MainActor
enum AkiAutomationBridge {
    static func perform(_ action: AkiAutomationAction) -> String {
        let controller = AkiMenuController.shared
        switch action {
        case .start:
            if controller.isRunning {
                return "Aki is already running."
            }
            controller.start()
            return "Started Aki."
        case .stop:
            if !controller.isRunning {
                return "Aki is already stopped."
            }
            controller.stop()
            return "Stopped Aki."
        case .pauseOrResume:
            if !controller.isRunning {
                controller.start()
                return "Started Aki."
            }
            controller.togglePause()
            return controller.isPaused ? "Resuming Aki." : "Pausing Aki."
        case .openTUI:
            controller.openTUI()
            return "Opened Aki TUI."
        }
    }
}
