"""Lightweight versioned migration system.

Does NOT introduce Alembic. Uses a plain ``schema_migrations`` table to track
applied versions. Supports PostgreSQL and SQLite via dialect detection.
"""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

_MIGRATIONS: list[tuple[str, str, Callable[[], None]]] = []


def ensure_schema_migrations_table() -> None:
    """Create the schema_migrations tracking table if it does not exist."""
    if engine.dialect.name == "postgresql":
        ddl = (
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "    version VARCHAR(64) PRIMARY KEY,"
            "    name VARCHAR(255) NOT NULL,"
            "    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            ")"
        )
    else:
        ddl = (
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "    version VARCHAR(64) PRIMARY KEY,"
            "    name VARCHAR(255) NOT NULL,"
            "    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    with engine.begin() as connection:
        connection.execute(text(ddl))


def has_migration(version: str) -> bool:
    """Return True if *version* has already been applied."""
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :ver"),
            {"ver": version},
        ).first()
        return row is not None


def mark_migration(version: str, name: str) -> None:
    """Record that *version* was applied."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO schema_migrations (version, name) "
                "VALUES (:ver, :nam)"
            ),
            {"ver": version, "nam": name},
        )


def apply_once(version: str, name: str, fn: Callable[[], None]) -> None:
    """Run *fn* exactly once, guarded by *version*."""
    if has_migration(version):
        logger.debug("Migration %s (%s) already applied — skip.", version, name)
        return
    logger.info("Applying migration %s (%s) ...", version, name)
    fn()
    mark_migration(version, name)


def _register(version: str, name: str, fn: Callable[[], None]) -> None:
    _MIGRATIONS.append((version, name, fn))


# ---------------------------------------------------------------------------
# Migration definitions
# ---------------------------------------------------------------------------


def migration_20260624_001() -> None:
    """Create F11-F15 tables and indexes that Base.metadata.create_all
    does not cover, plus legacy index fixes."""

    is_pg = engine.dialect.name == "postgresql"

    # user_local_apps indexes
    statements: list[str] = []
    if is_pg:
        statements += [
            "CREATE INDEX IF NOT EXISTS ix_user_local_apps_user_id ON user_local_apps (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_local_apps_app_key ON user_local_apps (app_key)",
            "CREATE INDEX IF NOT EXISTS ix_user_local_apps_intent_type ON user_local_apps (intent_type)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_local_apps_user_app_key ON user_local_apps (user_id, app_key)",
        ]
    else:
        statements += [
            "CREATE INDEX IF NOT EXISTS ix_user_local_apps_user_id ON user_local_apps (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_local_apps_app_key ON user_local_apps (app_key)",
            "CREATE INDEX IF NOT EXISTS ix_user_local_apps_intent_type ON user_local_apps (intent_type)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_local_apps_user_app_key ON user_local_apps (user_id, app_key)",
        ]

    # local_action_logs indexes
    statements += [
        _index_ddl("ix_local_action_logs_user_id", "local_action_logs", "user_id", is_pg),
        _index_ddl("ix_local_action_logs_conversation_id", "local_action_logs", "conversation_id", is_pg),
        _index_ddl("ix_local_action_logs_status", "local_action_logs", "status", is_pg),
        _index_ddl("ix_local_action_logs_action_type", "local_action_logs", "action_type", is_pg),
    ]

    # pending_actions indexes
    statements += [
        _index_ddl("ix_pending_actions_user_id", "pending_actions", "user_id", is_pg),
        _index_ddl("ix_pending_actions_conversation_id", "pending_actions", "conversation_id", is_pg),
        _index_ddl("ix_pending_actions_status", "pending_actions", "status", is_pg),
    ]

    # browser_action_logs indexes (F15 skeleton)
    statements += [
        _index_ddl("ix_browser_action_logs_user_id", "browser_action_logs", "user_id", is_pg),
        _index_ddl("ix_browser_action_logs_status", "browser_action_logs", "status", is_pg),
    ]

    # trusted_download_sources indexes (F15 skeleton)
    statements += [
        _index_ddl("ix_trusted_download_sources_user_id", "trusted_download_sources", "user_id", is_pg),
        _index_ddl("ix_trusted_download_sources_domain", "trusted_download_sources", "domain", is_pg),
    ]

    with engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))


def _index_ddl(index_name: str, table: str, column: str, is_pg: bool) -> str:
    if is_pg:
        return f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"
    return f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"


_register("20260624001", "F11-F15: local app tables, indexes, and constraints", migration_20260624_001)


def migration_20260624_002() -> None:
    """Fix: ensure (user_id, app_key) unique constraint on PostgreSQL."""
    is_pg = engine.dialect.name == "postgresql"
    if not is_pg:
        return
    with engine.begin() as connection:
        connection.execute(
            text("DROP INDEX IF EXISTS ix_user_local_apps_user_app_key")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_user_local_apps_user_app_key ON user_local_apps (user_id, app_key)"
            )
        )


_register("20260624002", "Fix: unique constraint on (user_id, app_key) for PostgreSQL", migration_20260624_002)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_migrations() -> None:
    """Apply all pending migrations.

    Must be called AFTER ``Base.metadata.create_all()`` so that tables exist
    before we try to create indexes on them.
    """
    ensure_schema_migrations_table()
    for version, name, fn in _MIGRATIONS:
        apply_once(version, name, fn)
