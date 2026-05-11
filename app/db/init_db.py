import uuid

from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.db.session import Base, engine


def _ensure_message_columns() -> None:
    inspector = inspect(engine)
    if "messages" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("messages")}
    dialect = engine.dialect.name
    client_message_type = "UUID" if dialect == "postgresql" else "CHAR(32)"

    with engine.begin() as connection:
        if "client_message_id" not in columns:
            connection.execute(text(f"ALTER TABLE messages ADD COLUMN client_message_id {client_message_type}"))
        if "message_category" not in columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN message_category VARCHAR(20)"))

        rows = connection.execute(
            text(
                """
                SELECT id, route_mode, client_message_id, message_category
                FROM messages
                """
            )
        ).mappings()

        for row in rows:
            updates: dict[str, str] = {}
            if not row["client_message_id"]:
                updates["client_message_id"] = str(uuid.uuid4()) if dialect == "postgresql" else uuid.uuid4().hex
            if not row["message_category"]:
                updates["message_category"] = "task" if row["route_mode"] == "agent" else "companion"
            if not updates:
                continue

            assignments = ", ".join(f"{column} = :{column}" for column in updates)
            connection.execute(
                text(f"UPDATE messages SET {assignments} WHERE id = :id"),
                {"id": row["id"], **updates},
            )

        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_messages_client_message_id ON messages (client_message_id)")
        )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_message_columns()


if __name__ == "__main__":
    init_db()
    print("Database schema created.")
