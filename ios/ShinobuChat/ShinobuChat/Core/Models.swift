import Foundation

enum RouteMode: String, Codable, CaseIterable, Identifiable {
    case auto
    case chat
    case agent

    var id: String { rawValue }

    var title: String {
        switch self {
        case .auto: "自动"
        case .chat: "纯聊天"
        case .agent: "Agent"
        }
    }
}

enum MessageRole: String, Codable {
    case user
    case assistant
    case system
}

struct ChatMessage: Identifiable, Codable, Equatable {
    let id: UUID
    var conversationID: UUID
    var role: MessageRole
    var content: String
    var routeMode: RouteMode?
    var createdAt: Date

    init(
        id: UUID = UUID(),
        conversationID: UUID,
        role: MessageRole,
        content: String,
        routeMode: RouteMode? = nil,
        createdAt: Date = Date()
    ) {
        self.id = id
        self.conversationID = conversationID
        self.role = role
        self.content = content
        self.routeMode = routeMode
        self.createdAt = createdAt
    }

    enum CodingKeys: String, CodingKey {
        case id
        case conversationID = "conversation_id"
        case role
        case content
        case routeMode = "route_mode"
        case createdAt = "created_at"
    }
}

struct Conversation: Identifiable, Codable, Equatable {
    let id: UUID
    var userID: UUID
    var title: String
    var summary: String?
    var createdAt: Date
    var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case userID = "user_id"
        case title
        case summary
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct DeviceAuthorizeResponse: Decodable {
    let deviceCode: String
    let userCode: String
    let verificationURI: String
    let expiresIn: Int
    let interval: Int

    enum CodingKeys: String, CodingKey {
        case deviceCode = "device_code"
        case userCode = "user_code"
        case verificationURI = "verification_uri"
        case expiresIn = "expires_in"
        case interval
    }
}

struct DeviceTokenResponse: Decodable {
    let accessToken: String
    let tokenType: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct ApnsRegistrationResponse: Decodable {
    let userID: UUID
    let deviceName: String
    let registeredAt: Date
    let sandbox: Bool

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case deviceName = "device_name"
        case registeredAt = "registered_at"
        case sandbox
    }
}

struct StreamConversationPayload: Decodable {
    let conversationID: UUID
    let routeMode: RouteMode
    let title: String
    let userMessage: ChatMessage

    enum CodingKeys: String, CodingKey {
        case conversationID = "conversation_id"
        case routeMode = "route_mode"
        case title
        case userMessage = "user_message"
    }
}

struct StreamChunkPayload: Decodable {
    let delta: String
}

struct StreamDonePayload: Decodable {
    let conversationID: UUID
    let assistantMessage: ChatMessage

    enum CodingKeys: String, CodingKey {
        case conversationID = "conversation_id"
        case assistantMessage = "assistant_message"
    }
}
