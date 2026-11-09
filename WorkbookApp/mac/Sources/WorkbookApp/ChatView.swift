import SwiftUI
import AppKit

struct ChatView: View {
    @Environment(Bridge.self) private var bridge
    @Environment(AppModel.self) private var app
    @FocusState private var inputFocused: Bool

    var body: some View {
        @Bindable var chat = app.chat
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        if chat.messages.isEmpty {
                            emptyState
                        }
                        ForEach(chat.messages) { message in
                            MessageRow(message: message)
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }
                    .padding(20)
                }
                .onChange(of: chat.messages.last?.content) { _, _ in
                    proxy.scrollTo("bottom", anchor: .bottom)
                }
            }

            Divider()
            if let error = chat.error {
                Banner(text: error)
            }
            HStack(alignment: .bottom, spacing: 10) {
                TextField("Message your local model  (Return to send, Option+Return for a new line)",
                          text: $chat.draft, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...8)
                    .focused($inputFocused)
                    .onSubmit(send)
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 10).fill(Color(nsColor: .textBackgroundColor)))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.secondary.opacity(0.2)))

                if chat.isStreaming {
                    Button { chat.stop() } label: {
                        Image(systemName: "stop.circle.fill").font(.system(size: 26))
                    }
                    .buttonStyle(.plain)
                    .help("Stop")
                } else {
                    Button(action: send) {
                        Image(systemName: "arrow.up.circle.fill").font(.system(size: 26))
                    }
                    .buttonStyle(.plain)
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(chat.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !bridge.isReady)
                    .help("Send (Command+Return)")
                }
            }
            .padding(.horizontal, 14)
            .padding(.top, 12)
            HStack {
                Text(chat.stats).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text("Runs on this Mac only").font(.caption).foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .toolbar {
            ToolbarItem {
                Button { app.chat.reset() } label: { Label("New chat", systemImage: "square.and.pencil") }
                    .help("New chat")
            }
        }
        .onAppear { inputFocused = true }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Chat with your local model").font(.title2.bold())
            Text("Nothing you type here leaves your Mac. Try: \"Quiz me on list comprehensions\" or \"Explain eigenvectors like I'm new to it\".")
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 30)
    }

    @MainActor
    private func send() {
        guard bridge.isReady else { return }
        app.chat.send(client: bridge.client)
    }
}

struct MessageRow: View {
    let message: ChatMessage

    var body: some View {
        let isUser = message.role == "user"
        HStack(alignment: .top) {
            if isUser { Spacer(minLength: 80) }
            VStack(alignment: .leading, spacing: 6) {
                Text(isUser ? "You" : "Model")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(message.content.isEmpty ? "…" : message.content)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isUser ? Color.accentColor.opacity(0.15) : Color.secondary.opacity(0.08))
            )
            .contextMenu {
                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(message.content, forType: .string)
                }
            }
            if !isUser { Spacer(minLength: 80) }
        }
    }
}
