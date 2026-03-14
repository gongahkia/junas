import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  private let storageChannelName = "kilter_together/catalog_storage"

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    if let controller = window?.rootViewController as? FlutterViewController {
      let channel = FlutterMethodChannel(
        name: storageChannelName,
        binaryMessenger: controller.binaryMessenger
      )
      channel.setMethodCallHandler { [weak self] call, result in
        self?.handleStorageMethodCall(call, result: result)
      }
    }
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }

  private func handleStorageMethodCall(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    guard
      let arguments = call.arguments as? [String: Any],
      let path = arguments["path"] as? String,
      !path.isEmpty
    else {
      result(
        FlutterError(
          code: "invalid_args",
          message: "Path is required.",
          details: nil
        )
      )
      return
    }

    switch call.method {
    case "excludeFromBackup":
      var url = URL(fileURLWithPath: path)
      var resourceValues = URLResourceValues()
      resourceValues.isExcludedFromBackup = true
      do {
        try url.setResourceValues(resourceValues)
        result(nil)
      } catch {
        result(
          FlutterError(
            code: "exclude_failed",
            message: "Unable to exclude catalog path from backup.",
            details: error.localizedDescription
          )
        )
      }
    case "availableBytes":
      do {
        let attributes = try FileManager.default.attributesOfFileSystem(forPath: path)
        let freeSize = attributes[.systemFreeSize] as? NSNumber
        result(freeSize?.int64Value)
      } catch {
        result(
          FlutterError(
            code: "space_check_failed",
            message: "Unable to inspect available device storage.",
            details: error.localizedDescription
          )
        )
      }
    default:
      result(FlutterMethodNotImplemented)
    }
  }
}
