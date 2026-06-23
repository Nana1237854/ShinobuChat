import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.live2d_interaction import Live2DInteraction
from app.schemas.live2d_interaction import Live2DInteractionCreate, Live2DInteractionOut

logger = logging.getLogger(__name__)


class Live2DInteractionService:
    """Records Live2D click events to DB.

    Does NOT write to Memory (long-term memory) — these are transient
    interaction events, not conversational context.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(self, user_id: UUID, payload: Live2DInteractionCreate) -> Live2DInteractionOut:
        interaction = Live2DInteraction(
            user_id=user_id,
            hit_area=payload.hit_area.value,
            x=payload.x,
            y=payload.y,
        )
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)

        return Live2DInteractionOut(event_id=interaction.id)
