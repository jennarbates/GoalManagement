// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "WorkbookApp",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "WorkbookApp", path: "Sources/WorkbookApp")
    ]
)
