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


class UserConfigFullCoverageTests(unittest.TestCase):
    """Tests covering all 15 fields, DB > env > default priority, encryption, masking, reset."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="cfgtest@example.com",
                    hashed_password="x",
                    display_name="CfgTest",
                )
            )
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _service(self, db=None) -> ConfigService:
        if db is None:
            db = self.Session()
        return ConfigService(db)

    # --- Default / Pydantic values ---

    def test_default_value_from_pydantic(self):
        """Config fields fall back to Pydantic settings default when no env/DB override."""
        from app.core.config import settings as s

        with self.Session() as db:
            svc = ConfigService(db)
            self.assertEqual(svc.get_effective_value(self.user_id, "ai_model"), s.ai_model)
            self.assertEqual(svc.get_effective_value(self.user_id, "ai_base_url"), s.ai_base_url)
            self.assertEqual(
                svc.get_effective_value(self.user_id, "ai_request_timeout_seconds"),
                s.ai_request_timeout_seconds,
            )
            self.assertEqual(
                svc.get_effective_value(self.user_id, "ai_supports_image_input"),
                s.ai_supports_image_input,
            )
            self.assertEqual(
                svc.get_effective_value(self.user_id, "ai_lightweight_max_tokens"),
                s.ai_lightweight_max_tokens,
            )

    def test_default_value_for_tts_and_asr(self):
        from app.core.config import settings as s

        with self.Session() as db:
            svc = ConfigService(db)
            self.assertEqual(svc.get_effective_value(self.user_id, "edge_tts_voice"), s.edge_tts_voice)
            self.assertEqual(svc.get_effective_value(self.user_id, "asr_engine"), s.asr_engine)

    # --- Env override default ---

    def test_env_overrides_default(self):
        from app.core.config import Settings as _S

        env_settings = _S(
            ai_model="env-model",
            roleplay_llm_temperature=1.5,
        )
        with patch("app.services.config_service.settings", env_settings):
            with self.Session() as db:
                svc = ConfigService(db)
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "ai_model"),
                    "env-model",
                )
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "roleplay_llm_temperature"),
                    1.5,
                )

    # --- DB override env ---

    def test_db_overrides_env(self):
        from app.core.config import Settings as _S

        with self.Session() as db:
            db.add(
                UserConfig(
                    user_id=self.user_id,
                    field_name="ai_model",
                    field_value='"db-model"',
                    encrypted=False,
                )
            )
            db.commit()

        env_settings = _S(ai_model="env-model")
        with patch("app.services.config_service.settings", env_settings):
            with self.Session() as db:
                svc = ConfigService(db)
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "ai_model"),
                    "db-model",
                )

    def test_db_overrides_env_for_multiple_fields(self):
        from app.core.config import Settings as _S

        with self.Session() as db:
            db.add(
                UserConfig(
                    user_id=self.user_id,
                    field_name="edge_tts_voice",
                    field_value='"db-voice"',
                    encrypted=False,
                )
            )
            db.add(
                UserConfig(
                    user_id=self.user_id,
                    field_name="asr_engine",
                    field_value='"db-asr"',
                    encrypted=False,
                )
            )
            db.commit()

        env_settings = _S(edge_tts_voice="env-voice", asr_engine="env-asr")
        with patch("app.services.config_service.settings", env_settings):
            with self.Session() as db:
                svc = ConfigService(db)
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "edge_tts_voice"),
                    "db-voice",
                )
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "asr_engine"),
                    "db-asr",
                )

    # --- All 15 fields can be updated and read ---

    ALL_15_FIELDS = {
        "ai_api_key": "sk-test-key-12345",
        "ai_base_url": "https://custom.api.com/v1",
        "ai_model": "custom-model",
        "ai_request_timeout_seconds": 30,
        "ai_supports_image_input": False,
        "ai_lightweight_max_tokens": 2048,
        "roleplay_llm_model": "roleplay-model",
        "roleplay_llm_temperature": 1.2,
        "decision_llm_model": "decision-model",
        "decision_llm_temperature": 0.5,
        "google_search_api_key": "sk-google-key",
        "google_search_cx": "custom-cx-id",
        "edge_tts_voice": "zh-CN-YunxiNeural",
        "asr_engine": "funasr",
        "whisper_api_key": "sk-whisper-key",
    }

    ENCRYPTED_FIELDS = {"ai_api_key", "google_search_api_key", "whisper_api_key"}

    def test_all_15_fields_can_be_updated_and_read_back(self):
        with self.Session() as db:
            svc = ConfigService(db)
            patch_req = UserConfigPatch(**self.ALL_15_FIELDS)
            svc.update(self.user_id, patch_req)

        with self.Session() as db:
            svc = ConfigService(db)
            effective = svc.resolve_runtime(self.user_id)
            for field_name, expected_value in self.ALL_15_FIELDS.items():
                with self.subTest(field=field_name):
                    self.assertEqual(
                        effective[field_name],
                        expected_value,
                        f"Field {field_name} should be {expected_value}",
                    )

    def test_get_effective_value_returns_each_field(self):
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(**self.ALL_15_FIELDS))

        with self.Session() as db:
            svc = ConfigService(db)
            for field_name, expected_value in self.ALL_15_FIELDS.items():
                with self.subTest(field=field_name):
                    self.assertEqual(
                        svc.get_effective_value(self.user_id, field_name),
                        expected_value,
                    )

    def test_get_effective_value_raises_for_unknown_field(self):
        with self.Session() as db:
            svc = ConfigService(db)
            with self.assertRaises(Exception):
                svc.get_effective_value(self.user_id, "nonexistent_field")

    # --- Encryption ---

    def test_encrypted_fields_are_not_plaintext_in_db(self):
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(
                self.user_id,
                UserConfigPatch(
                    ai_api_key="sk-secret-key",
                    google_search_api_key="sk-google-secret",
                    whisper_api_key="sk-whisper-secret",
                ),
            )

        with self.Session() as db:
            rows = db.query(UserConfig).filter(
                UserConfig.user_id == self.user_id,
                UserConfig.field_name.in_(self.ENCRYPTED_FIELDS),
            ).all()
            self.assertEqual(len(rows), 3)
            for row in rows:
                with self.subTest(field=row.field_name):
                    self.assertTrue(row.encrypted)
                    self.assertNotIn("sk-", row.field_value, f"{row.field_name} should be encrypted")

    def test_non_encrypted_fields_are_plaintext_in_db(self):
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_model="gpt-5-mini"))

        with self.Session() as db:
            row = (
                db.query(UserConfig)
                .filter(
                    UserConfig.user_id == self.user_id,
                    UserConfig.field_name == "ai_model",
                )
                .first()
            )
            self.assertIsNotNone(row)
            self.assertFalse(row.encrypted)
            self.assertIn("gpt-5-mini", row.field_value)

    def test_encrypt_decrypt_round_trip(self):
        with self.Session() as db:
            svc = ConfigService(db)
            plaintext = "my-super-secret-api-key"
            encrypted = svc.encrypt_value(plaintext)
            self.assertNotEqual(encrypted, plaintext)
            self.assertNotIn(plaintext, encrypted)
            decrypted = svc.decrypt_value(encrypted)
            self.assertEqual(decrypted, plaintext)

    # --- Masking ---

    def test_api_key_is_masked_in_response(self):
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(
                self.user_id,
                UserConfigPatch(
                    ai_api_key="sk-this-is-a-very-long-secret-key-for-testing",
                ),
            )
            response = svc.list_fields(self.user_id)

            ai_key_field = next(f for f in response.fields if f.key == "ai_api_key")
            self.assertTrue(ai_key_field.encrypted)
            self.assertNotIn("sk-this-is-a-very-long-secret-key-for-testing", ai_key_field.value)
            self.assertIn("••••", str(ai_key_field.value))
            # Check masking format: first 4, middle dots, last 4
            self.assertTrue(str(ai_key_field.value).startswith("sk-t"))
            self.assertTrue(str(ai_key_field.value).endswith("ing"))

    def test_mask_secret_short_value(self):
        with self.Session() as db:
            svc = ConfigService(db)
            self.assertEqual(svc.mask_secret("abc"), "••••••••")
            self.assertEqual(svc.mask_secret(""), "")
            self.assertEqual(svc.mask_secret(None), "")

    def test_mask_secret_normal_value(self):
        with self.Session() as db:
            svc = ConfigService(db)
            masked = svc.mask_secret("sk-abcdefghijklmnop")
            self.assertIn("••••", masked)

    def test_non_encrypted_field_not_masked(self):
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_model="gpt-5"))
            response = svc.list_fields(self.user_id)

            ai_model_field = next(f for f in response.fields if f.key == "ai_model")
            self.assertFalse(ai_model_field.encrypted)
            self.assertEqual(ai_model_field.value, "gpt-5")

    # --- Reset ---

    def test_reset_clears_user_overrides(self):
        from app.core.config import settings as s

        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_model="custom-model", edge_tts_voice="custom-voice"))
            svc.reset(self.user_id)

        with self.Session() as db:
            svc = ConfigService(db)
            self.assertEqual(
                svc.get_effective_value(self.user_id, "ai_model"),
                s.ai_model,
            )
            self.assertEqual(
                svc.get_effective_value(self.user_id, "edge_tts_voice"),
                s.edge_tts_voice,
            )

    def test_reset_returns_to_env_when_env_set(self):
        from app.core.config import Settings as _S

        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_model="custom-model"))
            svc.reset(self.user_id)

        env_settings = _S(ai_model="env-model-2")
        with patch("app.services.config_service.settings", env_settings):
            with self.Session() as db:
                svc = ConfigService(db)
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "ai_model"),
                    "env-model-2",
                )

    def test_reset_empty_config_is_noop(self):
        with self.Session() as db:
            svc = ConfigService(db)
            response = svc.reset(self.user_id)
            self.assertIsInstance(response, type(svc.list_fields(self.user_id)))

    # --- Masked value skipped in update ---

    def test_masked_value_is_skipped_on_update(self):
        """Sending a masked value (containing ••••) should not overwrite the real secret."""
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_api_key="sk-real-secret-12345"))

        # Now send masked-looking value
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_api_key="sk-r••••2345"))
            effective = svc.get_effective_value(self.user_id, "ai_api_key")
            self.assertEqual(effective, "sk-real-secret-12345")

    # --- resolve_runtime user scoping ---

    def test_resolve_runtime_is_scoped_to_user(self):
        other_user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(
                User(
                    id=other_user_id,
                    email="other@example.com",
                    hashed_password="x",
                    display_name="Other",
                )
            )
            db.commit()

        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_model="my-model"))
            svc.update(other_user_id, UserConfigPatch(ai_model="other-model"))

        with self.Session() as db:
            svc = ConfigService(db)
            self.assertEqual(
                svc.get_effective_value(self.user_id, "ai_model"),
                "my-model",
            )
            self.assertEqual(
                svc.get_effective_value(other_user_id, "ai_model"),
                "other-model",
            )

    # --- Encryption key validation ---

    def test_validate_encryption_key_warns_when_unset(self):
        # When key is empty (as in test), should log warning but not raise
        try:
            with self.assertLogs("app.services.config_service", level="WARNING") as cm:
                ConfigService.validate_encryption_key()
            self.assertTrue(
                any("SC_CONFIG_ENCRYPTION_KEY is not set" in msg for msg in cm.output),
                "Should log warning about missing encryption key",
            )
        except Exception:
            self.fail("validate_encryption_key should not raise when key is unset")

    @patch("app.services.config_service.settings")
    def test_validate_encryption_key_raises_for_invalid_key(self, mock_settings):
        mock_settings.config_encryption_key = "not-a-valid-fernet-key"
        from app.core.exceptions import ConfigurationError

        with self.assertRaises(ConfigurationError):
            ConfigService.validate_encryption_key()

    @patch("app.services.config_service.settings")
    def test_validate_encryption_key_passes_for_valid_key(self, mock_settings):
        from cryptography.fernet import Fernet

        mock_settings.config_encryption_key = Fernet.generate_key().decode()
        # Should not raise
        try:
            ConfigService.validate_encryption_key()
        except Exception:
            self.fail("validate_encryption_key should not raise for valid key")

    # --- Update with None (delete) ---

    def test_update_with_none_deletes_config_row(self):
        with self.Session() as db:
            svc = ConfigService(db)
            svc.update(self.user_id, UserConfigPatch(ai_model="temp-model"))
            # Delete by setting None
            svc.update(self.user_id, UserConfigPatch(ai_model=None))

        with self.Session() as db:
            svc = ConfigService(db)
            from app.core.config import settings as s

            self.assertEqual(
                svc.get_effective_value(self.user_id, "ai_model"),
                s.ai_model,
            )

    # --- Empty patch is noop ---

    def test_empty_patch_does_not_crash(self):
        with self.Session() as db:
            svc = ConfigService(db)
            response = svc.update(self.user_id, UserConfigPatch())
            self.assertIsNotNone(response)
            self.assertGreater(len(response.fields), 0)


if __name__ == "__main__":
    unittest.main()
