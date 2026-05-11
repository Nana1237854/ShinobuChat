import Foundation
import SQLite3

final class LocalChatCache {
    static let shared = LocalChatCache()

    private var db: OpaquePointer?
    private let queue = DispatchQueue(label: "chat.shinobu.local-cache")

    private init() {
        open()
        migrate()
    }

    deinit {
        sqlite3_close(db)
    }

    func loadMessages(conversationID: UUID?) -> [ChatMessage] {
        queue.sync {
            let sql: String
            if conversationID == nil {
                sql = "SELECT id, conversation_id, role, content, route_mode, created_at FROM messages ORDER BY created_at ASC LIMIT 200;"
            } else {
                sql = "SELECT id, conversation_id, role, content, route_mode, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC;"
            }

            var statement: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else { return [] }
            defer { sqlite3_finalize(statement) }

            if let conversationID {
                bind(statement, index: 1, text: conversationID.uuidString)
            }

            var messages: [ChatMessage] = []
            while sqlite3_step(statement) == SQLITE_ROW {
                guard
                    let id = UUID(uuidString: text(statement, column: 0)),
                    let conversationID = UUID(uuidString: text(statement, column: 1)),
                    let role = MessageRole(rawValue: text(statement, column: 2))
                else {
                    continue
                }
                let routeValue = nullableText(statement, column: 4)
                let date = Date(timeIntervalSince1970: sqlite3_column_double(statement, 5))
                messages.append(
                    ChatMessage(
                        id: id,
                        conversationID: conversationID,
                        role: role,
                        content: text(statement, column: 3),
                        routeMode: routeValue.flatMap(RouteMode.init(rawValue:)),
                        createdAt: date
                    )
                )
            }
            return messages
        }
    }

    func upsert(_ message: ChatMessage) {
        queue.sync {
            let sql = """
            INSERT INTO messages (id, conversation_id, role, content, route_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                conversation_id = excluded.conversation_id,
                role = excluded.role,
                content = excluded.content,
                route_mode = excluded.route_mode,
                created_at = excluded.created_at;
            """
            var statement: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(statement) }
            bind(statement, index: 1, text: message.id.uuidString)
            bind(statement, index: 2, text: message.conversationID.uuidString)
            bind(statement, index: 3, text: message.role.rawValue)
            bind(statement, index: 4, text: message.content)
            bind(statement, index: 5, text: message.routeMode?.rawValue)
            sqlite3_bind_double(statement, 6, message.createdAt.timeIntervalSince1970)
            sqlite3_step(statement)
        }
    }

    func deleteAll() {
        queue.sync {
            sqlite3_exec(db, "DELETE FROM messages; DELETE FROM conversations;", nil, nil, nil)
        }
    }

    private func open() {
        let urls = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)
        let directory = urls[0].appendingPathComponent("ShinobuChat", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let dbURL = directory.appendingPathComponent("shinobuchat.sqlite3")
        sqlite3_open(dbURL.path, &db)
    }

    private func migrate() {
        let sql = """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            route_mode TEXT,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
        ON messages(conversation_id, created_at);
        """
        sqlite3_exec(db, sql, nil, nil, nil)
    }

    private func bind(_ statement: OpaquePointer?, index: Int32, text: String?) {
        guard let text else {
            sqlite3_bind_null(statement, index)
            return
        }
        sqlite3_bind_text(statement, index, text, -1, SQLITE_TRANSIENT)
    }

    private func text(_ statement: OpaquePointer?, column: Int32) -> String {
        guard let raw = sqlite3_column_text(statement, column) else { return "" }
        return String(cString: raw)
    }

    private func nullableText(_ statement: OpaquePointer?, column: Int32) -> String? {
        guard sqlite3_column_type(statement, column) != SQLITE_NULL else { return nil }
        return text(statement, column: column)
    }
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
