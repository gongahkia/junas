// swift-tools-version: 6.0
import PackageDescription

let package = Package(
  name: "JunasMenuBar",
  platforms: [
    .macOS(.v14)
  ],
  products: [
    .executable(name: "JunasMenuBar", targets: ["JunasMenuBar"])
  ],
  targets: [
    .executableTarget(
      name: "JunasMenuBar",
      path: "Sources/JunasMenuBar"
    )
  ]
)
