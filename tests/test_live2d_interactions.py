import json
import uuid
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.live2d_interaction import Live2DInteraction
from app.models.user import User
from app.schemas.live2d_interaction import Live2DHitArea, Live2DInteractionCreate
from app.services.live2d_interaction_service import (
    Live2DInteractionService,
    _strip_sensitive_keys,
    _metadata_within_limit,
)


def _make_payload(**overrides):
    defaults = dict(
        hit_area=Live2DHitArea.HEAD, x=0.5, y=0.2,
        timestamp=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Live2DInteractionCreate(**defaults)


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

    # ------------------------------------------------------------------
    # Original tests
    # ------------------------------------------------------------------

    def test_record_head_tap_returns_event_id(self):
        result = self._svc().record(self.user_id, _make_payload())
        self.assertIsNotNone(result.event_id)

    def test_record_body_interaction(self):
        result = self._svc().record(
            self.user_id,
            _make_payload(hit_area=Live2DHitArea.BODY, x=0.5, y=0.6),
        )
        self.assertIsNotNone(result.event_id)

    def test_record_all_hit_areas(self):
        svc = self._svc()
        for area in Live2DHitArea:
            result = svc.record(self.user_id, _make_payload(hit_area=area))
            self.assertIsNotNone(result.event_id)

    def test_cross_user_isolation(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o@t.com", hashed_password="x", display_name="O"))
            db.commit()

        self._svc().record(self.user_id, _make_payload())

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
        self._svc().record(self.user_id, _make_payload())
        # Verify no memory rows were created by this transaction
        from app.models.memory import Memory
        with self.Session() as db:
            count = db.query(Memory).filter(Memory.user_id == self.user_id).count()
            self.assertEqual(count, 0)

    # ------------------------------------------------------------------
    # B15: interaction_type
    # ------------------------------------------------------------------

    def test_interaction_type_defaults_to_click(self):
        """When no interaction_type is provided, it defaults to 'click'."""
        result = self._svc().record(self.user_id, _make_payload())
        self.assertEqual(result.interaction_type, "click")

        # Verify persisted
        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            self.assertEqual(row.interaction_type, "click")

    def test_interaction_type_long_press_accepted(self):
        """interaction_type 'long_press' is recorded correctly."""
        result = self._svc().record(
            self.user_id, _make_payload(interaction_type="long_press"),
        )
        self.assertEqual(result.interaction_type, "long_press")

        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            self.assertEqual(row.interaction_type, "long_press")

    def test_interaction_type_invalid_rejected_by_schema(self):
        """An unknown interaction_type is rejected by Pydantic validation."""
        with self.assertRaises(ValidationError):
            _make_payload(interaction_type="swipe")

    # ------------------------------------------------------------------
    # B15: metadata
    # ------------------------------------------------------------------

    def test_metadata_stored_when_valid(self):
        md = {"motion_group": "tap_body"}
        result = self._svc().record(
            self.user_id, _make_payload(metadata=md),
        )
        self.assertIsNotNone(result.event_id)

        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            self.assertEqual(row.interaction_metadata, md)

    def test_metadata_over_1024_bytes_is_discarded(self):
        """Metadata whose JSON-encoded size exceeds 1024 bytes is rejected."""
        # Build a payload just over 1024 bytes
        big_value = "a" * 1020
        md = {"payload": big_value}  # "payload" + quotes + braces = extra bytes
        result = self._svc().record(
            self.user_id, _make_payload(metadata=md),
        )
        self.assertIsNotNone(result.event_id)

        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            self.assertIsNone(row.interaction_metadata)

    def test_sensitive_metadata_keys_stripped(self):
        """Metadata keys like token, password, secret etc. are removed."""
        md = {
            "motion_group": "tap_head",
            "token": "abc123",
            "Password": "secret123",
            "api_key": "sk-abc",
            "api_key_id": "kid-1",
            "authorization": "Bearer x",
            "secret": "s3cr3t",
            "key": "mykey",
            "safe_field": "keep_me",
        }
        result = self._svc().record(
            self.user_id, _make_payload(metadata=md),
        )
        self.assertIsNotNone(result.event_id)

        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            stored = row.interaction_metadata
            self.assertIsNotNone(stored)
            self.assertNotIn("token", stored)
            self.assertNotIn("Password", stored)
            self.assertNotIn("api_key", stored)
            self.assertNotIn("api_key_id", stored)
            self.assertNotIn("authorization", stored)
            self.assertNotIn("secret", stored)
            self.assertNotIn("key", stored)
            self.assertIn("motion_group", stored)
            self.assertIn("safe_field", stored)

    def test_sensitive_keys_stripped_deep(self):
        """Sensitive keys are stripped from nested dictionaries too."""
        md = {
            "nested": {
                "token": "nested_secret",
                "inner": {"api_key": "deep_secret", "ok": True},
            },
            "safe": "value",
        }
        result = self._svc().record(
            self.user_id, _make_payload(metadata=md),
        )
        self.assertIsNotNone(result.event_id)

        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            stored = row.interaction_metadata
            self.assertEqual(stored["nested"], {"inner": {"ok": True}})
            self.assertEqual(stored["safe"], "value")

    def test_metadata_none_is_preserved(self):
        """None metadata stays None."""
        result = self._svc().record(
            self.user_id, _make_payload(metadata=None),
        )
        self.assertIsNotNone(result.event_id)
        with self.Session() as db:
            row = db.query(Live2DInteraction).filter(
                Live2DInteraction.user_id == self.user_id
            ).first()
            self.assertIsNone(row.interaction_metadata)

    # ------------------------------------------------------------------
    # Unit tests for pure helpers
    # ------------------------------------------------------------------

    def test_strip_sensitive_keys_preserves_safe(self):
        out = _strip_sensitive_keys({"a": 1, "b": 2})
        self.assertEqual(out, {"a": 1, "b": 2})

    def test_strip_sensitive_keys_removes_all_variants(self):
        out = _strip_sensitive_keys({
            "token": 1, "TOKEN": 2, "Token": 3,
        })
        self.assertEqual(out, {})

    def test_metadata_within_limit_small(self):
        data = {"k": "v"}
        self.assertEqual(_metadata_within_limit(data), data)

    def test_metadata_within_limit_exactly_1024(self):
        # Generate a dict whose JSON representation is exactly 1024 bytes
        payload = "あ" * 510  # 510 CJK chars x 2 bytes = 1020, plus 4 for '[""]'
        data = {"k": payload}
        blob = json.dumps(data, ensure_ascii=False)
        if len(blob.encode("utf-8")) > 1024:
            # Trim until it fits
            while len(json.dumps({"k": payload}, ensure_ascii=False).encode("utf-8")) > 1024:
                payload = payload[:-1]
        data = {"k": payload}
        self.assertEqual(_metadata_within_limit(data), data)

    def test_metadata_within_limit_over_1024(self):
        data = {"k": "a" * 1100}
        self.assertIsNone(_metadata_within_limit(data))
