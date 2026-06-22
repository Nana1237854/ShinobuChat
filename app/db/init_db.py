from sqlalchemy import text

import app.models  # noqa: F401
from app.core.config import settings
from app.db.session import Base, engine


def ensure_todos_columns() -> None:
    """Add A10 reminder columns to existing todos tables (idempotent)."""
    if engine.dialect.name != "postgresql":
        return

    statements = [
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS last_reminded_at TIMESTAMPTZ",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS last_reminder_kind VARCHAR(50)",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS reminder_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS reminder_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMPTZ",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS dismissed_at TIMESTAMPTZ",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_memory_columns() -> None:
    """Add missing columns to existing conversation_memories tables (idempotent)."""
    if engine.dialect.name != "postgresql":
        return

    statements = [
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS category VARCHAR(50) NOT NULL DEFAULT 'long_term'",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS title VARCHAR(200) NOT NULL DEFAULT ''",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'auto'",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS tags JSON NOT NULL DEFAULT '[]'",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS emotion_label VARCHAR(60)",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS inferred BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS confidence FLOAT NOT NULL DEFAULT 1.0",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS archived_reason VARCHAR(100)",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100)",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ",
        "ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def init_db() -> None:
    if settings.memory_pgvector_enabled and engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    ensure_todos_columns()
    ensure_memory_columns()


if __name__ == "__main__":
    init_db()
    print("Database schema created.")
