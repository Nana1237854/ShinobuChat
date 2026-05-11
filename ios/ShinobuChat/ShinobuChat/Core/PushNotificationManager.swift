import Foundation
import SwiftUI
import UIKit
import UserNotifications

@MainActor
final class PushNotificationManager: ObservableObject {
    static let shared = PushNotificationManager()

    @Published private(set) var deviceToken: String?
    @Published private(set) var lastNotificationTitle: String?
    @Published private(set) var isRegisteredWithBackend = false
    @Published var lastRegistrationError: String?

    private weak var session: AppSession?

    private init() {}

    func attach(session: AppSession) {
        self.session = session
    }

    func requestAuthorizationAndRegister() async {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound])
            guard granted else {
                lastRegistrationError = "用户未授权推送通知"
                return
            }
            UIApplication.shared.registerForRemoteNotifications()
        } catch {
            lastRegistrationError = error.localizedDescription
        }
    }

    func didReceiveDeviceToken(_ token: String) async {
        deviceToken = token
        await uploadPendingTokenIfPossible()
    }

    func uploadPendingTokenIfPossible() async {
        guard
            let token = deviceToken,
            let session,
            let userID = session.userID,
            let client = session.client
        else {
            return
        }

        do {
            _ = try await client.registerAPNs(
                userID: userID,
                deviceToken: token,
                deviceName: session.deviceName
            )
            isRegisteredWithBackend = true
            lastRegistrationError = nil
        } catch {
            isRegisteredWithBackend = false
            lastRegistrationError = error.localizedDescription
        }
    }

    func record(notification: UNNotification) async {
        let content = notification.request.content
        lastNotificationTitle = content.title.isEmpty ? content.body : content.title
    }
}
