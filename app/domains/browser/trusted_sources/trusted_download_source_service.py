"""Trusted download source service — CRUD for TrustedDownloadSource."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.trusted_download_source import TrustedDownloadSource


class TrustedDownloadSourceService:
    def __init__(self, db: Session):
        self.db = db

    def list_sources(self, user_id: UUID) -> list[TrustedDownloadSource]:
        return (
            self.db.query(TrustedDownloadSource)
            .filter(
                (TrustedDownloadSource.user_id == user_id)
                | (TrustedDownloadSource.user_id.is_(None))
            )
            .order_by(TrustedDownloadSource.domain)
            .all()
        )

    def create_source(
        self,
        user_id: UUID,
        domain: str,
        product_key: str | None = None,
        trust_level: str = "trusted",
        note: str | None = None,
    ) -> TrustedDownloadSource:
        source = TrustedDownloadSource(
            user_id=user_id,
            domain=domain,
            product_key=product_key,
            trust_level=trust_level,
            source_type="user",
            note=note,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source
