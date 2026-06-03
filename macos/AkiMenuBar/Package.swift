// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "AkiMenuBar",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "AkiMenuBar", targets: ["AkiMenuBar"])
    ],
    targets: [
        .executableTarget(
            name: "AkiMenuBar"
        )
    ]
)
