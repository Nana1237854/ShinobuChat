from sqlalchemy import text

from app import models  # noqa: F401
from app.core.config import settings
from app.db.session import Base, engine


def init_db() -> None:
    if engine.dialect.name == "postgresql" and settings.memory_pgvector_enabled:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database schema created.")
