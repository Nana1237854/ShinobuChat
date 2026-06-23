from sqlalchemy import text

import app.models  # noqa: F401
from app.core.config import settings
from app.db.migrations import run_migrations
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


def ensure_live2d_interactions_columns() -> None:
    """Add B15 columns to existing live2d_interactions tables (idempotent)."""
    if engine.dialect.name != "postgresql":
        return

    statements = [
        "ALTER TABLE live2d_interactions ADD COLUMN IF NOT EXISTS interaction_type VARCHAR(20) NOT NULL DEFAULT 'click'",
        "ALTER TABLE live2d_interactions ADD COLUMN IF NOT EXISTS metadata JSON",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_character_profiles_columns() -> None:
    """Add B16 role_type column to existing character_profiles tables (idempotent)."""
    if engine.dialect.name != "postgresql":
        return

    statements = [
        "ALTER TABLE character_profiles ADD COLUMN IF NOT EXISTS role_type VARCHAR(20) NOT NULL DEFAULT 'auxiliary'",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_trusted_download_sources_columns() -> None:
    """Add F15 columns to existing trusted_download_sources tables (idempotent)."""
    if engine.dialect.name != "postgresql":
        return

    statements = [
        "ALTER TABLE trusted_download_sources ADD COLUMN IF NOT EXISTS product_key VARCHAR(128)",
        "ALTER TABLE trusted_download_sources ADD COLUMN IF NOT EXISTS trust_level VARCHAR(32) NOT NULL DEFAULT 'trusted'",
        "ALTER TABLE trusted_download_sources ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) NOT NULL DEFAULT 'builtin'",
        "ALTER TABLE trusted_download_sources ADD COLUMN IF NOT EXISTS note TEXT",
        "ALTER TABLE trusted_download_sources ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
        "ALTER TABLE trusted_download_sources ALTER COLUMN user_id DROP NOT NULL",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_phase2_columns() -> None:
    """Add Phase 2 columns to existing tables, and idempotent constraints for new tables."""
    if engine.dialect.name != "postgresql":
        return

    statements = [
        "ALTER TABLE action_audit_logs ADD COLUMN IF NOT EXISTS verified BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE action_audit_logs ADD COLUMN IF NOT EXISTS requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE",
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
    run_migrations()
    ensure_todos_columns()
    ensure_memory_columns()
    ensure_live2d_interactions_columns()
    ensure_character_profiles_columns()
    ensure_trusted_download_sources_columns()
    ensure_phase2_columns()


if __name__ == "__main__":
    init_db()
    print("Database schema created.")
