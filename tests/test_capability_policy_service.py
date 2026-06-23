"""CapabilityPolicyService unit tests with in-memory SQLite (Phase 3 fix).

Covers: defaults, ensure success, ensure raises ForbiddenError, unknown capability.
"""

import json
import uuid
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ForbiddenError
from app.db.session import Base
from app.models.user import User
from app.models.user_config import UserConfig
from app.services.capabilities.capability_policy_service import CapabilityPolicyService


def _save_local_agent_settings(db, user_id, data: dict):
    row = (
        db.query(UserConfig)
        .filter(
            UserConfig.user_id == user_id,
            UserConfig.field_name == "local_agent_settings",
        )
        .first()
    )
    if row is None:
        row = UserConfig(
            user_id=user_id,
            field_name="local_agent_settings",
            field_value=json.dumps(data, ensure_ascii=False),
            encrypted=False,
        )
        db.add(row)
    else:
        row.field_value = json.dumps(data, ensure_ascii=False)
    db.commit()
    return row


class CapabilityPolicyServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="t@t.com", hashed_password="x", display_name="T"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> CapabilityPolicyService:
        return CapabilityPolicyService(self.Session())

    # ── Defaults ──

    def test_local_launcher_enabled_by_default(self):
        decision = self._svc().check(self.user_id, "local_launcher")
        self.assertTrue(decision.enabled)
        self.assertFalse(decision.requires_confirmation)

    def test_browser_reader_enabled_by_default(self):
        decision = self._svc().check(self.user_id, "browser_reader")
        self.assertTrue(decision.enabled)
        self.assertTrue(decision.requires_confirmation)

    def test_browser_automation_disabled_by_default(self):
        decision = self._svc().check(self.user_id, "browser_automation")
        self.assertFalse(decision.enabled)
        self.assertTrue(decision.requires_confirmation)

    def test_mcp_disabled_by_default(self):
        decision = self._svc().check(self.user_id, "mcp")
        self.assertFalse(decision.enabled)
        self.assertFalse(decision.requires_confirmation)

    def test_download_safety_enabled_by_default(self):
        decision = self._svc().check(self.user_id, "download_safety")
        self.assertTrue(decision.enabled)
        self.assertTrue(decision.requires_confirmation)

    # ── ensure() success path ──

    def test_ensure_local_launcher_passes(self):
        decision = self._svc().ensure(self.user_id, "local_launcher")
        self.assertTrue(decision.enabled)

    def test_ensure_browser_reader_passes(self):
        decision = self._svc().ensure(self.user_id, "browser_reader")
        self.assertTrue(decision.enabled)

    def test_ensure_download_safety_passes(self):
        decision = self._svc().ensure(self.user_id, "download_safety")
        self.assertTrue(decision.enabled)

    # ── ensure() raises ForbiddenError for disabled ──

    def test_ensure_browser_automation_raises(self):
        with self.assertRaises(ForbiddenError):
            self._svc().ensure(self.user_id, "browser_automation")

    def test_ensure_mcp_raises(self):
        with self.assertRaises(ForbiddenError):
            self._svc().ensure(self.user_id, "mcp")

    def test_ensure_browser_reader_disabled_raises(self):
        db = self.Session()
        _save_local_agent_settings(db, self.user_id, {"browser_reader_enabled": False})
        db.close()

        decision = self._svc().check(self.user_id, "browser_reader")
        self.assertFalse(decision.enabled)

        with self.assertRaises(ForbiddenError):
            self._svc().ensure(self.user_id, "browser_reader")

    # ── Unknown capability ──

    def test_check_unknown_capability_returns_disabled(self):
        decision = self._svc().check(self.user_id, "unknown_xxx")
        self.assertFalse(decision.enabled)
        self.assertTrue(decision.requires_confirmation)
        self.assertEqual(decision.reason, "Unknown capability")

    def test_ensure_unknown_capability_raises(self):
        with self.assertRaises(ForbiddenError):
            self._svc().ensure(self.user_id, "unknown_xxx")
