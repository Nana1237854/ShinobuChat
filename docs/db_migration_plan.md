# Database Migration Plan

## Current approach (as of B20)

The project uses **SQLAlchemy `Base.metadata.create_all()` + idempotent `ALTER TABLE` helpers** for schema management.

### Startup flow (`app/db/init_db.py`)

1. `CREATE EXTENSION IF NOT EXISTS vector` (PostgreSQL only, when pgvector is enabled)
2. `Base.metadata.create_all(bind=engine)` — creates missing tables from SQLAlchemy models
3. `ensure_todos_columns()` — adds A10 reminder columns via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
4. `ensure_memory_columns()` — adds B12 memory metadata columns
5. `ensure_live2d_interactions_columns()` — adds B15 interaction columns
6. `ensure_character_profiles_columns()` — adds B16 role_type column

### What this means

- **Fresh install**: run the app, tables are created with all columns.
- **Existing DB**: run the app, missing columns are added idempotently (no error on re-run).

### Limitations

- No versioned migration history (no way to know which migrations have been applied)
- No downgrade path
- Column renames, type changes, or constraint changes require manual SQL
- No CI-friendly `alembic upgrade head` step

## How to add new fields (current manual strategy)

If a new model field is added in B11-B19 style, follow this pattern in `init_db.py`:

```python
def ensure_new_feature_columns() -> None:
    if engine.dialect.name != "postgresql":
        return
    statements = [
        "ALTER TABLE target_table ADD COLUMN IF NOT EXISTS new_column TYPE DEFAULT 'value'",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
```

Then call it from `init_db()`.

## B11-B19 fields already covered

| Batch | Table(s) | Columns added |
|---|---|---|
| A10 | `todos` | `last_reminded_at`, `last_reminder_kind`, `reminder_count`, `reminder_enabled`, `snoozed_until`, `dismissed_at` |
| B12 | `conversation_memories` | `category`, `title`, `source`, `pinned`, `tags`, `emotion_label`, `inferred`, `confidence`, `archived`, `archived_reason`, `archived_at`, `embedding_model`, `last_accessed_at`, `updated_at` |
| B15 | `live2d_interactions` | `interaction_type`, `metadata` |
| B16 | `character_profiles` | `role_type` |

All new tables (diaries, mode_sessions, etc.) are created automatically by `Base.metadata.create_all()`.

## Recommended next step: Alembic

Introduce Alembic for versioned migrations:

```bash
pip install alembic
alembic init alembic
```

Then:
1. Point `alembic.ini` at `SC_DATABASE_URL`
2. Set `target_metadata = app.db.session.Base.metadata` in `alembic/env.py`
3. Generate initial migration: `alembic revision --autogenerate -m "initial"`
4. Replace the `init_db()` manual ALTER TABLE calls with proper migration revisions
5. Update startup to run `alembic upgrade head` instead of `Base.metadata.create_all()`

**Risk**: low. The current approach continues to work. Alembic can be introduced incrementally without breaking existing databases.
