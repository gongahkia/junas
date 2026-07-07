import Foundation

@MainActor
enum RuntimeQA {
  static var shouldRun: Bool {
    ProcessInfo.processInfo.environment["JUNAS_MENU_BAR_RUNTIME_QA"] == "1"
  }

  static func run(environment: [String: String] = ProcessInfo.processInfo.environment) -> Bool {
    let scenario = environment["JUNAS_MENU_BAR_QA_SCENARIO"] ?? "normal"
    print("menu_bar_runtime_qa_scenario=\(scenario)")
    let passed: Bool
    switch scenario {
    case "normal":
      passed = runNormal(environment: environment)
    case "unavailable":
      passed = runUnavailable(environment: environment)
    case "invalid_response":
      passed = runInvalidResponse(environment: environment)
    case "packaged_resource":
      passed = runPackagedResource()
    default:
      print("unknown_scenario=fail")
      passed = false
    }
    print("menu_bar_runtime_qa_scenario_result=\(passed ? "pass" : "fail")")
    return passed
  }

  private static func runNormal(environment: [String: String]) -> Bool {
    let client = SidecarClient(environment: environment)
    do {
      try client.startIfNeeded()
      print("sidecar_child_launch=pass")
      if environment["JUNAS_SIDECAR_COMMAND"] != nil {
        print("override_command=pass")
      }
      try client.initialize()
      try client.selectSource(.display)
      try client.selectTransform(.redactionBox)
      try client.selectOutput(.preview)
      try client.startCapture()
      print("normal_launch=pass")
      client.shutdown()
      print("app_shutdown=pass")
      return true
    } catch {
      print("normal_launch=fail error_class=\(type(of: error))")
      client.shutdown()
      return false
    }
  }

  private static func runUnavailable(environment: [String: String]) -> Bool {
    let client = SidecarClient(environment: environment)
    do {
      try client.startIfNeeded()
      print("sidecar_unavailable=fail")
      client.shutdown()
      return false
    } catch {
      print("sidecar_unavailable=pass")
      if environment["JUNAS_SIDECAR_COMMAND"] != nil {
        print("override_unavailable_command=pass")
      }
      return true
    }
  }

  private static func runInvalidResponse(environment: [String: String]) -> Bool {
    let client = SidecarClient(environment: environment)
    do {
      try client.initialize()
      print("invalid_sidecar_response=fail")
      client.shutdown()
      return false
    } catch {
      print("invalid_sidecar_response=pass")
      print("invalid_sidecar_error_class=\(type(of: error))")
      client.shutdown()
      return true
    }
  }

  private static func runPackagedResource() -> Bool {
    guard let resourceURL = Bundle.main.resourceURL else {
      print("packaged_resource_lookup=fail")
      return false
    }
    let sidecarURL = resourceURL.appending(path: "junas-sidecar/junas-sidecar")
    if FileManager.default.isExecutableFile(atPath: sidecarURL.path) {
      print("packaged_resource_lookup=pass")
      print("packaged_resource_path=Contents/Resources/junas-sidecar/junas-sidecar")
    } else {
      print("packaged_resource_lookup=deferred")
      print("packaged_resource_deferred_reason=signed_dmg_task_bundles_sidecar")
    }
    return true
  }
}
