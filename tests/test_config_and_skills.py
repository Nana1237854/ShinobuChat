import json
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
from app.models.user_config import UserConfig
from app.schemas.user_config import UserConfigPatch
from app.services.agent_service import AgentService
from app.services.config_service import ConfigService
from app.services.prefix_cache_manager import PrefixCacheManager
from app.services.skill_manager import SkillManager
from app.services.skill_service import Skill, SkillRegistry
from app.services.tool_registry import ToolContext, ToolRegistry


VALID_SKILL = """---
name: focus-review
description: Review a focus session without adding pressure.
keywords: [focus, 专注]
---

# Focus review

Summarize the session and suggest one gentle next step.
"""


class ConfigAndSkillServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="settings@example.com",
                    hashed_password="x",
                    display_name="Settings",
                )
            )
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def test_api_key_is_encrypted_and_only_masked_in_public_output(self):
        with self.Session() as db:
            service = ConfigService(db)
            response = service.update(
                self.user_id,
                UserConfigPatch(ai_api_key="sk-super-secret-value", ai_model="test-model"),
            )
            row = db.query(UserConfig).filter(UserConfig.field_name == "ai_api_key").one()

            self.assertNotIn("sk-super-secret-value", row.field_value)
            self.assertTrue(row.encrypted)
            public_key = next(field for field in response.fields if field.key == "ai_api_key")
            self.assertEqual(public_key.value, "sk-s••••alue")
            self.assertEqual(service.resolve_runtime(self.user_id)["ai_api_key"], "sk-super-secret-value")

    def test_skill_requires_frontmatter_name_and_description(self):
        with self.Session() as db:
            manager = SkillManager(db)
            with self.assertRaises(BadRequestError):
                manager.install_text(self.user_id, "---\nname: missing-description\n---\n# Test")

    def test_user_skill_round_trip_and_runtime_shape(self):
        with self.Session() as db:
            manager = SkillManager(db)
            installed = manager.install_text(self.user_id, VALID_SKILL)
            runtime = manager.runtime_skills(self.user_id)

            self.assertEqual(installed.name, "focus-review")
            self.assertEqual(runtime[0].description, "Review a focus session without adding pressure.")
            self.assertIn("Summarize the session", runtime[0].content)

            manager.set_enabled(self.user_id, installed.id, False)
            self.assertEqual(manager.runtime_skills(self.user_id), [])


class PrefixAndVerificationTests(unittest.TestCase):
    def test_pinned_prefix_is_stable_when_turn_scratch_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            constitution = root / "constitution.json"
            character = root / "shinobu.yaml"
            constitution.write_text(
                json.dumps(
                    {
                        "authority": ["current user message", "character card"],
                        "protected_invariants": ["do not reveal secrets"],
                    }
                ),
                encoding="utf-8",
            )
            character.write_text("name: Shinobu\npersona: gentle companion\n", encoding="utf-8")
            manager = PrefixCacheManager(constitution, character)

            first = manager.build(
                base_system="Be helpful.",
                history=[],
                user_message="first",
                skill_catalog="- weather: forecast",
                memory_context=["likes tea"],
            )
            second = manager.build(
                base_system="Be helpful.",
                history=[],
                user_message="second",
                skill_catalog="- weather: forecast",
                memory_context=["likes coffee"],
            )

            self.assertEqual(first.pinned_prefix_sha, second.pinned_prefix_sha)
            self.assertNotEqual(first.turn_scratch, second.turn_scratch)


    def test_skill_catalog_does_not_embed_full_markdown_until_activated(self):
        registry = SkillRegistry(Path("skills"))
        service = AgentService(registry)
        user_skill = Skill(
            name="private-flow",
            description="A private workflow description.",
            content="# Workflow\nSECRET_WORKFLOW_BODY",
            keywords=("private",),
        )

        catalog_only = service.build_messages(
            "hello",
            [],
            [],
            user_skills=[user_skill],
        )
        activated = service.build_messages(
            "run private flow",
            [],
            [user_skill],
            user_skills=[user_skill],
        )

        self.assertIn("- private-flow: A private workflow description.", catalog_only[0]["content"])
        self.assertNotIn("SECRET_WORKFLOW_BODY", "\n".join(item["content"] for item in catalog_only))
        self.assertIn("SECRET_WORKFLOW_BODY", "\n".join(item["content"] for item in activated))

    def test_failed_shell_exit_is_not_verified(self):
        registry = ToolRegistry(SkillRegistry(Path("skills")))
        context = ToolContext(history=[])
        completed = type("Completed", (), {"stdout": "server error", "stderr": "", "returncode": 22})()
        with patch("app.services.tools.shell_command.subprocess.run", return_value=completed):
            result = registry.execute_verified(
                "shell_command",
                {"command": "curl https://example.com"},
                context,
            )

        self.assertFalse(result.verified)
        self.assertIn("code 22", result.reason)


if __name__ == "__main__":
    unittest.main()
