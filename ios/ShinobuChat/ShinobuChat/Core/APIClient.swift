import Foundation

enum APIError: LocalizedError {
    case invalidBaseURL
    case invalidResponse
    case server(Int, String)
    case missingUserID

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            "API 地址无效"
        case .invalidResponse:
            "服务端响应格式无效"
        case let .server(status, body):
            "请求失败 \(status): \(body)"
        case .missingUserID:
            "无法从登录令牌读取 user_id"
        }
    }
}

struct APIClient {
    var baseURL: URL
    var accessToken: String?

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            if let date = ISO8601DateFormatter.backend.date(from: value) {
                return date
            }
            if let date = ISO8601DateFormatter.backendWithoutFraction.date(from: value) {
                return date
            }
            if let date = DateFormatter.backendWithMicroseconds.date(from: value) {
                return date
            }
            if let date = DateFormatter.backendWithoutMicroseconds.date(from: value) {
                return date
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid ISO8601 date")
        }
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    func authorizeDevice(email: String, password: String, deviceName: String) async throws -> DeviceAuthorizeResponse {
        try await post(
            path: "auth/device/authorize",
            body: [
                "email": email,
                "password": password,
                "device_name": deviceName,
                "device_type": "ios"
            ]
        )
    }

    func exchangeDeviceToken(deviceCode: String) async throws -> DeviceTokenResponse {
        try await post(path: "auth/device/token", body: ["device_code": deviceCode])
    }

    func registerAPNs(userID: UUID, deviceToken: String, deviceName: String) async throws -> ApnsRegistrationResponse {
        try await post(
            path: "sync/apns/register",
            body: [
                "user_id": userID.uuidString,
                "device_token": deviceToken,
                "device_name": deviceName
            ]
        )
    }

    func fetchMessages(conversationID: UUID, userID: UUID) async throws -> [ChatMessage] {
        let request = try makeRequest(path: "conversations/\(conversationID.uuidString)/messages?user_id=\(userID.uuidString)")
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode([ChatMessage].self, from: data)
    }

    func sendMessage(
        userID: UUID,
        conversationID: UUID?,
        content: String,
        routeMode: RouteMode,
        onConversation: @escaping @MainActor (StreamConversationPayload) async -> Void,
        onChunk: @escaping @MainActor (String) async -> Void,
        onDone: @escaping @MainActor (StreamDonePayload) async -> Void
    ) async throws {
        var payload: [String: String] = [
            "user_id": userID.uuidString,
            "content": content,
            "route_mode": routeMode.rawValue
        ]
        if let conversationID {
            payload["conversation_id"] = conversationID.uuidString
        }

        var request = try makeRequest(path: "messages")
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(payload)

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        try validate(response: response, data: Data())

        var eventName = "message"
        for try await line in bytes.lines {
            if line.hasPrefix("event:") {
                eventName = line.dropFirst("event:".count).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                let json = line.dropFirst("data:".count).trimmingCharacters(in: .whitespaces)
                guard let data = json.data(using: .utf8) else { continue }
                switch eventName {
                case "conversation":
                    await onConversation(try decoder.decode(StreamConversationPayload.self, from: data))
                case "chunk":
                    let payload = try decoder.decode(StreamChunkPayload.self, from: data)
                    await onChunk(payload.delta)
                case "done":
                    await onDone(try decoder.decode(StreamDonePayload.self, from: data))
                default:
                    break
                }
            }
        }
    }

    private func post<Response: Decodable, Body: Encodable>(path: String, body: Body) async throws -> Response {
        var request = try makeRequest(path: path)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(Response.self, from: data)
    }

    private func makeRequest(path: String) throws -> URLRequest {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw APIError.invalidBaseURL
        }
        let basePath = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let separator = basePath.isEmpty ? "" : "/"
        let fullPath = "\(basePath)\(separator)\(path)"
        let pieces = fullPath.split(separator: "?", maxSplits: 1).map(String.init)
        components.path = "/" + pieces[0]
        if pieces.count > 1 {
            components.query = pieces[1]
        }
        guard let url = components.url else { throw APIError.invalidBaseURL }
        var request = URLRequest(url: url)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let accessToken {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.server(http.statusCode, body)
        }
    }
}

extension ISO8601DateFormatter {
    static let backend: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    static let backendWithoutFraction: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()
}

extension DateFormatter {
    static let backendWithMicroseconds: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .iso8601)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        return formatter
    }()

    static let backendWithoutMicroseconds: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .iso8601)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return formatter
    }()
}
