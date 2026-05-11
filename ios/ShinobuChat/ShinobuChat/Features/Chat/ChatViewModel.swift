import Foundation

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var draft = ""
    @Published var routeMode: RouteMode = .auto
    @Published var conversationID: UUID?
    @Published var isStreaming = false
    @Published var errorMessage: String?

    private let cache = LocalChatCache.shared
    private var pendingAssistantID: UUID?

    func restoreCache() {
        messages = cache.loadMessages(conversationID: conversationID)
        conversationID = messages.last?.conversationID ?? conversationID
    }

    func send(session: AppSession) async {
        let content = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return }
        guard let userID = session.userID, let client = session.client else {
            errorMessage = "请先登录"
            return
        }

        draft = ""
        errorMessage = nil
        isStreaming = true
        pendingAssistantID = nil

        do {
            try await client.sendMessage(
                userID: userID,
                conversationID: conversationID,
                content: content,
                routeMode: routeMode,
                onConversation: { [weak self] payload in
                    guard let self else { return }
                    self.conversationID = payload.conversationID
                    self.append(payload.userMessage)
                    let pending = ChatMessage(
                        conversationID: payload.conversationID,
                        role: .assistant,
                        content: "",
                        routeMode: payload.routeMode
                    )
                    self.pendingAssistantID = pending.id
                    self.messages.append(pending)
                },
                onChunk: { [weak self] delta in
                    guard let self, let pendingAssistantID = self.pendingAssistantID else { return }
                    if let index = self.messages.firstIndex(where: { $0.id == pendingAssistantID }) {
                        self.messages[index].content += delta
                    }
                },
                onDone: { [weak self] payload in
                    guard let self else { return }
                    self.conversationID = payload.conversationID
                    if let pendingAssistantID = self.pendingAssistantID,
                       let index = self.messages.firstIndex(where: { $0.id == pendingAssistantID }) {
                        self.messages.remove(at: index)
                    }
                    self.pendingAssistantID = nil
                    self.append(payload.assistantMessage)
                }
            )
        } catch {
            errorMessage = error.localizedDescription
        }

        isStreaming = false
    }

    func clearLocalCache() {
        cache.deleteAll()
        messages = []
        conversationID = nil
        pendingAssistantID = nil
    }

    private func append(_ message: ChatMessage) {
        guard !messages.contains(where: { $0.id == message.id }) else { return }
        messages.append(message)
        cache.upsert(message)
    }
}
