import SwiftUI
import AppKit

struct ContentView: View {
    @Environment(AppModel.self) private var app
    @Environment(Bridge.self) private var bridge

    var body: some View {
        @Bindable var app = app
        NavigationSplitView {
            List(selection: $app.tab) {
                ForEach(AppTab.allCases) { tab in
                    Label(tab.title, systemImage: tab.icon).tag(tab)
                }
            }
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    StatusPill()
                    if let id = bridge.health?.modelId, !id.isEmpty {
                        Text(id.components(separatedBy: "/").last ?? id)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .navigationSplitViewColumnWidth(min: 190, ideal: 210)
        } detail: {
            VStack(spacing: 0) {
                if let problem = bridge.problem {
                    Banner(text: problem, color: .red)
                }
                Group {
                    switch app.tab ?? .today {
                    case .today: TodayView()
                    case .chat: ChatView()
                    case .workbook: WorkbookView()
                    case .settings: SettingsView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }
}

// MARK: Shared small views

struct StatusPill: View {
    @Environment(Bridge.self) private var bridge

    var body: some View {
        let s = status
        HStack(spacing: 6) {
            Circle().fill(s.1).frame(width: 8, height: 8)
            Text(s.0).font(.caption).lineLimit(1)
        }
    }

    private var status: (String, Color) {
        if case .failed = bridge.runState { return ("Bridge stopped", .red) }
        if !bridge.isRunning { return ("Bridge stopped", .gray) }
        guard let h = bridge.health else { return ("Starting…", .yellow) }
        switch h.modelStatus {
        case "ready":
            if !h.busy.isEmpty { return (h.busy + "…", .orange) }
            return (h.offlineGuard.allowHosts.isEmpty ? "Ready, offline" : "Ready, weather allowed", .green)
        case "loading": return ("Loading model…", .yellow)
        case "error": return ("Model error", .red)
        default: return ("Model not loaded", .gray)
        }
    }
}

struct Banner: View {
    let text: String
    var color: Color = .orange

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
            Text(text).textSelection(.enabled)
            Spacer(minLength: 0)
        }
        .font(.callout)
        .padding(10)
        .foregroundStyle(color)
        .background(color.opacity(0.1))
    }
}

/// Wraps children onto new lines when they run out of width.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0, widest: CGFloat = 0
        for view in subviews {
            let size = fitted(view, maxWidth)
            if x > 0 && x + size.width > maxWidth {
                y += rowHeight + spacing
                x = 0
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: proposal.width ?? widest, height: y + rowHeight)
    }

    /// Natural size, but never wider than the row (long items wrap their text).
    private func fitted(_ view: LayoutSubview, _ maxWidth: CGFloat) -> CGSize {
        let natural = view.sizeThatFits(.unspecified)
        guard maxWidth.isFinite, natural.width > maxWidth else { return natural }
        return view.sizeThatFits(ProposedViewSize(width: maxWidth, height: nil))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for view in subviews {
            let size = fitted(view, bounds.width)
            if x > bounds.minX && x + size.width > bounds.maxX {
                y += rowHeight + spacing
                x = bounds.minX
                rowHeight = 0
            }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

func openFile(_ path: String) {
    guard !path.isEmpty else { return }
    NSWorkspace.shared.open(URL(fileURLWithPath: path))
}
