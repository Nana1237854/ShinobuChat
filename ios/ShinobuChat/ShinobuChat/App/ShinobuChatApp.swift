import SwiftUI

@main
struct ShinobuChatApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var session = AppSession()

    var body: some Scene {
        WindowGroup {
            ChatView()
                .environmentObject(session)
                .task {
                    PushNotificationManager.shared.attach(session: session)
                    await session.restore()
                }
        }
    }
}
