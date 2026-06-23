import uuid
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.live2d_interaction import Live2DInteraction
from app.models.user import User
from app.schemas.live2d_interaction import Live2DHitArea, Live2DInteractionCreate
from app.services.live2d_interaction_service import Live2DInteractionService


class Live2DInteractionServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="l2d@t.com", hashed_password="x", display_name="L2D"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> Live2DInteractionService:
        return Live2DInteractionService(self.Session())

    def test_record_head_tap_returns_event_id(self):
        result = self._svc().record(
            self.user_id,
            Live2DInteractionCreate(
                hit_area=Live2DHitArea.HEAD, x=0.5, y=0.2,
                timestamp=datetime.now(timezone.utc),
            ),
        )
        self.assertIsNotNone(result.event_id)

    def test_record_body_interaction(self):
        result = self._svc().record(
            self.user_id,
            Live2DInteractionCreate(
                hit_area=Live2DHitArea.BODY, x=0.5, y=0.6,
                timestamp=datetime.now(timezone.utc),
            ),
        )
        self.assertIsNotNone(result.event_id)

    def test_record_all_hit_areas(self):
        svc = self._svc()
        for area in Live2DHitArea:
            result = svc.record(
                self.user_id,
                Live2DInteractionCreate(
                    hit_area=area, x=0.5, y=0.5,
                    timestamp=datetime.now(timezone.utc),
                ),
            )
            self.assertIsNotNone(result.event_id)

    def test_cross_user_isolation(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o@t.com", hashed_password="x", display_name="O"))
            db.commit()

        self._svc().record(
            self.user_id,
            Live2DInteractionCreate(
                hit_area=Live2DHitArea.HEAD, x=0.5, y=0.2,
                timestamp=datetime.now(timezone.utc),
            ),
        )

        # Other user should see no interactions
        with self.Session() as db:
            count = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == other_id
            ).count()
            self.assertEqual(count, 0)
        # User A should have 1
        with self.Session() as db:
            count = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).count()
            self.assertEqual(count, 1)

    def test_no_memory_written(self):
        """Live2D interactions must NOT write to Memory."""
        self._svc().record(
            self.user_id,
            Live2DInteractionCreate(
                hit_area=Live2DHitArea.HEAD, x=0.5, y=0.2,
                timestamp=datetime.now(timezone.utc),
            ),
        )
        # Verify no memory rows were created by this transaction
        from app.models.memory import Memory
        with self.Session() as db:
            count = db.query(Memory).filter(Memory.user_id == self.user_id).count()
            self.assertEqual(count, 0)
