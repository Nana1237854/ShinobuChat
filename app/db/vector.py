from __future__ import annotations

from typing import Any

from sqlalchemy.types import UserDefinedType

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:  # pragma: no cover - used until pgvector is installed
    PgVector = None


def format_vector(value: list[float] | tuple[float, ...]) -> str:
    return "[" + ",".join(f"{item:.8f}" for item in value) + "]"


class FallbackVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect: Any):
        def process(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, str):
                return value
            return format_vector(value)

        return process


def Vector(dimensions: int):
    if PgVector is not None:
        return PgVector(dimensions)
    return FallbackVector(dimensions)
