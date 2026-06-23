import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import BadRequestError
from app.db.session import Base
from app.models.user import User
from app.models.user_skill import UserSkill
from app.services.default_skill_seed_service import ensure_default_user_skills
from app.services.skill_manager import SkillManager

SEED_SKILL = """---
name: gentle-daily-checkin
description: 温和日常关怀 Skill
keywords: [日常, 陪伴]
version: 1.0.0
---

# Gentle Daily Checkin

## Trigger

用户说"今天好累"时使用。

## Workflow

1. 接住用户状态
2. 给一个温柔小问题

## Output

简短共情 + 小问题
"""


class DefaultSkillSeedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="seed@example.com", hashed_password="x", display_name="Seed"))
            db.commit()

        self._seed_dir = tempfile.TemporaryDirectory()
        skill_dir = Path(self._seed_dir.name) / "gentle-daily-checkin"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(SEED_SKILL, encoding="utf-8")

        self._seed_patch = patch(
            "app.services.default_skill_seed_service._seed_root",
            return_value=Path(self._seed_dir.name),
        )
        self._seed_patch.start()

    def tearDown(self):
        self._seed_patch.stop()
        self._seed_dir.cleanup()
        Base.metadata.drop_all(bind=self.engine)

    # ── basic seeding ──────────────────────────────────────────

    def test_first_call_installs_default_skills(self):
        with self.Session() as db:
            created = ensure_default_user_skills(db, self.user_id)
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0].name, "gentle-daily-checkin")
            self.assertEqual(created[0].installed_from, "default")
            self.assertTrue(created[0].enabled)

    def test_second_call_is_idempotent(self):
        with self.Session() as db:
            first = ensure_default_user_skills(db, self.user_id)
            self.assertEqual(len(first), 1)

            second = ensure_default_user_skills(db, self.user_id)
            self.assertEqual(len(second), 0)

            skills = db.query(UserSkill).filter(UserSkill.user_id == self.user_id).all()
            self.assertEqual(len(skills), 1)

    def test_existing_skill_not_overwritten(self):
        with self.Session() as db:
            existing = UserSkill(
                user_id=self.user_id,
                name="gentle-daily-checkin",
                description="用户自定义版本",
                content="custom content",
                keywords=["custom"],
                enabled=False,
                installed_from="text",
                source_url=None,
            )
            db.add(existing)
            db.commit()
            existing_id = existing.id

        with self.Session() as db:
            created = ensure_default_user_skills(db, self.user_id)
            self.assertEqual(len(created), 0)

            persisted = db.query(UserSkill).filter(UserSkill.id == existing_id).first()
            self.assertIsNotNone(persisted)
            self.assertEqual(persisted.description, "用户自定义版本")
            self.assertFalse(persisted.enabled)
            self.assertEqual(persisted.installed_from, "text")

    def test_installed_from_is_default(self):
        with self.Session() as db:
            created = ensure_default_user_skills(db, self.user_id)
            self.assertEqual(created[0].installed_from, "default")

    def test_enabled_is_true(self):
        with self.Session() as db:
            created = ensure_default_user_skills(db, self.user_id)
            self.assertTrue(created[0].enabled)

    # ── SkillManager integration ───────────────────────────────

    def test_runtime_skills_includes_seeded_skills(self):
        with self.Session() as db:
            ensure_default_user_skills(db, self.user_id)
            runtime = SkillManager(db).runtime_skills(self.user_id)
            self.assertGreaterEqual(len(runtime), 1)
            names = [skill.name for skill in runtime]
            self.assertIn("gentle-daily-checkin", names)

    # ── frontmatter validation ─────────────────────────────────

    def test_seed_skill_frontmatter_is_parseable(self):
        """Every seed SKILL.md must pass SkillManager.parse()."""
        from app.services.default_skill_seed_service import _seed_root

        root = _seed_root()
        if not root.exists():
            self.skipTest("Seed root not found (real path may differ in CI)")

        for skill_file in sorted(root.glob("*/SKILL.md")):
            content = skill_file.read_text(encoding="utf-8")
            with self.Session() as db:
                parsed = SkillManager(db).parse(content)
                self.assertTrue(parsed.name, f"{skill_file}: missing name")
                self.assertTrue(parsed.description, f"{skill_file}: missing description")
                self.assertIsInstance(parsed.keywords, tuple, f"{skill_file}: keywords not a tuple")

    # ── missing seed directory ─────────────────────────────────

    def test_missing_seed_directory_returns_empty(self):
        with patch(
            "app.services.default_skill_seed_service._seed_root",
            return_value=Path("/nonexistent/seed/path/that/does/not/exist"),
        ):
            with self.Session() as db:
                created = ensure_default_user_skills(db, self.user_id)
                self.assertEqual(len(created), 0)

    # ── malformed seed file is skipped ─────────────────────────

    def test_malformed_seed_file_is_skipped(self):
        bad_dir = Path(self._seed_dir.name) / "bad-skill"
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "SKILL.md").write_text("no frontmatter at all", encoding="utf-8")

        with self.Session() as db:
            created = ensure_default_user_skills(db, self.user_id)
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0].name, "gentle-daily-checkin")


class SkillInstallUrlAndFileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="install@example.com", hashed_password="x", display_name="Install"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _manager(self):
        return SkillManager(self.Session())

    # ── URL install ──────────────────────────────────────────────

    def test_install_from_url_rejects_invalid_scheme(self):
        from app.core.exceptions import BadRequestError

        mgr = self._manager()
        with self.assertRaises(BadRequestError):
            mgr.install_from_url(self.user_id, "ftp://example.com/skill.md")

    def test_install_from_url_rejects_missing_frontmatter(self):
        from app.core.exceptions import BadRequestError

        class FakeResponse:
            body = b"no frontmatter here"
        fake_client = type("FakeClient", (), {
            "request_bytes": lambda self, url, timeout: FakeResponse()
        })()

        mgr = self._manager()
        with patch("app.services.http_client.UrllibHttpClient", return_value=fake_client):
            with self.assertRaises(BadRequestError):
                mgr.install_from_url(self.user_id, "https://example.com/skill.md")

    def test_install_from_url_success(self):
        class FakeResponse:
            body = SEED_SKILL.encode("utf-8")
        fake_client = type("FakeClient", (), {
            "request_bytes": lambda self, url, timeout, **kw: FakeResponse()
        })()

        mgr = self._manager()
        with patch("app.services.http_client.UrllibHttpClient", return_value=fake_client):
            skill = mgr.install_from_url(self.user_id, "https://example.com/skill.md")

        self.assertEqual(skill.installed_from, "url")
        self.assertEqual(skill.source_url, "https://example.com/skill.md")
        self.assertTrue(skill.enabled)

    def test_install_from_url_rejects_oversize(self):
        from app.core.exceptions import BadRequestError

        class FakeResponse:
            body = b"#" * 200_000
        fake_client = type("FakeClient", (), {
            "request_bytes": lambda self, url, timeout: FakeResponse()
        })()

        mgr = self._manager()
        with patch("app.services.http_client.UrllibHttpClient", return_value=fake_client):
            with self.assertRaises(BadRequestError):
                mgr.install_from_url(self.user_id, "https://example.com/skill.md")

    # ── File install ─────────────────────────────────────────────

    def test_install_from_file_rejects_non_utf8(self):
        from app.core.exceptions import BadRequestError

        mgr = self._manager()
        gbk_bytes = "你好世界".encode("gbk")
        with self.assertRaises(BadRequestError):
            mgr.install_from_file(self.user_id, gbk_bytes, "skill.md")

    def test_install_from_file_success(self):
        mgr = self._manager()
        skill = mgr.install_from_file(self.user_id, SEED_SKILL.encode("utf-8"), "skill.md")

        self.assertEqual(skill.installed_from, "file")
        self.assertIsNone(skill.source_url)
        self.assertTrue(skill.enabled)
        self.assertEqual(skill.name, "gentle-daily-checkin")

if __name__ == "__main__":
    unittest.main()
