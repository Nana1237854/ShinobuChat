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

# Provide a valid Fernet key for tests — encrypted fields require an explicit key.
TEST_ENCRYPTION_KEY = "qd1FW1RJNh0m3Di-wyg0qBNHls20FePZsWQ-LGJ83B0="


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
        # Ensure encryption key is available for encrypted field tests
        self._encryption_patch = patch(
            "app.services.config_service.settings.config_encryption_key",
            TEST_ENCRYPTION_KEY,
        )
        self._encryption_patch.start()
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
        self._encryption_patch.stop()
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
        with patch("app.services.tool_policy_service.ToolPolicyService.check") as mock_check:
            from app.services.tool_policy_service import ToolPolicyDecision
            mock_check.return_value = ToolPolicyDecision(True, "test bypass", {"rule": "test_bypass"})
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
        self._encryption_patch = patch(
            "app.services.config_service.settings.config_encryption_key",
            TEST_ENCRYPTION_KEY,
        )
        self._encryption_patch.start()
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
        self._encryption_patch.stop()
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
        # Temporarily stop the setUp patch to test the "key not set" path
        self._encryption_patch.stop()
        try:
            with self.assertLogs("app.services.config_service", level="WARNING") as cm:
                ConfigService.validate_encryption_key()
            self.assertTrue(
                any("SC_CONFIG_ENCRYPTION_KEY is not set" in msg for msg in cm.output),
                "Should log warning about missing encryption key",
            )
        except Exception:
            self.fail("validate_encryption_key should not raise when key is unset")
        finally:
            self._encryption_patch.start()

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

    # --- Display vs runtime decode split ---

    def test_list_fields_returns_mask_for_encrypted_when_no_key(self):
        """list_fields (display) returns mask when key unavailable."""
        self._encryption_patch.stop()
        try:
            with self.Session() as db:
                svc = ConfigService(db)
                svc.update(self.user_id, UserConfigPatch(ai_model="gpt-5"))
                # Encrypted field must fail to save without key, so test display
                # by directly inserting an encrypted row (simulating pre-key data)
                row = UserConfig(
                    user_id=self.user_id,
                    field_name="ai_api_key",
                    field_value="unreachable-encrypted-blob",
                    encrypted=True,
                )
                db.add(row)
                db.commit()
                # list_fields should return mask for encrypted field
                response = svc.list_fields(self.user_id)
                ai_key = next(f for f in response.fields if f.key == "ai_api_key")
                self.assertEqual(ai_key.value, "••••••••")
                self.assertEqual(ai_key.source, "user")
                self.assertTrue(ai_key.encrypted)
                # Non-encrypted field still readable
                ai_model = next(f for f in response.fields if f.key == "ai_model")
                self.assertEqual(ai_model.value, "gpt-5")
                self.assertFalse(ai_model.encrypted)
        finally:
            self._encryption_patch.start()

    def test_resolve_runtime_raises_when_encrypted_and_no_key(self):
        """resolve_runtime (runtime) raises ConfigurationError when encrypted field exists without key."""
        self._encryption_patch.stop()
        try:
            with self.Session() as db:
                # Insert an encrypted row directly
                row = UserConfig(
                    user_id=self.user_id,
                    field_name="ai_api_key",
                    field_value="encrypted-blob-data",
                    encrypted=True,
                )
                db.add(row)
                db.add(UserConfig(
                    user_id=self.user_id,
                    field_name="ai_model",
                    field_value='"safe-model"',
                    encrypted=False,
                ))
                db.commit()
                svc = ConfigService(db)
                from app.core.exceptions import ConfigurationError
                with self.assertRaises(ConfigurationError) as ctx:
                    svc.resolve_runtime(self.user_id)
                self.assertIn("ai_api_key", str(ctx.exception))
                self.assertIn("SC_CONFIG_ENCRYPTION_KEY is not set", str(ctx.exception))
        finally:
            self._encryption_patch.start()

    def test_resolve_runtime_does_not_return_mask_as_api_key(self):
        """resolve_runtime must never return '••••••••' as a real API key."""
        self._encryption_patch.stop()
        try:
            with self.Session() as db:
                row = UserConfig(
                    user_id=self.user_id,
                    field_name="whisper_api_key",
                    field_value="encrypted-whisper-key",
                    encrypted=True,
                )
                db.add(row)
                db.commit()
                svc = ConfigService(db)
                from app.core.exceptions import ConfigurationError
                with self.assertRaises(ConfigurationError):
                    result = svc.resolve_runtime(self.user_id)
                    # If it somehow doesn't raise, check it's not a mask
                    if "whisper_api_key" in result:
                        self.assertNotEqual(result["whisper_api_key"], "••••••••")
                        self.assertNotIn("••••", str(result["whisper_api_key"]))
        finally:
            self._encryption_patch.start()

    def test_non_encrypted_fields_readable_without_key(self):
        """Non-encrypted fields are still readable via runtime decode when key is missing."""
        self._encryption_patch.stop()
        try:
            with self.Session() as db:
                db.add(UserConfig(
                    user_id=self.user_id,
                    field_name="ai_model",
                    field_value='"no-key-model"',
                    encrypted=False,
                ))
                db.add(UserConfig(
                    user_id=self.user_id,
                    field_name="edge_tts_voice",
                    field_value='"no-key-voice"',
                    encrypted=False,
                ))
                db.commit()
                svc = ConfigService(db)
                # resolve_runtime works when only non-encrypted fields exist
                runtime = svc.resolve_runtime(self.user_id)
                self.assertEqual(runtime["ai_model"], "no-key-model")
                self.assertEqual(runtime["edge_tts_voice"], "no-key-voice")
                # get_effective_value also works
                self.assertEqual(
                    svc.get_effective_value(self.user_id, "ai_model"),
                    "no-key-model",
                )
        finally:
            self._encryption_patch.start()

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


class UserSkillFullCoverageTests(unittest.TestCase):
    """Tests covering install, update, delete, enable/disable, conflict detection, catalog injection."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="skilltest@example.com",
                    hashed_password="x",
                    display_name="SkillTest",
                )
            )
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _manager(self) -> SkillManager:
        return SkillManager(self.Session())

    # --- Install ---

    def test_valid_skill_installs_successfully(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        self.assertEqual(installed.name, "focus-review")
        self.assertEqual(installed.description, "Review a focus session without adding pressure.")
        self.assertIn("Summarize the session", installed.content)
        self.assertEqual(installed.installed_from, "text")
        self.assertTrue(installed.enabled)

    def test_missing_name_fails(self):
        mgr = self._manager()
        content = "---\ndescription: No name here\n---\n# Test"
        with self.assertRaises(Exception):
            mgr.install_text(self.user_id, content)

    def test_missing_description_fails(self):
        mgr = self._manager()
        content = "---\nname: my-skill\n---\n# Test"
        with self.assertRaises(Exception):
            mgr.install_text(self.user_id, content)

    def test_missing_frontmatter_fails(self):
        mgr = self._manager()
        with self.assertRaises(Exception):
            mgr.install_text(self.user_id, "# Just a heading, no frontmatter")

    def test_duplicate_name_fails(self):
        mgr = self._manager()
        mgr.install_text(self.user_id, VALID_SKILL)
        with self.assertRaises(Exception):
            mgr.install_text(self.user_id, VALID_SKILL)

    def test_install_text_round_trip_list_and_get(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        skills = mgr.list(self.user_id)
        self.assertEqual(len(skills), 1)
        fetched = mgr.get(self.user_id, installed.id)
        self.assertEqual(fetched.name, "focus-review")
        self.assertEqual(fetched.content, VALID_SKILL.strip() + "\n")

    # --- Conflict with built-in ---

    def test_conflict_with_builtin_skill_fails(self):
        mgr = self._manager()
        # "web-search-aggregator" is a built-in skill name
        conflict_skill = """---
name: web-search-aggregator
description: Try to override a built-in skill.
---
# Conflict test
"""
        from app.core.exceptions import ConflictError

        with self.assertRaises(ConflictError):
            mgr.install_text(self.user_id, conflict_skill)

    # --- Enable / Disable ---

    def test_disabled_skill_not_in_runtime(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        mgr.set_enabled(self.user_id, installed.id, False)
        runtime = mgr.runtime_skills(self.user_id)
        self.assertEqual(len(runtime), 0)

    def test_enabled_skill_appears_in_runtime(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        runtime = mgr.runtime_skills(self.user_id)
        self.assertEqual(len(runtime), 1)
        self.assertEqual(runtime[0].name, "focus-review")

    def test_re_enable_after_disable(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        mgr.set_enabled(self.user_id, installed.id, False)
        self.assertEqual(len(mgr.runtime_skills(self.user_id)), 0)
        mgr.set_enabled(self.user_id, installed.id, True)
        self.assertEqual(len(mgr.runtime_skills(self.user_id)), 1)

    # --- Delete ---

    def test_delete_removes_skill(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        mgr.delete(self.user_id, installed.id)
        self.assertEqual(len(mgr.list(self.user_id)), 0)
        self.assertEqual(len(mgr.runtime_skills(self.user_id)), 0)

    def test_delete_nonexistent_raises(self):
        mgr = self._manager()
        fake_id = uuid.uuid4()
        with self.assertRaises(Exception):
            mgr.delete(self.user_id, fake_id)

    # --- Update ---

    def test_update_skill_content(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        updated_content = """---
name: focus-review-v2
description: An updated focus review skill.
keywords: [focus-v2, 专注v2]
---
# Focus review v2
Updated instructions.
"""
        updated = mgr.update(self.user_id, installed.id, updated_content)
        self.assertEqual(updated.name, "focus-review-v2")
        self.assertIn("Updated instructions", updated.content)
        self.assertEqual(updated.description, "An updated focus review skill.")

    # --- Catalog / Prompt ---

    def test_build_skill_directory_prompt(self):
        mgr = self._manager()
        mgr.install_text(self.user_id, VALID_SKILL)
        prompt = mgr.build_skill_directory_prompt(self.user_id)
        self.assertIn("focus-review", prompt)
        self.assertIn("Review a focus session", prompt)
        self.assertNotIn("Summarize the session", prompt)  # full content NOT in directory

    def test_build_skill_directory_prompt_empty_when_no_skills(self):
        mgr = self._manager()
        prompt = mgr.build_skill_directory_prompt(self.user_id)
        self.assertEqual(prompt, "")

    def test_runtime_skills_only_enabled(self):
        mgr = self._manager()
        mgr.install_text(self.user_id, VALID_SKILL)
        skill2 = """---
name: second-skill
description: A second test skill.
---
# Second
Content here.
"""
        mgr.install_text(self.user_id, skill2)
        all_skills = mgr.list(self.user_id)
        mgr.set_enabled(self.user_id, all_skills[0].id, False)
        runtime = mgr.runtime_skills(self.user_id)
        self.assertEqual(len(runtime), 1)
        self.assertEqual(runtime[0].name, "second-skill")

    # --- SkillRegistry with user skills ---

    def test_render_catalog_includes_user_skills(self):
        mgr = self._manager()
        mgr.install_text(self.user_id, VALID_SKILL)
        runtime = mgr.runtime_skills(self.user_id)

        registry = SkillRegistry(Path("skills"))
        catalog = registry.render_catalog(extra_skills=runtime)
        self.assertIn("focus-review", catalog)
        self.assertIn("Review a focus session", catalog)
        self.assertNotIn("Summarize the session", catalog)

    def test_render_catalog_builtin_takes_precedence(self):
        """User skill with same name as built-in should not appear in catalog
        (blocked by _check_builtin_conflict at install time).
        When catalog renders, built-in takes precedence."""
        registry = SkillRegistry(Path("skills"))
        # Simulate a user skill that somehow has a built-in name
        rogue = Skill(
            name="web-search-aggregator",
            description="User's rogue override",
            content="bad content",
            keywords=(),
        )
        catalog = registry.render_catalog(extra_skills=[rogue])
        # The built-in description should appear, not the user's
        self.assertIn("web-search-aggregator", catalog)
        self.assertNotIn("User's rogue override", catalog)

    def test_describe_for_llm_includes_user_skills(self):
        registry = SkillRegistry(Path("skills"))
        user_skills = [
            Skill(
                name="user-skill-1",
                description="First user skill",
                content="Full content 1",
                keywords=("test",),
            ),
            Skill(
                name="user-skill-2",
                description="Second user skill",
                content="Full content 2",
                keywords=(),
            ),
        ]
        description = registry.describe_for_llm(user_skills=user_skills)
        self.assertIn("User-Installed Skills", description)
        self.assertIn("user-skill-1", description)
        self.assertIn("First user skill", description)
        self.assertIn("user-skill-2", description)
        self.assertNotIn("Full content 1", description)
        self.assertNotIn("Full content 2", description)

    def test_describe_for_llm_no_user_skills(self):
        registry = SkillRegistry(Path("skills"))
        description = registry.describe_for_llm()
        self.assertNotIn("User-Installed Skills", description)

    # --- install_from_file ---

    def test_install_from_file_succeeds(self):
        mgr = self._manager()
        installed = mgr.install_from_file(
            self.user_id,
            VALID_SKILL.encode("utf-8"),
            filename="focus-review.md",
        )
        self.assertEqual(installed.name, "focus-review")
        self.assertEqual(installed.installed_from, "file")
        self.assertIsNone(installed.source_url)

    def test_install_from_file_rejects_non_utf8(self):
        mgr = self._manager()
        with self.assertRaises(Exception):
            mgr.install_from_file(self.user_id, b"\xff\xfe\x00\x01")

    # --- Keywords ---

    def test_keywords_are_parsed_and_stored(self):
        mgr = self._manager()
        installed = mgr.install_text(self.user_id, VALID_SKILL)
        self.assertIn("focus", installed.keywords)
        self.assertIn("专注", installed.keywords)

    # --- User scoping ---

    def test_skills_are_scoped_to_user(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(
                User(
                    id=other_id,
                    email="other-skill@example.com",
                    hashed_password="x",
                    display_name="OtherSkill",
                )
            )
            db.commit()

        mgr = self._manager()
        mgr.install_text(self.user_id, VALID_SKILL)
        self.assertEqual(len(mgr.list(self.user_id)), 1)
        self.assertEqual(len(mgr.list(other_id)), 0)

    # --- Invalid YAML frontmatter ---

    def test_invalid_yaml_frontmatter_fails(self):
        mgr = self._manager()
        bad_yaml = """---
name: [unclosed
description: Bad YAML
---
# Bad skill
"""
        with self.assertRaises(Exception):
            mgr.install_text(self.user_id, bad_yaml)

    # --- install_from_url fetches and installs ---

    def test_install_from_url_success(self):
        from unittest.mock import patch

        mgr = self._manager()

        class FakeResponse:
            body = VALID_SKILL.encode("utf-8")

        class FakeClient:
            def request_bytes(self, url, timeout=30):
                return FakeResponse()

        with patch(
            "app.services.http_client.UrllibHttpClient",
            return_value=FakeClient(),
        ):
            installed = mgr.install_from_url(
                self.user_id,
                "https://raw.githubusercontent.com/user/repo/main/SKILL.md",
            )
        self.assertEqual(installed.name, "focus-review")
        self.assertEqual(installed.installed_from, "url")
        self.assertEqual(
            installed.source_url,
            "https://raw.githubusercontent.com/user/repo/main/SKILL.md",
        )

    def test_install_from_url_invalid_scheme_fails(self):
        mgr = self._manager()
        with self.assertRaises(Exception):
            mgr.install_from_url(self.user_id, "file:///etc/passwd")


class SkillMarketTests(unittest.TestCase):
    """Tests for the skill market backend — list and install."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="market@example.com",
                    hashed_password="x",
                    display_name="Market",
                )
            )
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def test_market_list_returns_skills(self):
        from app.api.v1.routes.skill_market import list_market_skills

        items = list_market_skills()
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        first = items[0]
        self.assertTrue(hasattr(first, "name"))
        self.assertTrue(hasattr(first, "description"))
        self.assertTrue(hasattr(first, "tags"))
        self.assertTrue(hasattr(first, "official"))

    def test_market_install_success(self):
        from app.api.v1.routes.skill_market import _find_market_skill

        item = _find_market_skill("daily-planner")
        self.assertIsNotNone(item)
        content = item["content"]
        self.assertIn("name: daily-planner", content)

        with self.Session() as db:
            mgr = SkillManager(db)
            installed = mgr.install_text(self.user_id, content, installed_from="market")
            self.assertEqual(installed.name, "daily-planner")
            self.assertEqual(installed.installed_from, "market")
            self.assertTrue(installed.enabled)

    def test_market_install_duplicate_fails(self):
        from app.api.v1.routes.skill_market import _find_market_skill

        item = _find_market_skill("learning-tracker")
        content = item["content"]
        with self.Session() as db:
            mgr = SkillManager(db)
            mgr.install_text(self.user_id, content, installed_from="market")
            with self.assertRaises(Exception):
                mgr.install_text(self.user_id, content, installed_from="market")

    def test_market_install_invalid_name_returns_none(self):
        from app.api.v1.routes.skill_market import _find_market_skill

        self.assertIsNone(_find_market_skill("nonexistent-skill-xyz"))

    def test_market_list_does_not_return_content(self):
        """Market list must not leak full SKILL.md content."""
        from app.api.v1.routes.skill_market import list_market_skills

        items = list_market_skills()
        self.assertGreater(len(items), 0)
        for item in items:
            self.assertFalse(
                hasattr(item, "content"),
                f"MarketSkillOut must not expose 'content' field for {item.name}",
            )

    def test_market_skill_has_required_fields(self):
        from app.api.v1.routes.skill_market import _load_market

        items = _load_market()
        self.assertGreaterEqual(len(items), 3)
        for item in items:
            with self.subTest(name=item.get("name", "unknown")):
                self.assertIn("name", item)
                self.assertIn("description", item)
                self.assertIn("content", item)
                self.assertIn("tags", item)
                self.assertIn("version", item)
                self.assertIn("author", item)

    def test_market_skill_content_is_valid_skillmd(self):
        """All market skills must have valid SKILL.md content that parse() accepts."""
        from app.api.v1.routes.skill_market import _load_market

        items = _load_market()
        with self.Session() as db:
            mgr = SkillManager(db)
            for item in items:
                with self.subTest(name=item["name"]):
                    parsed = mgr.parse(item["content"])
                    self.assertTrue(parsed.name)
                    self.assertTrue(parsed.description)


if __name__ == "__main__":
    unittest.main()
