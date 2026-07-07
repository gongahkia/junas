import AppKit
import Darwin
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
  func applicationDidFinishLaunching(_ notification: Notification) {
    if RuntimeQA.shouldRun {
      let passed = RuntimeQA.run()
      fflush(stdout)
      fflush(stderr)
      Darwin.exit(passed ? EXIT_SUCCESS : EXIT_FAILURE)
    }
    NSApp.setActivationPolicy(.regular)
    NSApp.activate(ignoringOtherApps: true)
  }
}

@main
struct JunasMenuBarApp: App {
  @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
  @StateObject private var store = PipelineStore()

  var body: some Scene {
    WindowGroup("Junas", id: "main") {
      StatusWindowView(store: store)
    }

    MenuBarExtra {
      MenuBarContentView(store: store)
    } label: {
      Label("Junas", systemImage: store.state.systemImage)
    }
    .menuBarExtraStyle(.window)
    .commands {
      CommandMenu("Pipeline") {
        Button("Start Redaction") { store.start() }
          .keyboardShortcut("r", modifiers: [.command])
          .disabled(!store.canStart)
        Button("Pause Redaction") { store.pause() }
          .keyboardShortcut("p", modifiers: [.command])
          .disabled(!store.canPause)
        Button("Stop Redaction") { store.stop() }
          .keyboardShortcut(".", modifiers: [.command])
          .disabled(!store.canStop)
        Divider()
        Button("Open TUI") { store.openTUI() }
      }
    }
  }
}
