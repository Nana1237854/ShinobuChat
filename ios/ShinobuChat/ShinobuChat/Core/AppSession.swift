import Foundation
import UIKit

@MainActor
final class AppSession: ObservableObject {
    @Published var apiBaseURLString = UserDefaults.standard.string(forKey: Keys.apiBaseURL) ?? "http://127.0.0.1:8000/api/v1"
    @Published private(set) var accessToken: String?
    @Published private(set) var userID: UUID?
    @Published private(set) var deviceName = UIDevice.current.name
    @Published var authError: String?
    @Published var isSigningIn = false

    private enum Keys {
        static let apiBaseURL = "apiBaseURL"
        static let accessToken = "accessToken"
        static let userID = "userID"
    }

    var isAuthenticated: Bool {
        accessToken != nil && userID != nil
    }

    var client: APIClient? {
        guard let url = URL(string: apiBaseURLString) else { return nil }
        return APIClient(baseURL: url, accessToken: accessToken)
    }

    func restore() async {
        accessToken = UserDefaults.standard.string(forKey: Keys.accessToken)
        if let value = UserDefaults.standard.string(forKey: Keys.userID) {
            userID = UUID(uuidString: value)
        }
        await PushNotificationManager.shared.uploadPendingTokenIfPossible()
    }

    func signIn(email: String, password: String) async {
        authError = nil
        isSigningIn = true
        defer { isSigningIn = false }

        guard let url = URL(string: apiBaseURLString) else {
            authError = APIError.invalidBaseURL.localizedDescription
            return
        }

        do {
            UserDefaults.standard.set(apiBaseURLString, forKey: Keys.apiBaseURL)
            let anonymousClient = APIClient(baseURL: url)
            let authorization = try await anonymousClient.authorizeDevice(
                email: email,
                password: password,
                deviceName: deviceName
            )
            let token = try await anonymousClient.exchangeDeviceToken(deviceCode: authorization.deviceCode)
            let parsedUserID = try Self.userID(fromJWT: token.accessToken)

            accessToken = token.accessToken
            userID = parsedUserID
            UserDefaults.standard.set(token.accessToken, forKey: Keys.accessToken)
            UserDefaults.standard.set(parsedUserID.uuidString, forKey: Keys.userID)

            PushNotificationManager.shared.attach(session: self)
            await PushNotificationManager.shared.requestAuthorizationAndRegister()
        } catch {
            authError = error.localizedDescription
        }
    }

    func signOut() {
        accessToken = nil
        userID = nil
        authError = nil
        UserDefaults.standard.removeObject(forKey: Keys.accessToken)
        UserDefaults.standard.removeObject(forKey: Keys.userID)
    }

    private static func userID(fromJWT token: String) throws -> UUID {
        let segments = token.split(separator: ".")
        guard segments.count >= 2 else { throw APIError.missingUserID }
        var payload = String(segments[1])
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        while payload.count % 4 != 0 {
            payload += "="
        }
        guard
            let data = Data(base64Encoded: payload),
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let sub = json["sub"] as? String,
            let userID = UUID(uuidString: sub)
        else {
            throw APIError.missingUserID
        }
        return userID
    }
}
