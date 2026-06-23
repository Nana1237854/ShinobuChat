import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.live2d_interaction import Live2DInteraction
from app.schemas.live2d_interaction import Live2DInteractionCreate, Live2DInteractionOut

logger = logging.getLogger(__name__)

_SENSITIVE_METADATA_KEYS = frozenset({
    "token", "password", "secret", "api_key", "api_key_id", "authorization", "key",
})
_METADATA_MAX_BYTES = 1024
_VALID_INTERACTION_TYPES = frozenset({"click", "long_press"})


def _strip_sensitive_keys(data: dict | None) -> dict | None:
    """Recursively remove sensitive keys from metadata dict."""
    if data is None:
        return None
    clean: dict = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_METADATA_KEYS:
            continue
        if isinstance(v, dict):
            clean[k] = _strip_sensitive_keys(v)
        else:
            clean[k] = v
    return clean


def _metadata_within_limit(data: dict | None) -> dict | None:
    """Return data only if its JSON-serialized size is <= 1024 bytes, else None."""
    if data is None:
        return None
    try:
        blob = json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        logger.warning("Metadata is not JSON-serializable; discarding.")
        return None
    if len(blob.encode("utf-8")) > _METADATA_MAX_BYTES:
        logger.warning(
            "Metadata exceeds %d bytes (%d bytes); discarding.",
            _METADATA_MAX_BYTES,
            len(blob.encode("utf-8")),
        )
        return None
    return data


class Live2DInteractionService:
    """Records Live2D click events to DB.

    Does NOT write to Memory (long-term memory) — these are transient
    interaction events, not conversational context.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(self, user_id: UUID, payload: Live2DInteractionCreate) -> Live2DInteractionOut:
        # Validate and default interaction_type
        interaction_type = getattr(payload, "interaction_type", None) or "click"
        if interaction_type not in _VALID_INTERACTION_TYPES:
            interaction_type = "click"

        # Sanitize metadata: strip sensitive keys and enforce size limit
        clean_meta = _strip_sensitive_keys(payload.metadata)
        clean_meta = _metadata_within_limit(clean_meta)

        interaction = Live2DInteraction(
            user_id=user_id,
            hit_area=payload.hit_area.value,
            x=payload.x,
            y=payload.y,
            interaction_type=interaction_type,
            interaction_metadata=clean_meta,
        )
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)

        return Live2DInteractionOut(
            event_id=interaction.id,
            interaction_type=interaction.interaction_type,
        )
