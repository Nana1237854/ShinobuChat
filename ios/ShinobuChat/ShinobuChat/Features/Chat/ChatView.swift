import SwiftUI

struct ChatView: View {
    @EnvironmentObject private var session: AppSession
    @StateObject private var viewModel = ChatViewModel()
    @ObservedObject private var push = PushNotificationManager.shared

    var body: some View {
        NavigationStack {
            ZStack {
                ShinobuBackground()
                    .ignoresSafeArea()

                if session.isAuthenticated {
                    chatSurface
                } else {
                    SignInView()
                        .environmentObject(session)
                }
            }
            .navigationTitle("Shinobu")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if session.isAuthenticated {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("清空") { viewModel.clearLocalCache() }
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("退出") { session.signOut() }
                    }
                }
            }
            .task { viewModel.restoreCache() }
        }
    }

    private var chatSurface: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        if viewModel.messages.isEmpty {
                            MessageBubble(
                                text: "准备好了。发送第一条消息时会自动创建 conversation_id，之后继续发送就会走多轮上下文。",
                                role: .assistant
                            )
                            .id("empty")
                        }

                        ForEach(viewModel.messages) { message in
                            MessageBubble(text: message.content, role: message.role)
                                .id(message.id)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 18)
                }
                .onChange(of: viewModel.messages) { _, messages in
                    guard let last = messages.last else { return }
                    withAnimation(.snappy) {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }

            VStack(spacing: 10) {
                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                PushStatusView(push: push)

                Picker("Route", selection: $viewModel.routeMode) {
                    ForEach(RouteMode.allCases) { mode in
                        Text(mode.title).tag(mode)
                    }
                }
                .pickerStyle(.segmented)

                HStack(alignment: .bottom, spacing: 10) {
                    TextField("和 Shinobu 聊天，或者给她安排一个任务", text: $viewModel.draft, axis: .vertical)
                        .lineLimit(1...5)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 11)
                        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18))
                        .overlay(
                            RoundedRectangle(cornerRadius: 18)
                                .stroke(.white.opacity(0.6), lineWidth: 1)
                        )

                    Button {
                        Task { await viewModel.send(session: session) }
                    } label: {
                        Image(systemName: viewModel.isStreaming ? "hourglass" : "paperplane.fill")
                            .font(.system(size: 17, weight: .semibold))
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.borderedProminent)
                    .clipShape(Circle())
                    .disabled(viewModel.isStreaming || viewModel.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .padding(14)
            .background(.ultraThinMaterial)
        }
    }
}

private struct SignInView: View {
    @EnvironmentObject private var session: AppSession
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("ShinobuChat")
                .font(.largeTitle.bold())
                .foregroundStyle(Color(red: 0.18, green: 0.15, blue: 0.13))

            TextField("API Base URL", text: $session.apiBaseURLString)
                .textInputAutocapitalization(.never)
                .keyboardType(.URL)
                .textFieldStyle(.roundedBorder)

            TextField("Email", text: $email)
                .textInputAutocapitalization(.never)
                .keyboardType(.emailAddress)
                .textFieldStyle(.roundedBorder)

            SecureField("Password", text: $password)
                .textFieldStyle(.roundedBorder)

            if let error = session.authError {
                Text(error)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            Button {
                Task { await session.signIn(email: email, password: password) }
            } label: {
                HStack {
                    if session.isSigningIn {
                        ProgressView()
                    }
                    Text(session.isSigningIn ? "正在注册设备" : "登录并注册设备")
                        .frame(maxWidth: .infinity)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(session.isSigningIn || email.isEmpty || password.isEmpty)
        }
        .padding(22)
        .background(.white.opacity(0.78), in: RoundedRectangle(cornerRadius: 24))
        .padding(20)
    }
}

private struct PushStatusView: View {
    @ObservedObject var push: PushNotificationManager

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: push.isRegisteredWithBackend ? "bell.badge.fill" : "bell")
            Text(push.isRegisteredWithBackend ? "APNs 已上报" : "等待 APNs token")
            if let title = push.lastNotificationTitle {
                Text(title)
                    .lineLimit(1)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .font(.caption)
        .foregroundStyle(Color(red: 0.15, green: 0.38, blue: 0.31))
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(Color(red: 0.86, green: 0.94, blue: 0.9).opacity(0.88), in: Capsule())
    }
}

private struct MessageBubble: View {
    let text: String
    let role: MessageRole

    private var isUser: Bool { role == .user }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 42) }
            Text(text.isEmpty ? " " : text)
                .font(.body)
                .foregroundStyle(isUser ? Color(red: 1, green: 0.97, blue: 0.94) : Color(red: 0.18, green: 0.15, blue: 0.13))
                .padding(.horizontal, 15)
                .padding(.vertical, 11)
                .background {
                    if isUser {
                        LinearGradient(
                            colors: [Color(red: 0.76, green: 0.35, blue: 0.22), Color(red: 0.72, green: 0.29, blue: 0.16)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    } else {
                        Color(red: 1, green: 0.98, blue: 0.96).opacity(0.9)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 19, style: .continuous))
                .shadow(color: .black.opacity(0.08), radius: 12, y: 6)
            if !isUser { Spacer(minLength: 42) }
        }
    }
}

private struct ShinobuBackground: View {
    var body: some View {
        LinearGradient(
            colors: [
                Color(red: 0.91, green: 0.82, blue: 0.72),
                Color(red: 0.97, green: 0.93, blue: 0.89),
                Color(red: 0.78, green: 0.84, blue: 0.87)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .overlay(.white.opacity(0.22))
    }
}

#Preview {
    ChatView()
        .environmentObject(AppSession())
}
