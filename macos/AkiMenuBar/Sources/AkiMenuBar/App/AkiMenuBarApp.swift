import SwiftUI

@main
struct AkiMenuBarApp: App {
    @StateObject private var controller = AkiMenuController.shared

    var body: some Scene {
        MenuBarExtra {
            AkiMenuView(controller: controller)
        } label: {
            Label("Aki", systemImage: controller.isRunning ? "hand.raised.fill" : "hand.raised")
        }
        .menuBarExtraStyle(.window)
    }
}
